"""
servers.py - Minecraft Server Management Supporting:
- Free Default Auto Domain vs 1,000 KRW Premium Custom Domain
- Server Version/Core Switcher with Mod Loader Dependency Warning
- server.properties Comprehensive GUI Config Editor
- Modrinth & CurseForge Split Tabs, Tag Filters, Infinite Scroll & 1-Click Mod Updater
- Modpack Archive (.zip, .mrpack) Direct Importer
"""
import uuid
import os
import subprocess
import asyncio
import io
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse, FileResponse
from app.models.schema import (
    ServerDeployRequest, ServerControlRequest, RconExecuteRequest,
    TelemetryReportPayload, ServerResponse, AIReportResponse, HelpdeskTicket,
    HelpdeskTicketCreate, TicketResolveRequest, TicketStatus, ServerStatus,
    ServerType, ServerPreset, DomainCheckResponse, FileItem, FileContentRead,
    FileContentSave, ModSearchItem, ModDetailResponse, ModInstallRequest,
    ServerPropertiesModel, ServerVersionChangeRequest, InstalledModItem,
    ModUpdateRequest
)
from app.core.security import sanitize_rcon_command, require_admin_auth
from app.core.database import db
from app.services.node_scheduler import scheduler
from app.services.billing_engine import billing_engine
from app.services.ai_profiler import ai_profiler
from app.services.version_manifest import version_service
from app.services.file_manager import file_manager
from app.services.mod_indexer import mod_engine

router = APIRouter(prefix="/servers", tags=["Minecraft Servers & Management"])

# In-memory Mock Stores
MOCK_SERVERS: Dict[str, Dict[str, Any]] = {
    "mc-demo-01": {
        "id": "mc-demo-01",
        "name": "야생 생존 알파",
        "domain_slug": "alpha",
        "preset_type": ServerPreset.SURVIVAL_SMP,
        "node_id": "master-local",
        "node_ip": "127.0.0.1",
        "port": 25565,
        "rcon_port": 25575,
        "rcon_password": "SafeRconPassword123!",
        "server_type": "PAPER",
        "mc_version": "26.2",
        "allocated_ram_mb": 4096,
        "status": ServerStatus.RUNNING,
        "billing_multiplier": 1.0,
        "full_domain": "alpha.domain.com",
        "is_local_master": True,
        "user_email": "player_steve@gmail.com",
        "injected_plugins": ["EssentialsX (TPA, Home)", "Chunky", "Spark"],
        "created_at": datetime.utcnow()
    }
}

MOCK_TICKETS: Dict[str, Dict[str, Any]] = {
    "TCK-1001": {
        "id": "TCK-1001",
        "server_id": "mc-demo-01",
        "user_email": "player_steve@gmail.com",
        "title": "주말 동접 증가 시 순간적인 TPS 드랍 현상 문의",
        "user_message": "스폰 지점 인근에서 플레이어가 몰릴 때 틱 저하가 발생합니다. AI 진단 결과 엔티티 과밀집으로 나오는데 확인 부탁드립니다.",
        "status": TicketStatus.OPEN,
        "admin_response": None,
        "ai_report_json": {
            "root_cause_summary": "스폰 청크(x:120, z:-340) 내 몬스터 엔티티 과밀집(520마리) 감지",
            "culprits": ["Zombie 엔티티 AI 틱 과부하", "Spawn Chunk Lock"],
            "actionable_steps": ["mob-spawn-range를 8에서 6으로 축소", "/kill @e[type=zombie] 실행 권고"]
        },
        "created_at": datetime.utcnow()
    }
}

# ---------------------------------------------------------------------------
# 1. Mojang Official Version Manifest
# ---------------------------------------------------------------------------
@router.get("/versions")
async def get_available_mc_versions(refresh: bool = False):
    return await version_service.get_version_manifest(force_refresh=refresh)

