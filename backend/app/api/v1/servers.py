"""
servers.py - Minecraft Server Management, Deployment, RCON & AI Diagnostics
"""
import uuid
import httpx
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

# In-memory mock server store for demonstration / testing
MOCK_SERVERS: Dict[str, Dict[str, Any]] = {}

@router.post("/deploy")
async def deploy_server(req: ServerDeployRequest):
    """
    서버 생성 요청:
    1. 스케줄러가 자원 가용성(RAM, ZRAM) 및 선호 티어에 맞는 최적의 워커 노드 선택
    2. 워커 노드로 컨테이너 생성 디스패치
    3. Dynamic Ingress (Velocity) 라우팅 맵 등록 (id.domain.com -> node_ip:port)
    """
    # 최적 노드 선정 (부하 분산 & OOM 임계치 검증)
    assigned_node = scheduler.select_best_node(
        required_ram_mb=req.allocated_ram_mb,
        preferred_tier=req.hardware_tier_preference
    )

    server_id = f"mc-{uuid.uuid4().hex[:8]}"
    assigned_port = 25565 + len(MOCK_SERVERS) + 1
    rcon_port = 25575 + len(MOCK_SERVERS) + 1
    rcon_pass = f"RconPass_{uuid.uuid4().hex[:12]}"

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
        "full_domain": f"{req.domain_slug}.domain.com"
    }

    MOCK_SERVERS[server_id] = server_data

    # Redis 라우팅 맵 등록 (Velocity 프록시가 읽어 포워딩)
    if db.redis:
        await db.redis.hset("routing:map:java", f"{req.domain_slug}.domain.com", f"{assigned_node.ip_address}:{assigned_port}")

    return {
        "status": "success",
        "server_id": server_id,
        "connect_address": f"{req.domain_slug}.domain.com (Port 25565 - No port required)",
        "assigned_node": assigned_node.node_name,
        "hardware_tier": assigned_node.hardware_tier,
        "billing_multiplier": assigned_node.billing_multiplier,
        "allocated_ram_mb": req.allocated_ram_mb
    }

@router.post("/{server_id}/rcon")
async def execute_rcon(server_id: str, req: RconExecuteRequest):
    """
    RCON 명령어 실행 (보안 Sanitizer 적용)
    """
    if server_id not in MOCK_SERVERS:
        raise HTTPException(status_code=404, detail="서버를 찾을 수 없습니다.")

    # 1. 원격 코드 실행 및 CRLF 인젝션 방어 살균
    clean_cmd = sanitize_rcon_command(req.command)

    server = MOCK_SERVERS[server_id]
    # 실제 환경에서는 AsyncRconClient를 통해 실행
    return {
        "server_id": server_id,
        "command_executed": clean_cmd,
        "response": f"[Server Output for '{clean_cmd}']: Command executed successfully."
    }

@router.post("/{server_id}/telemetry")
async def receive_telemetry(server_id: str, payload: TelemetryReportPayload):
    """
    Worker 플러그인에서 1분마다 발송되는 텔레메트리 수신 및 실시간 과금 연산
    """
    server = MOCK_SERVERS.get(server_id, {})
    data = payload.dict()
    data["server_meta"] = server
    await billing_engine.process_telemetry(data)
    return {"status": "recorded"}

@router.post("/{server_id}/ai-diagnose", response_model=AIReportResponse)
async def trigger_ai_diagnostic(server_id: str, spark_dump: str = ""):
    """
    서버 틱(TPS) 저하 시 Spark Profiler 덤프를 로컬 LLM으로 전송하여 렉 원인 자동 분석
    """
    telemetry = {"loaded_chunks": 850, "active_players": 12, "tps": 14.2}
    report = await ai_profiler.analyze_profiler_dump(
        server_id=server_id,
        spark_summary=spark_dump or "Spark Profiler Tick Breakdown: 65% EntityTick (Zombie near x:120, z:-340), 20% ChunkProviderServer",
        telemetry=telemetry
    )
    return report

@router.post("/tickets/create")
async def create_support_ticket(ticket: HelpdeskTicketCreate):
    """
    AI 진단 리포트를 포함하여 관리자 헬프데스크로 원클릭 티켓 전송
    """
    return {
        "status": "ticket_created",
        "ticket_id": f"TICKET-{uuid.uuid4().hex[:6].upper()}",
        "server_id": ticket.server_id,
        "title": ticket.title,
        "attached_ai_report": ticket.ai_report_json is not None,
        "message": "AI 원인 분석 리포트와 시스템 로그가 어드민 기술지원 팀으로 전달되었습니다."
    }
