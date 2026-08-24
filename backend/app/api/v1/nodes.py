"""
nodes.py - Worker Node Management, Dynamic Admin Billing Rates, Custom Tiers & Swap Config
Protected by Admin Auth Gateway
"""
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from app.models.schema import (
    NodeRegisterRequest, NodeHealthReport, BillingRateConfig, NodeMultiplierUpdate,
    CustomTierCreate, CustomTierResponse, SwapConfigModel
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
# Hardware Tiers (공용 조회 & 어드민 관리)
# ---------------------------------------------------------------------------
@router.get("/tiers", response_model=List[CustomTierResponse])
async def get_available_tiers():
    """모든 활성 과금 티어 목록 조회 (유저 서버 생성 시 선택 가능한 티어들)"""
    return scheduler.get_all_tiers()

@router.post("/admin/tiers", response_model=CustomTierResponse, dependencies=[Depends(require_admin_auth)])
async def create_custom_tier(payload: CustomTierCreate):
    """어드민 대시보드: 커스텀 하드웨어 티어 생성 및 특정 노드들 묶기 (인증 필수)"""
    return scheduler.create_custom_tier(payload)

@router.delete("/admin/tiers/{tier_id}", dependencies=[Depends(require_admin_auth)])
async def delete_custom_tier(tier_id: str):
    """어드민 대시보드: 커스텀 하드웨어 티어 삭제 (인증 필수)"""
    ok = scheduler.delete_custom_tier(tier_id)
    if not ok:
        raise HTTPException(status_code=404, detail="해당 티어를 찾을 수 없습니다.")
    return {"status": "success", "message": f"티어 [{tier_id}]가 삭제되었습니다."}

# ---------------------------------------------------------------------------
# Global Swap / ZRAM / Swappiness Configuration (어드민 관리)
# ---------------------------------------------------------------------------
@router.get("/admin/swap-config", response_model=SwapConfigModel, dependencies=[Depends(require_admin_auth)])
async def get_swap_configuration():
    """어드민 대시보드: 글로벌 스왑 비율, ZRAM 압축 알고리즘, Swappiness 설정 조회 (인증 필수)"""
    return scheduler.get_swap_config()

@router.put("/admin/swap-config", response_model=SwapConfigModel, dependencies=[Depends(require_admin_auth)])
async def update_swap_configuration(payload: SwapConfigModel):
    """어드민 대시보드: 글로벌 스왑 비율 (RAM x N배), ZRAM 압축 알고리즘, Swappiness 변경 및 실시간 적용 (인증 필수)"""
    return scheduler.update_swap_config(payload)

# ---------------------------------------------------------------------------
# Dynamic Admin Billing Endpoints (어드민 인증 필수)
# ---------------------------------------------------------------------------
@router.get("/admin/billing/rates", response_model=BillingRateConfig, dependencies=[Depends(require_admin_auth)])
async def get_current_billing_rates():
    """어드민 대시보드: 현재 적용 중인 기본비, 청크당 요율, 플레이어당 요율 조회"""
    return billing_engine.get_current_rates()

@router.put("/admin/billing/rates", response_model=BillingRateConfig, dependencies=[Depends(require_admin_auth)])
async def update_billing_rates(new_rates: BillingRateConfig):
    """어드민 대시보드: 청크, 플레이어, 기본 유지비 실시간 변경"""
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
    """어드민 대시보드: Master 및 모든 Worker 노드의 CPU, RAM, ZRAM 활용도 실시간 조회"""
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
    tiers = scheduler.get_all_tiers()
    swap_cfg = scheduler.get_swap_config()

    return {
        "nodes": result,
        "total_nodes": len(result),
        "current_rates": rates.dict(),
        "custom_tiers": [t.dict() for t in tiers],
        "swap_config": swap_cfg.dict()
    }