# ---------------------------------------------------------------------------
# 2. Domain Availability Check
# ---------------------------------------------------------------------------
@router.get("/check-domain", response_model=DomainCheckResponse)
async def check_domain_availability(slug: str = Query(..., min_length=3, max_length=32)):
    clean_slug = slug.lower().strip()
    reserved = {"admin", "api", "auth", "mail", "portal", "dashboard", "root", "status"}
    is_taken = clean_slug in reserved or any(s["domain_slug"].lower() == clean_slug for s in MOCK_SERVERS.values())

    suggested = [f"{clean_slug}-mc", f"{clean_slug}01", f"play-{clean_slug}"] if is_taken else []

    return DomainCheckResponse(
        slug=clean_slug,
        is_available=not is_taken,
        is_premium=True,
        custom_fee_krw=1000,
        suggested_slugs=suggested,
        message="사용 가능한 프리미엄 도메인입니다. (1,000 KRW 차감)" if not is_taken else "이미 사용 중인 도메인입니다. 다른 이름을 선택해주세요."
    )

# ---------------------------------------------------------------------------
# 3. Server Provisioning & Deployment
# ---------------------------------------------------------------------------
def deploy_local_container(server_data: Dict[str, Any], req: ServerDeployRequest):
    try:
        server_id = server_data["id"]
        port = server_data["port"]
        rcon_port = server_data["rcon_port"]
        ram_mb = server_data["allocated_ram_mb"]
        
        swap_cfg = scheduler.get_swap_config()
        swap_mb = int(ram_mb * swap_cfg.swap_ratio)

        rcon_pass = server_data["rcon_password"]
        server_type = server_data["server_type"]
        mc_version = server_data["mc_version"]
        crossplay = "true" if req.enable_crossplay else "false"

        script_path = "/opt/nextgen-mc-platform/scripts/deploy-mc-sandbox.sh"
        if not os.path.exists(script_path):
            script_path = "/home/bettercallsixseven/nextgen-mc-platform/scripts/deploy-mc-sandbox.sh"

        log_dir = "/tmp/nextgen-mc-logs"
        try:
            os.makedirs("/var/log/nextgen-mc", exist_ok=True)
            log_dir = "/var/log/nextgen-mc"
        except Exception:
            os.makedirs(log_dir, exist_ok=True)

        log_file_path = os.path.join(log_dir, f"deploy_{server_id}.log")

        if os.path.exists(script_path):
            cmd = [
                "bash", script_path,
                server_id, str(port), str(rcon_port),
                str(ram_mb), str(swap_mb),
                str(server_type), str(mc_version), str(rcon_pass), crossplay
            ]
            print(f"[Master Local Deploy] Executing: {' '.join(cmd)}")
            with open(log_file_path, "a") as log_f:
                proc = subprocess.Popen(cmd, stdout=log_f, stderr=subprocess.STDOUT)
            print(f"[Master Local Deploy] Process spawned (PID: {proc.pid}). Log: {log_file_path}")
    except Exception as e:
        print(f"[Master Local Deploy Warning] {e}")


