"""
node_scheduler.py - Advanced Node Resource Monitoring & Tier-Aware Scheduler
"""
import time
from typing import Dict, List, Optional
from fastapi import HTTPException
from app.models.schema import HardwareTier, NodeHealthReport, NodeRegisterRequest

# 하드웨어 티어별 과금 배율
TIER_MULTIPLIERS: Dict[HardwareTier, float] = {
    HardwareTier.STANDARD_SSD: 1.0,
    HardwareTier.HIGH_NVME: 1.3,
    HardwareTier.EXTREME_DEDICATED: 1.8,
}

# 스케줄링 차단 임계치 (Hard Limits)
MAX_RAM_USAGE_RATIO = 0.90   # 물리 RAM 90% 초과 시 차단
MAX_ZRAM_USAGE_RATIO = 0.80  # ZRAM 80% 초과 시 차단
MAX_CPU_USAGE_PCT = 95.0     # CPU 95% 초과 시 차단


class NodeInfo:
    def __init__(self, meta: NodeRegisterRequest):
        self.node_id = meta.node_id
        self.node_name = meta.node_name
        self.ip_address = meta.ip_address
        self.hardware_tier = meta.hardware_tier
        self.billing_multiplier = TIER_MULTIPLIERS.get(meta.hardware_tier, 1.0)
        self.total_ram_mb = meta.total_ram_mb
        self.total_zram_mb = meta.total_zram_mb
        self.total_cpu_cores = meta.total_cpu_cores
        self.latest_health: Optional[NodeHealthReport] = None
        self.last_heartbeat = time.time()


class NodeScheduler:
    def __init__(self):
        self.nodes: Dict[str, NodeInfo] = {}

    def register_node(self, req: NodeRegisterRequest) -> NodeInfo:
        node = NodeInfo(req)
        self.nodes[req.node_id] = node
        print(f"[Scheduler] Registered Node: {node.node_id} ({node.node_name}) Tier: {node.hardware_tier} (Multiplier: {node.billing_multiplier}x)")
        return node

    def update_health(self, health: NodeHealthReport):
        if health.node_id in self.nodes:
            node = self.nodes[health.node_id]
            node.latest_health = health
            node.last_heartbeat = time.time()

    def get_tier_multiplier(self, node_id: str) -> float:
        node = self.nodes.get(node_id)
        if node:
            return node.billing_multiplier
        return 1.0

    def select_best_node(self, required_ram_mb: int, preferred_tier: Optional[HardwareTier] = None) -> NodeInfo:
        """
        자원 가용성 검증 및 최적의 워커 노드 스케줄링 (Least-Loaded Score)
        1. 최근 30초 이내 하트비트가 있는 노드만 필터링
        2. RAM 90% 초과, ZRAM 80% 초과 노드 배제 (OOM/Swap 폭주 방지)
        3. 선호하는 하드웨어 티어 우선 매칭
        4. (가용 RAM + 남은 CPU 여유분) 점수가 가장 높은 노드 선택
        """
        now = time.time()
        available_candidates: List[NodeInfo] = []

        for node_id, node in self.nodes.items():
            # 1. 하트비트 생존 여부 (30초)
            if now - node.last_heartbeat > 30:
                continue

            health = node.latest_health
            if not health:
                continue

            # 2. 임계치 검증 (Hard limits)
            ram_ratio = health.ram_used_mb / max(health.ram_total_mb, 1)
            zram_ratio = health.zram_used_mb / max(health.zram_total_mb, 1) if health.zram_total_mb > 0 else 0.0

            if ram_ratio >= MAX_RAM_USAGE_RATIO:
                print(f"[Scheduler] Node {node_id} skipped: RAM threshold reached ({ram_ratio*100:.1f}%)")
                continue

            if zram_ratio >= MAX_ZRAM_USAGE_RATIO:
                print(f"[Scheduler] Node {node_id} skipped: ZRAM threshold reached ({zram_ratio*100:.1f}%)")
                continue

            if health.cpu_usage_pct >= MAX_CPU_USAGE_PCT:
                print(f"[Scheduler] Node {node_id} skipped: CPU overload ({health.cpu_usage_pct:.1f}%)")
                continue

            # 남은 물리 RAM이 요구량 이상인지 확인
            available_ram = health.ram_total_mb - health.ram_used_mb
            if available_ram < required_ram_mb:
                continue

            available_candidates.append(node)

        if not available_candidates:
            raise HTTPException(
                status_code=503,
                detail="클러스터 내 가용 자원이 충분한 워커 노드가 없습니다. 잠시 후 다시 시도하십시오."
            )

        # 티어 선호도 필터링
        if preferred_tier:
            tier_matched = [n for n in available_candidates if n.hardware_tier == preferred_tier]
            if tier_matched:
                available_candidates = tier_matched

        # Least-Loaded 스코어링: 가용 RAM이 많고 CPU 사용률이 낮은 노드 선택
        def score(n: NodeInfo) -> float:
            h = n.latest_health
            avail_ram = h.ram_total_mb - h.ram_used_mb
            cpu_free = 100.0 - h.cpu_usage_pct
            return (avail_ram * 0.7) + (cpu_free * 30.0)

        best_node = max(available_candidates, key=score)
        return best_node

scheduler = NodeScheduler()
