"""
servers.py - Minecraft Server Management Supporting:
- All Versions (Releases + Snapshots from Mojang Manifest)
- Core Types: PAPER, PURPUR, FOLIA, FABRIC, FORGE, NEOFORGE, SPONGE, VANILLA, SPIGOT, CRAFTBUKKIT, VELOCITY, BUNGEECORD
- Dynamic Custom Tiers & Swap Ratios
- Presets & Web RCON & AI Profiler
"""
import uuid
import os
import re
import subprocess
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from app.models.schema import (
    ServerDeployRequest, ServerControlRequest, RconExecuteRequest,
    TelemetryReportPayload, ServerResponse, AIReportResponse, HelpdeskTicket,
    HelpdeskTicketCreate, TicketResolveRequest, TicketStatus, ServerStatus,
    ServerType, ServerPreset
)
from app.core.security import sanitize_rcon_command, require_admin_auth
from app.core.database import db
from app.services.node_scheduler import scheduler
from app.services.billing_engine import billing_engine
from app.services.ai_profiler import ai_profiler
from app.services.version_manifest import version_service

router = APIRouter(prefix="/servers", tags=["Minecraft Servers & Helpdesk"])

VALID_VER_REGEX = re.compile(r"^(1\.\d+(\.\d+)?|\d{2}w\d{2}[a-z]|1\.\d+-pre\d+|latest)$")

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
        "server_type": ServerType.PAPER,
        "mc_version": "1.20.4",
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
# 1. Mojang Official Version Manifest (Releases + Snapshots)
# ---------------------------------------------------------------------------
@router.get("/versions")
async def get_available_mc_versions(refresh: bool = False):
    """모장(Mojang) 공식 API에서 정규 릴리즈 및 개발 스냅샷(Snapshots) 목록 조회"""
    manifest = await version_service.get_version_manifest(force_refresh=refresh)
    return manifest

# ---------------------------------------------------------------------------
# 2. Local Container Deployment Helper (Safe Fallback Logging)
# ---------------------------------------------------------------------------
def deploy_local_container(server_data: Dict[str, Any], req: ServerDeployRequest):
    try:
        server_id = server_data["id"]
        port = server_data["port"]
        rcon_port = server_data["rcon_port"]
        ram_mb = server_data["allocated_ram_mb"]
        
        # 어드민이 설정한 글로벌 스왑 비율 적용
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
            print(f"[Master Local Deploy] Process spawned (PID: {proc.pid}). Output logged to: {log_file_path}")
    except Exception as e:
        print(f"[Master Local Deploy Warning] Local container deployment encountered an issue: {e}")


@router.post("/deploy")
async def deploy_server(req: ServerDeployRequest):
    """
    마인크래프트 서버 또는 프록시(Velocity/Bungee) 배포
    - 버전 검증 및 1.20.4 기본 안정화 가드 탑재
    - 전체 12대 구동기 및 스냅샷 지원
    """
    injected_plugins = []
    actual_version = req.mc_version
    actual_server_type = req.server_type.value if hasattr(req.server_type, "value") else str(req.server_type)

    # 1. 프리셋별 코어 및 버전 자동 보정
    if req.preset_type == ServerPreset.BUILDER_FLAT:
        actual_server_type = "PAPER"
        actual_version = "1.20.4"
        injected_plugins = ["FastAsyncWorldEdit", "CoreProtect", "Chunky", "Spark"]
    elif req.preset_type == ServerPreset.SURVIVAL_SMP:
        actual_server_type = "PAPER"
        actual_version = "1.20.4"
        injected_plugins = ["EssentialsX (TPA, Spawn, Home)", "Chunky", "Spark"]
    elif actual_server_type == "VELOCITY":
        actual_version = "latest"
        injected_plugins = ["Velocity L4 Forwarding", "RedisBungeeBridge"]
    elif actual_server_type in ("BUNGEECORD", "WATERFALL"):
        actual_version = "latest"
        injected_plugins = ["BungeeGuard", "RedisBungee"]
    else:
        # 버전 정규식 검증 (비정상 버전이 들어오면 1.20.4로 자동 교정)
        if not actual_version or not VALID_VER_REGEX.match(actual_version):
            print(f"[Deploy Warning] Invalid MC version detected ('{actual_version}'). Fallback to 1.20.4.")
            actual_version = "1.20.4"

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
        "domain_slug": req.domain_slug,
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
        "full_domain": f"{req.domain_slug}.domain.com",
        "is_local_master": assigned_node.is_master_node,
        "user_email": req.target_user_id or "user@domain.com",
        "injected_plugins": injected_plugins,
        "created_at": datetime.utcnow()
    }

    MOCK_SERVERS[server_id] = server_data

    if assigned_node.is_master_node:
        deploy_local_container(server_data, req)

    if db.redis:
        try:
            await db.redis.hset("routing:map:java", f"{req.domain_slug}.domain.com", f"{assigned_node.ip_address}:{assigned_port}")
        except Exception:
            pass

    return {
        "status": "success",
        "server_id": server_id,
        "connect_address": f"{req.domain_slug}.domain.com (Port 25565 - No port required)",
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
        "message": f"[{actual_server_type}] 버전 {actual_version} 서버 [{req.name}]가 성공적으로 배포되었습니다."
    }

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
# Admin Server & Helpdesk Endpoints (Protected by require_admin_auth)
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