@router.post("/deploy")
async def deploy_server(req: ServerDeployRequest):
    """
    서버 배포:
    - is_custom_domain=False 시: 무료 자동 발급 도메인 (mc-xxxxxx.domain.com) -> 요금 0원
    - is_custom_domain=True 시: 사용자 지정 서브도메인 -> 1,000 KRW 차감
    """
    # 1. 도메인 슬러그 결정 (무료 자동 vs 프리미엄 커스텀)
    if req.is_custom_domain and req.domain_slug:
        clean_slug = req.domain_slug.lower().strip()
        if any(s["domain_slug"].lower() == clean_slug for s in MOCK_SERVERS.values()):
            raise HTTPException(
                status_code=400,
                detail=f"접속 도메인 '{clean_slug}.domain.com'은 이미 다른 서버에서 사용 중입니다. 다른 이름을 지정해주세요."
            )
        custom_fee = 1000
    else:
        # 무료 자동 발급
        clean_slug = f"mc-{uuid.uuid4().hex[:6]}"
        custom_fee = 0

    user_email = req.target_user_id or "user@domain.com"
    actual_version = req.mc_version or "26.2"
    actual_server_type = req.server_type.value if hasattr(req.server_type, "value") else str(req.server_type)
    injected_plugins = []

    if req.preset_type == ServerPreset.BUILDER_FLAT:
        actual_server_type = "PAPER"
        injected_plugins = ["FastAsyncWorldEdit", "CoreProtect", "Chunky", "Spark"]
    elif req.preset_type == ServerPreset.SURVIVAL_SMP:
        actual_server_type = "PAPER"
        injected_plugins = ["EssentialsX (TPA, Spawn, Home)", "Chunky", "Spark"]
    elif req.preset_type == ServerPreset.MODPACK_READY:
        if actual_server_type not in ("FORGE", "NEOFORGE", "FABRIC"):
            actual_server_type = "FABRIC"

    assigned_node = scheduler.select_best_node(
        required_ram_mb=req.allocated_ram_mb,
        preferred_tier=req.hardware_tier_preference,
        preferred_node_id=req.preferred_node_id
    )

    server_id = f"mc-{uuid.uuid4().hex[:8]}"
    assigned_port = 25565 + len(MOCK_SERVERS) + 1
    rcon_port = 25575 + len(MOCK_SERVERS) + 1
    rcon_pass = f"RconPass_{uuid.uuid4().hex[:10]}!"

    server_data = {
        "id": server_id,
        "name": req.name,
        "domain_slug": clean_slug,
        "preset_type": req.preset_type,
        "node_id": assigned_node.node_id,
        "node_ip": assigned_node.ip_address,
        "port": assigned_port,
        "rcon_port": rcon_port,
        "rcon_password": rcon_pass,
        "server_type": actual_server_type,
        "mc_version": actual_version,
        "allocated_ram_mb": req.allocated_ram_mb,
        "status": ServerStatus.RUNNING,
        "billing_multiplier": assigned_node.billing_multiplier,
        "full_domain": f"{clean_slug}.domain.com",
        "is_local_master": assigned_node.is_master_node,
        "user_email": user_email,
        "injected_plugins": injected_plugins,
        "created_at": datetime.utcnow()
    }

    MOCK_SERVERS[server_id] = server_data

    # 모드팩 ID가 제공된 경우 자동 설치
    if req.modpack_id:
        try:
            await mod_engine.install_mod_to_server(
                server_id=server_id,
                mod_id_or_slug=req.modpack_id,
                project_type="modpack"
            )
        except Exception:
            pass

    if assigned_node.is_master_node:
        deploy_local_container(server_data, req)

    return {
        "status": "success",
        "server_id": server_id,
        "connect_address": f"{clean_slug}.domain.com (Port 25565 - No port required)",
        "server_type": actual_server_type,
        "mc_version": actual_version,
        "preset_type": req.preset_type,
        "assigned_node": assigned_node.node_name,
        "node_id": assigned_node.node_id,
        "is_master_node": assigned_node.is_master_node,
        "hardware_tier": assigned_node.hardware_tier,
        "billing_multiplier": assigned_node.billing_multiplier,
        "allocated_ram_mb": req.allocated_ram_mb,
        "injected_plugins": injected_plugins,
        "custom_domain_fee_deducted_krw": custom_fee,
        "message": f"[{actual_server_type}] 버전 {actual_version} 서버 [{req.name}]가 성공적으로 배포되었습니다."
    }

# ---------------------------------------------------------------------------
# 4. Server Version / Core Switcher with Mod Loader Dependency Warning
# ---------------------------------------------------------------------------
@router.put("/{server_id}/version")
async def switch_server_version(server_id: str, req: ServerVersionChangeRequest):
    """
    서버의 마인크래프트 버전 및 구동기(코어) 변경
    (모드팩/모드가 설치된 상태에서 비호환 구동기로 변경 시 경고)
    """
    if server_id not in MOCK_SERVERS:
        raise HTTPException(status_code=404, detail="서버를 찾을 수 없습니다.")

    server = MOCK_SERVERS[server_id]
    cur_type = server["server_type"]
    new_type = req.server_type.upper()

    installed_mods = mod_engine.get_installed_mods(server_id)
    has_mods = any(m.project_type == "mod" for m in installed_mods)

    # 모드가 설치되어 있는데 Paper나 Vanilla로 변경하려는 경우
    if has_mods and cur_type in ("FABRIC", "FORGE", "NEOFORGE") and new_type in ("PAPER", "PURPUR", "VANILLA", "SPIGOT"):
        if not req.force:
            raise HTTPException(
                status_code=400,
                detail=f"⚠️ 모드로더 호환성 경고: 현재 서버에 {len(installed_mods)}개의 모드가 설치되어 있습니다. [{new_type}] 구동기로 변경 시 기존 모드들이 실행되지 않습니다. 계속 진행하시려면 '강제 변경'을 선택하십시오."
            )

    server["server_type"] = new_type
    server["mc_version"] = req.mc_version

    return {
        "status": "success",
        "server_id": server_id,
        "server_type": new_type,
        "mc_version": req.mc_version,
        "message": f"서버 구동기가 [{new_type} {req.mc_version}]으로 성공적으로 변경되었습니다. (서버 재시작 시 적용)"
    }

