"""
node_scheduler.py - Advanced Node Resource Monitoring & Tier-Aware Scheduler
Supports: Master-as-Worker (Local Container Deployment), Dynamic Multipliers, Hard Threshold Guard
"""
import time
import os
import subprocess
import psutil
from typing import Dict, List, Optional
from fastapi import HTTPException
from app.models.schema import HardwareTier, NodeHealthReport, NodeRegisterRequest

# 기본 하드웨어 티어별 과금 배율
DEFAULT_TIER_MULTIPLIERS: Dict[str, float] = {
    HardwareTier.STANDARD_SSD.value: 1.0,
    HardwareTier.HIGH_NVME.value: 1.3,
    HardwareTier.EXTREME_DEDICATED.value: 1.8,
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
        self.hardware_tier = meta.hardware_tier.value if hasattr(meta.hardware_tier, "value") else str(meta.hardware_tier)
        self.is_master_node = meta.is_master_node
        
        # 어드민 커스텀 배율이 지정되었으면 우선 적용, 아니면 티어 기본 배율 적용
        if meta.custom_multiplier is not None:
            self.billing_multiplier = float(meta.custom_multiplier)
        else:
            self.billing_multiplier = DEFAULT_TIER_MULTIPLIERS.get(self.hardware_tier, 1.0)

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
        print(f"[Scheduler] Registered Node: {node.node_id} ({node.node_name}) Tier: {node.hardware_tier} Multiplier: {node.billing_multiplier}x (MasterNode: {node.is_master_node})")
        return node

    def set_node_multiplier(self, node_id: str, multiplier: float) -> bool:
        """어드민 페이지에서 특정 노드의 과금 배율을 즉시 직접 변경"""
        if node_id in self.nodes:
            self.nodes[node_id].billing_multiplier = round(multiplier, 2)
            print(f"[Scheduler] Node [{node_id}] billing multiplier updated to: {multiplier}x")
            return True
        return False

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

    def register_master_as_local_worker(self):
        """
        Master 노드 자체를 로컬 워커로 스케줄러에 자동 등록 (Master-as-Worker / Single-Node Mode)
        """
        try:
            mem = psutil.virtual_memory()
            cpu_cores = psutil.cpu_count(logical=True) or 4
            total_ram_mb = int(mem.total / (1024 * 1024))
            
            # ZRAM 크기 탐색
            total_zram_mb = 0
            try:
                out = subprocess.check_output(["zramctl", "--json"], text=True)
                import json
                data = json.loads(out)
                for dev in data.get("zramdevices", []):
                    d_str = dev.get("disksize", "0")
                    if d_str.endswith("G"):
                        total_zram_mb += int(float(d_str[:-1]) * 1024)
                    elif d_str.endswith("M"):
                        total_zram_mb += int(float(d_str[:-1]))
            except Exception:
                pass

            master_req = NodeRegisterRequest(
                node_id="master-local",
                node_name="Master Node (Local Container Engine)",
                ip_address="127.0.0.1",
                hardware_tier=HardwareTier.HIGH_NVME,
                custom_multiplier=1.0,
                total_ram_mb=total_ram_mb,
                total_zram_mb=total_zram_mb,
                total_cpu_cores=cpu_cores,
                is_master_node=True
            )
            self.register_node(master_req)
            self.update_master_local_health()
            print("[Scheduler] 🚀 Master Node initialized as active Worker Node (Local Container Support Active).")
        except Exception as e:
            print(f"[Scheduler Warn] Could not initialize Master as local worker: {e}")

    def update_master_local_health(self):
        """Master 노드의 실시간 메트릭 갱신"""
        try:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            cpu_pct = psutil.cpu_percent(interval=None)
            
            # Docker 컨테이너 수
            running_cnt = 0
            try:
                out = subprocess.check_output(["docker", "ps", "-q"], text=True)
                running_cnt = len(out.strip().splitlines()) if out.strip() else 0
            except Exception:
                pass

            health = NodeHealthReport(
                node_id="master-local",
                cpu_usage_pct=cpu_pct,
                ram_used_mb=int(mem.used / (1024 * 1024)),
                ram_total_mb=int(mem.total / (1024 * 1024)),
                zram_used_mb=0,
                zram_total_mb=0,
                nvme_swap_used_mb=int(swap.used / (1024 * 1024)),
                disk_io_wait_pct=0.1,
                running_containers_count=running_cnt
            )
            self.update_health(health)
        except Exception:
            pass

    def select_best_node(self, required_ram_mb: int, preferred_tier: Optional[HardwareTier] = None, preferred_node_id: Optional[str] = None) -> NodeInfo:
        """
        자원 가용성 검증 및 최적 노드 스케줄링 (Least-Loaded Score)
        - preferred_node_id (예: master-local) 요청 시 해당 노드 우선 할당
        - RAM 90%, ZRAM 80% 초과 노드 배제
        """
        # 1. 특정 노드 지정 요청 처리
        if preferred_node_id and preferred_node_id in self.nodes:
            target = self.nodes[preferred_node_id]
            if target.latest_health:
                avail_ram = target.latest_health.ram_total_mb - target.latest_health.ram_used_mb
                if avail_ram >= required_ram_mb:
                    return target

        now = time.time()
        available_candidates: List[NodeInfo] = []

        for node_id, node in self.nodes.items():
            # Master 로컬 노드는 자체 생존 처리
            if node.is_master_node:
                self.update_master_local_health()

            # 하트비트 생존 여부 (30초)
            if not node.is_master_node and (now - node.last_heartbeat > 30):
                continue

            health = node.latest_health
            if not health:
                continue

            # Hard limits 검증
            ram_ratio = health.ram_used_mb / max(health.ram_total_mb, 1)
            zram_ratio = health.zram_used_mb / max(health.zram_total_mb, 1) if health.zram_total_mb > 0 else 0.0

            if ram_ratio >= MAX_RAM_USAGE_RATIO:
                print(f"[Scheduler] Node {node_id} skipped: RAM limit reached ({ram_ratio*100:.1f}%)")
                continue

            if zram_ratio >= MAX_ZRAM_USAGE_RATIO:
                print(f"[Scheduler] Node {node_id} skipped: ZRAM limit reached ({zram_ratio*100:.1f}%)")
                continue

            if health.cpu_usage_pct >= MAX_CPU_USAGE_PCT:
                print(f"[Scheduler] Node {node_id} skipped: CPU overloaded ({health.cpu_usage_pct:.1f}%)")
                continue

            available_ram = health.ram_total_mb - health.ram_used_mb
            if available_ram < required_ram_mb:
                continue

            available_candidates.append(node)

        if not available_candidates:
            # Fallback: 만약 Master-local 노드가 존재한다면 강제 할당 시도
            if "master-local" in self.nodes:
                return self.nodes["master-local"]

            raise HTTPException(
                status_code=503,
                detail="클러스터 내 가용 자원이 충분한 노드가 없습니다. 잠시 후 다시 시도하십시오."
            )

        # 티어 선호도 매칭
        if preferred_tier:
            tier_val = preferred_tier.value if hasattr(preferred_tier, "value") else str(preferred_tier)
            tier_matched = [n for n in available_candidates if n.hardware_tier == tier_val]
            if tier_matched:
                available_candidates = tier_matched

        # Least-Loaded 스코어링
        def score(n: NodeInfo) -> float:
            h = n.latest_health
            avail_ram = h.ram_total_mb - h.ram_used_mb
            cpu_free = 100.0 - h.cpu_usage_pct
            return (avail_ram * 0.7) + (cpu_free * 30.0)

        best_node = max(available_candidates, key=score)
        return best_node

scheduler = NodeScheduler()
