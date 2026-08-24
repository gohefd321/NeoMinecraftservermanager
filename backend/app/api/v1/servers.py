"""
servers.py - Minecraft Server Management with 3 Supported Versions and 3 Server Presets
Supported Presets:
1. BUILDER_FLAT (건축: 평지맵, WorldEdit, CoreProtect, 최적화)
2. SURVIVAL_SMP (야생: 일반맵, EssentialsX TPA/Home, Spark 렉방지)
3. ADVANCED_CUSTOM (고급: Paper/Fabric/NeoForge, 3대 버전, 세부 RAM)
"""
import uuid
import os
import subprocess
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from app.models.schema import (
    ServerDeployRequest, ServerControlRequest, RconExecuteRequest,
    TelemetryReportPayload, ServerResponse, AIReportResponse, HelpdeskTicket,
    HelpdeskTicketCreate, TicketResolveRequest, TicketStatus, ServerStatus,
    ServerType, ServerPreset, SupportedMCVersion
)
from app.core.security import sanitize_rcon_command, require_admin_auth
from app.core.database import db
from app.services.node_scheduler import scheduler
from app.services.billing_engine import billing_engine
from app.services.ai_profiler import ai_profiler

router = APIRouter(prefix="/servers", tags=["Minecraft Servers & Helpdesk"])

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

def deploy_local_container(server_data: Dict[str, Any], req: ServerDeployRequest):
    server_id = server_data["id"]
    port = server_data["port"]
    rcon_port = server_data["rcon_port"]
    ram_mb = server_data["allocated_ram_mb"]
    swap_mb = int(ram_mb * 1.5)
    rcon_pass = server_data["rcon_password"]
    server_type = req.server_type.value if hasattr(req.server_type, "value") else str(req.server_type)
    mc_version = req.mc_version.value if hasattr(req.mc_version, "value") else str(req.mc_version)
    crossplay = "true" if req.enable_crossplay else "false"

    script_path = "/opt/nextgen-mc-platform/scripts/deploy-mc-sandbox.sh"
    if not os.path.exists(script_path):
        script_path = "/home/bettercallsixseven/nextgen-mc-platform/scripts/deploy-mc-sandbox.sh"

    if os.path.exists(script_path):
        try:
            cmd = [
                "bash", script_path,
                server_id, str(port), str(rcon_port),
                str(ram_mb), str(swap_mb),
                server_type, mc_version, rcon_pass, crossplay
            ]
            print(f"[Master Local Deploy] Executing: {' '.join(cmd)}")
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"[Master Local Deploy Error] {e}")


@router.post("/deploy")
async def deploy_server(req: ServerDeployRequest):
    """
    서버 생성 요청 (3가지 프리셋 및 3대 버전 지원)
    1. BUILDER_FLAT: 평지 맵, 월드에딧, 코어프로텍트 자동 탑재
    2. SURVIVAL_SMP: 야생 맵, EssentialsX (TPA/Home), Spark 자동 탑재
    3. ADVANCED_CUSTOM: 고급 커스텀 사용자 정의
    """
    # 프리셋별 기본 파라미터 보정
    injected_plugins = []
    actual_version = req.mc_version.value if hasattr(req.mc_version, "value") else str(req.mc_version)
    actual_server_type = req.server_type

    if req.preset_type == ServerPreset.BUILDER_FLAT:
        actual_server_type = ServerType.PAPER
        actual_version = "1.20.4"
        injected_plugins = ["FastAsyncWorldEdit", "CoreProtect", "Chunky", "Spark"]
    elif req.preset_type == ServerPreset.SURVIVAL_SMP:
        actual_server_type = ServerType.PAPER
        actual_version = "1.20.4"
        injected_plugins = ["EssentialsX (TPA, Spawn, Home)", "Chunky", "Spark"]

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
        "preset_type": req.preset_type,
        "assigned_node": assigned_node.node_name,
        "node_id": assigned_node.node_id,
        "is_master_node": assigned_node.is_master_node,
        "hardware_tier": assigned_node.hardware_tier,
        "billing_multiplier": assigned_node.billing_multiplier,
        "allocated_ram_mb": req.allocated_ram_mb,
        "injected_plugins": injected_plugins,
        "message": f"[{req.preset_type.value}] 프리셋 기반 서버 [{req.name}]가 성공적으로 배포되었습니다."
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