# ---------------------------------------------------------------------------
# 5. server.properties GUI Config Editor API
# ---------------------------------------------------------------------------
@router.get("/{server_id}/properties", response_model=ServerPropertiesModel)
async def get_server_properties_gui(server_id: str):
    """server.properties 전체 설정을 파싱하여 GUI 폼으로 제공"""
    if server_id not in MOCK_SERVERS:
        raise HTTPException(status_code=404, detail="서버를 찾을 수 없습니다.")
    return file_manager.get_parsed_properties(server_id)

@router.put("/{server_id}/properties")
async def save_server_properties_gui(server_id: str, props: ServerPropertiesModel):
    """GUI 폼에서 수정한 server.properties 설정을 서버에 안전하게 저장"""
    if server_id not in MOCK_SERVERS:
        raise HTTPException(status_code=404, detail="서버를 찾을 수 없습니다.")
    return file_manager.save_parsed_properties(server_id, props)

# ---------------------------------------------------------------------------
# 6. Web File Explorer & World ZIP Download
# ---------------------------------------------------------------------------
@router.get("/{server_id}/files", response_model=List[FileItem])
async def list_server_files(server_id: str, path: str = ""):
    if server_id not in MOCK_SERVERS:
        raise HTTPException(status_code=404, detail="서버를 찾을 수 없습니다.")
    return file_manager.list_files(server_id, path)

@router.get("/{server_id}/files/content", response_model=FileContentRead)
async def read_server_file(server_id: str, path: str):
    if server_id not in MOCK_SERVERS:
        raise HTTPException(status_code=404, detail="서버를 찾을 수 없습니다.")
    return file_manager.read_file_content(server_id, path)

@router.put("/{server_id}/files/content")
async def save_server_file(server_id: str, req: FileContentSave):
    if server_id not in MOCK_SERVERS:
        raise HTTPException(status_code=404, detail="서버를 찾을 수 없습니다.")
    return file_manager.save_file_content(server_id, req.path, req.content)

@router.post("/{server_id}/files/upload")
async def upload_server_file(
    server_id: str,
    path: str = Form(""),
    file: UploadFile = File(...)
):
    if server_id not in MOCK_SERVERS:
        raise HTTPException(status_code=404, detail="서버를 찾을 수 없습니다.")
    contents = await file.read()
    return file_manager.save_uploaded_file(server_id, path, file.filename, contents)

@router.get("/{server_id}/files/download")
async def download_single_file(server_id: str, path: str):
    if server_id not in MOCK_SERVERS:
        raise HTTPException(status_code=404, detail="서버를 찾을 수 없습니다.")
    abs_path = file_manager._resolve_safe_path(server_id, path)
    if not os.path.exists(abs_path) or os.path.isdir(abs_path):
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(abs_path, filename=os.path.basename(abs_path), media_type="application/octet-stream")

@router.get("/{server_id}/world/download")
async def download_world_zip(server_id: str):
    if server_id not in MOCK_SERVERS:
        raise HTTPException(status_code=404, detail="서버를 찾을 수 없습니다.")
    server = MOCK_SERVERS[server_id]
    zip_stream = file_manager.create_world_archive_stream(server_id)
    zip_filename = f"{server['domain_slug']}_world_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.zip"
    return StreamingResponse(
        zip_stream,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'}
    )

