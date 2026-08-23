"""
servers.py - Minecraft Server Management, Deployment (Master & Worker), RCON & AI Diagnostics
"""
import uuid
import os
import subprocess
import asyncio
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends, status
from app.models.schema import (
    ServerDeployRequest, ServerControlRequest, RconExecuteRequest,
    TelemetryReportPayload, ServerResponse, AIReportResponse, HelpdeskTicketCreate
)
from app.core.security import sanitize_rcon_command
from app.core.database import db
from app.services.node_scheduler import scheduler
from app.services.billing_engine import billing_engine
from app.services.ai_profiler import ai_profiler

router = APIRouter(prefix="/servers", tags=["Minecraft Servers"])

MOCK_SERVERS: Dict[str, Dict[str, Any]] = {}

def deploy_local_container(server_data: Dict[str, Any], req: ServerDeployRequest):
    """
    Master 노드 로컬에서 직접 격리 컨테이너 구동 (Master-as-Worker)
    """
    server_id = server_data["id"]
    port = server_data["port"]
    rcon_port = server_data["rcon_port"]
    ram_mb = server_data["allocated_ram_mb"]
    swap_mb = int(ram_mb * 1.5)
    rcon_pass = server_data["rcon_password"]
    server_type = req.server_type.value if hasattr(req.server_type, "value") else str(req.server_type)
    mc_version = req.mc_version
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
    서버 생성 요청:
    1. 스케줄러가 자원 가용성(RAM, ZRAM)을 검증하여 최적의 노드(Master 또는 Worker) 선택
    2. Master 노드 선정 시 로컬 샌드박스 배포기 즉시 실행
    3. Redis 라우팅 맵에 id.domain.com 매핑 등록
    """
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
        "node_id": assigned_node.node_id,
        "node_ip": assigned_node.ip_address,
        "port": assigned_port,
        "rcon_port": rcon_port,
        "rcon_password": rcon_pass,
        "server_type": req.server_type,
        "mc_version": req.mc_version,
        "allocated_ram_mb": req.allocated_ram_mb,
        "status": "RUNNING",
        "billing_multiplier": assigned_node.billing_multiplier,
        "full_domain": f"{req.domain_slug}.domain.com",
        "is_local_master": assigned_node.is_master_node
    }

    MOCK_SERVERS[server_id] = server_data

    # Master 로컬 노드인 경우 로컬 도커 샌드박스 배포 실행
    if assigned_node.is_master_node:
        deploy_local_container(server_data, req)

    # Redis 라우팅 맵 등록 (Velocity 프록시 연동)
    if db.redis:
        await db.redis.hset("routing:map:java", f"{req.domain_slug}.domain.com", f"{assigned_node.ip_address}:{assigned_port}")

    return {
        "status": "success",
        "server_id": server_id,
        "connect_address": f"{req.domain_slug}.domain.com (Port 25565 - No port required)",
        "assigned_node": assigned_node.node_name,
        "node_id": assigned_node.node_id,
        "is_master_node": assigned_node.is_master_node,
        "hardware_tier": assigned_node.hardware_tier,
        "billing_multiplier": assigned_node.billing_multiplier,
        "allocated_ram_mb": req.allocated_ram_mb
    }

@router.post("/{server_id}/rcon")
async def execute_rcon(server_id: str, req: RconExecuteRequest):
    """RCON 명령어 실행 (보안 Sanitizer 적용)"""
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
    """Worker 또는 Master 로컬 컨테이너의 1분 주기 과금 텔레메트리 수신"""
    server = MOCK_SERVERS.get(server_id, {})
    data = payload.dict()
    data["server_meta"] = server
    await billing_engine.process_telemetry(data)
    return {"status": "recorded"}

@router.post("/{server_id}/ai-diagnose", response_model=AIReportResponse)
async def trigger_ai_diagnostic(server_id: str, spark_dump: str = ""):
    """Spark Profiler 덤프를 로컬 LLM으로 분석하여 렉 원인 진단"""
    telemetry = {"loaded_chunks": 850, "active_players": 12, "tps": 14.2}
    report = await ai_profiler.analyze_profiler_dump(
        server_id=server_id,
        spark_summary=spark_dump or "Spark Profiler Tick Breakdown: 65% EntityTick (Zombie near x:120, z:-340), 20% ChunkProviderServer",
        telemetry=telemetry
    )
    return report

@router.post("/tickets/create")
async def create_support_ticket(ticket: HelpdeskTicketCreate):
    """AI 진단 리포트를 포함하여 관리자 헬프데스크로 원클릭 티켓 전송"""
    return {
        "status": "ticket_created",
        "ticket_id": f"TICKET-{uuid.uuid4().hex[:6].upper()}",
        "server_id": ticket.server_id,
        "title": ticket.title,
        "attached_ai_report": ticket.ai_report_json is not None,
        "message": "AI 원인 분석 리포트와 시스템 로그가 어드민 기술지원 팀으로 전달되었습니다."
    }
