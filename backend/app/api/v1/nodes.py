"""
nodes.py - Worker Node Management, Dynamic Admin Billing Rates & Master-as-Worker Monitoring
Protected by Admin Auth Gateway
"""
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from app.models.schema import (
    NodeRegisterRequest, NodeHealthReport, BillingRateConfig, NodeMultiplierUpdate
)
from app.services.node_scheduler import scheduler
from app.services.billing_engine import billing_engine
from app.core.security import require_admin_auth

router = APIRouter(prefix="/nodes", tags=["Worker Nodes & Admin Billing"])

@router.post("/register")
async def register_node(req: NodeRegisterRequest):
    node = scheduler.register_node(req)
    return {
        "status": "success",
        "node_id": node.node_id,
        "hardware_tier": node.hardware_tier,
        "billing_multiplier": node.billing_multiplier,
        "is_master_node": node.is_master_node,
        "message": f"노드 [{node.node_name}]가 성공적으로 클러스터에 등록되었습니다."
    }

@router.post("/health")
async def report_health(report: NodeHealthReport):
    scheduler.update_health(report)
    return {"status": "ok"}

# ---------------------------------------------------------------------------
# Dynamic Admin Billing Endpoints (어드민 인증 필수)
# ---------------------------------------------------------------------------
@router.get("/admin/billing/rates", response_model=BillingRateConfig, dependencies=[Depends(require_admin_auth)])
async def get_current_billing_rates():
    """어드민 대시보드: 현재 적용 중인 기본비, 청크당 요율, 플레이어당 요율, 티어별 배율 조회"""
    return billing_engine.get_current_rates()

@router.put("/admin/billing/rates", response_model=BillingRateConfig, dependencies=[Depends(require_admin_auth)])
async def update_billing_rates(new_rates: BillingRateConfig):
    """어드민 대시보드: 청크, 플레이어, 기본 유지비 및 티어 배율 실시간 변경"""
    updated = await billing_engine.update_billing_rates(new_rates)
    return updated

@router.post("/admin/nodes/set-multiplier", dependencies=[Depends(require_admin_auth)])
async def set_custom_node_multiplier(payload: NodeMultiplierUpdate):
    """어드민 대시보드: 특정 워커/마스터 노드의 과금 배율만 개별적으로 즉시 수정"""
    ok = scheduler.set_node_multiplier(payload.node_id, payload.custom_multiplier)
    if not ok:
        raise HTTPException(status_code=404, detail=f"노드 ID [{payload.node_id}]를 찾을 수 없습니다.")
    return {
        "status": "success",
        "node_id": payload.node_id,
        "new_multiplier": payload.custom_multiplier,
        "message": f"노드 [{payload.node_id}]의 과금 배율이 {payload.custom_multiplier}x로 변경되었습니다."
    }

@router.get("/admin/overview", dependencies=[Depends(require_admin_auth)])
async def get_cluster_admin_overview():
    """
    어드민 대시보드: Master 노드(로컬 컨테이너 엔진) 및 모든 Worker 노드의 CPU, RAM, ZRAM 활용도 실시간 조회
    """
    scheduler.update_master_local_health()

    result = []
    for node_id, node in scheduler.nodes.items():
        h = node.latest_health
        item = {
            "node_id": node.node_id,
            "node_name": node.node_name,
            "ip_address": node.ip_address,
            "hardware_tier": node.hardware_tier,
            "billing_multiplier": node.billing_multiplier,
            "is_master_node": node.is_master_node,
            "status": "ONLINE" if (h is not None) else "OFFLINE",
            "cpu_usage_pct": h.cpu_usage_pct if h else 0.0,
            "ram_used_mb": h.ram_used_mb if h else 0,
            "ram_total_mb": h.ram_total_mb if h else node.total_ram_mb,
            "zram_used_mb": h.zram_used_mb if h else 0,
            "zram_total_mb": h.zram_total_mb if h else node.total_zram_mb,
            "nvme_swap_used_mb": h.nvme_swap_used_mb if h else 0,
            "running_containers": h.running_containers_count if h else 0,
            "schedulable": True if (h and (h.ram_used_mb / max(h.ram_total_mb, 1) < 0.90)) else False
        }
        result.append(item)

    rates = billing_engine.get_current_rates()
    return {
        "nodes": result,
        "total_nodes": len(result),
        "current_rates": rates.dict()
    }