# ---------------------------------------------------------------------------
# 7. Modrinth & CurseForge Marketplace (Tabs, Tags, Infinite Scroll & Updater)
# ---------------------------------------------------------------------------
@router.get("/mods/categories")
async def get_mod_categories_and_tags(source: str = "modrinth"):
    """Modrinth 및 CurseForge 전체 태그/카테고리 목록 조회"""
    return mod_engine.get_categories_and_tags(source)

@router.get("/mods/search", response_model=List[ModSearchItem])
async def search_mods(
    query: str = "",
    loader: Optional[str] = "all",
    version: Optional[str] = "all",
    project_type: Optional[str] = None, # "mod" or "modpack"
    source: Optional[str] = "modrinth", # "modrinth" or "curseforge"
    category: Optional[str] = None,
    offset: int = 0,
    limit: int = 10
):
    """모드 & 모드팩 실시간 검색 (무한 스크롤 및 소스/태그/버전 필터 지원)"""
    return await mod_engine.search_projects(
        query=query,
        loader=loader,
        version=version,
        project_type=project_type,
        source=source,
        category=category,
        offset=offset,
        limit=limit
    )

@router.get("/mods/{mod_id}", response_model=ModDetailResponse)
async def get_mod_detail(mod_id: str):
    return await mod_engine.get_project_detail(mod_id)

@router.post("/{server_id}/mods/install")
async def install_mod_to_server(server_id: str, req: ModInstallRequest):
    if server_id not in MOCK_SERVERS:
        raise HTTPException(status_code=404, detail="서버를 찾을 수 없습니다.")

    return await mod_engine.install_mod_to_server(
        server_id=server_id,
        mod_id_or_slug=req.mod_id,
        project_type=req.project_type,
        source=req.source,
        custom_download_url=req.download_url,
        custom_filename=req.filename
    )

@router.get("/{server_id}/installed-mods", response_model=List[InstalledModItem])
async def get_installed_mods(server_id: str):
    """현재 서버에 설치된 모드/플러그인 및 업데이트 가능 여부 조회"""
    if server_id not in MOCK_SERVERS:
        raise HTTPException(status_code=404, detail="서버를 찾을 수 없습니다.")
    return mod_engine.get_installed_mods(server_id)

@router.post("/{server_id}/mods/update")
async def update_installed_mods(server_id: str, req: ModUpdateRequest):
    """설치된 모드/플러그인 최신 버전으로 1클릭 일괄/선택 업데이트"""
    if server_id not in MOCK_SERVERS:
        raise HTTPException(status_code=404, detail="서버를 찾을 수 없습니다.")
    return await mod_engine.update_mods(server_id, req.mod_ids)

@router.post("/{server_id}/modpack/import")
async def import_modpack_archive_file(
    server_id: str,
    file: UploadFile = File(...)
):
    """CurseForge ZIP 또는 Modrinth .mrpack 모드팩 아카이브 직접 업로드 및 서버 임포트"""
    if server_id not in MOCK_SERVERS:
        raise HTTPException(status_code=404, detail="서버를 찾을 수 없습니다.")

    contents = await file.read()
    return mod_engine.import_modpack_archive(server_id, file.filename, contents)

# ---------------------------------------------------------------------------
# 8. RCON & Telemetry & AI Diagnostic
# ---------------------------------------------------------------------------
@router.post("/{server_id}/rcon")
async def execute_rcon(server_id: str, req: RconExecuteRequest):
    if server_id not in MOCK_SERVERS:
        raise HTTPException(status_code=404, detail="서버를 찾을 수 없습니다.")

    clean_cmd = sanitize_rcon_command(req.command)
    server = MOCK_SERVERS[server_id]
    return {
        "server_id": server_id,
        "command_executed": clean_cmd,
        "response": f"[{server['name']}] Command '{clean_cmd}' executed successfully."
    }

@router.post("/{server_id}/telemetry")
async def receive_telemetry(server_id: str, payload: TelemetryReportPayload):
    server = MOCK_SERVERS.get(server_id, {})
    data = payload.dict()
    data["server_meta"] = server
    await billing_engine.process_telemetry(data)
    return {"status": "recorded"}

