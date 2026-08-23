"""
nodes.py - Worker Node Registration, Real-Time Health Reporting & Admin Resource View
"""
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from app.models.schema import NodeRegisterRequest, NodeHealthReport
from app.services.node_scheduler import scheduler, TIER_MULTIPLIERS

router = APIRouter(prefix="/nodes", tags=["Worker Nodes & Cluster"])

@router.post("/register")
async def register_node(req: NodeRegisterRequest):
    node = scheduler.register_node(req)
    return {
        "status": "success",
        "node_id": node.node_id,
        "hardware_tier": node.hardware_tier,
        "billing_multiplier": node.billing_multiplier,
        "message": f"Worker 노드 [{node.node_name}]가 성공적으로 클러스터에 등록되었습니다."
    }

@router.post("/health")
async def report_health(report: NodeHealthReport):
    scheduler.update_health(report)
    return {"status": "ok"}

@router.get("/admin/overview")
async def get_cluster_admin_overview():
    """
    어드민 대시보드: 각 워커 노드의 CPU, RAM, ZRAM, NVMe Swap 가용성 및 차등 과금 배율 실시간 조회
    """
    result = []
    for node_id, node in scheduler.nodes.items():
        h = node.latest_health
        item = {
            "node_id": node.node_id,
            "node_name": node.node_name,
            "ip_address": node.ip_address,
            "hardware_tier": node.hardware_tier,
            "billing_multiplier": node.billing_multiplier,
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
    return {"nodes": result, "total_nodes": len(result)}