@router.post("/{server_id}/ai-diagnose", response_model=AIReportResponse)
async def trigger_ai_diagnostic(server_id: str, spark_dump: str = ""):
    telemetry = {"loaded_chunks": 850, "active_players": 12, "tps": 14.2}
    report = await ai_profiler.analyze_profiler_dump(
        server_id=server_id,
        spark_summary=spark_dump or "Spark Profiler Tick Breakdown: 65% EntityTick (Zombie near x:120, z:-340), 20% ChunkProviderServer",
        telemetry=telemetry
    )
    return report

# ---------------------------------------------------------------------------
# 9. Admin Server & Helpdesk Endpoints
# ---------------------------------------------------------------------------
@router.get("/admin/all", dependencies=[Depends(require_admin_auth)])
async def get_all_servers_admin():
    return list(MOCK_SERVERS.values())

@router.post("/admin/{server_id}/force-action", dependencies=[Depends(require_admin_auth)])
async def force_server_action(server_id: str, req: ServerControlRequest):
    if server_id not in MOCK_SERVERS:
        raise HTTPException(status_code=404, detail="서버를 찾을 수 없습니다.")

    server = MOCK_SERVERS[server_id]
    if req.action in ("stop", "kill"):
        server["status"] = ServerStatus.STOPPED
        try:
            subprocess.run(["docker", "stop", server_id], check=False, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    elif req.action in ("start", "restart"):
        server["status"] = ServerStatus.RUNNING
        try:
            subprocess.run(["docker", "start", server_id], check=False, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    return {
        "status": "success",
        "server_id": server_id,
        "action": req.action,
        "new_status": server["status"],
        "message": f"서버 [{server['name']}]에 대해 '{req.action}' 강제 명령이 수행되었습니다."
    }

@router.delete("/admin/{server_id}", dependencies=[Depends(require_admin_auth)])
async def force_destroy_server(server_id: str):
    if server_id not in MOCK_SERVERS:
        raise HTTPException(status_code=404, detail="서버를 찾을 수 없습니다.")

    server = MOCK_SERVERS.pop(server_id)
    try:
        subprocess.run(["docker", "rm", "-f", server_id], check=False, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    return {
        "status": "success",
        "server_id": server_id,
        "message": f"서버 [{server['name']}]가 클러스터에서 완전히 제거되었습니다."
    }

@router.get("/admin/tickets", dependencies=[Depends(require_admin_auth)])
async def get_all_tickets():
    return list(MOCK_TICKETS.values())

@router.post("/tickets/create")
async def create_support_ticket(ticket: HelpdeskTicketCreate):
    t_id = f"TCK-{uuid.uuid4().hex[:4].upper()}"
    new_ticket = {
        "id": t_id,
        "server_id": ticket.server_id,
        "user_email": ticket.user_email,
        "title": ticket.title,
        "user_message": ticket.user_message,
        "status": TicketStatus.OPEN,
        "admin_response": None,
        "ai_report_json": ticket.ai_report_json,
        "created_at": datetime.utcnow()
    }
    MOCK_TICKETS[t_id] = new_ticket
    return {
        "status": "ticket_created",
        "ticket_id": t_id,
        "message": "AI 진단 리포트가 포함된 기술지원 티켓이 어드민 팀으로 전달되었습니다."
    }

@router.post("/admin/tickets/resolve", dependencies=[Depends(require_admin_auth)])
async def resolve_ticket_admin(req: TicketResolveRequest):
    if req.ticket_id not in MOCK_TICKETS:
        raise HTTPException(status_code=404, detail="해당 티켓을 찾을 수 없습니다.")

    t = MOCK_TICKETS[req.ticket_id]
    t["status"] = req.status
    t["admin_response"] = req.admin_response
    t["resolved_at"] = datetime.utcnow()

    return {
        "status": "success",
        "ticket_id": req.ticket_id,
        "new_status": req.status,
        "message": f"[{req.ticket_id}] 민원에 대한 답변이 등록되고 상태가 '{req.status}'로 갱신되었습니다."
    }
