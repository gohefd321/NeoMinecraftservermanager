"""
node_scheduler.py - Advanced Node Resource Monitoring, Dynamic Custom Tiers & Swap Configuration
Supports:
- Master-as-Worker Local Container Support
- Dynamic Custom Tiers (Grouping Nodes & Custom Multipliers)
- Global Memory & Swap Ratio (ZRAM/NVMe) Configuration
- Tier-Aware Node Scheduler & Overload Guard
"""
import time
import os
import subprocess
import psutil
from typing import Dict, List, Optional
from datetime import datetime
from fastapi import HTTPException
from app.models.schema import (
    HardwareTier, NodeHealthReport, NodeRegisterRequest,
    CustomTierCreate, CustomTierResponse, SwapConfigModel
)

# 기본 하드웨어 티어별 과금 배율
DEFAULT_TIER_MULTIPLIERS: Dict[str, float] = {
    "standard_ssd": 1.0,
    "high_nvme": 1.3,
    "extreme_dedicated": 1.8,
}

MAX_RAM_USAGE_RATIO = 0.90
MAX_ZRAM_USAGE_RATIO = 0.80
MAX_CPU_USAGE_PCT = 95.0


def get_safe_zram_total_mb() -> int:
    """ZRAM 총 용량 감지 (zramctl 에러 방어 및 /sys, /proc/swaps 파싱)"""
    total_mb = 0
    try:
        sys_zram = "/sys/block"
        if os.path.exists(sys_zram):
            for dev in os.listdir(sys_zram):
                if dev.startswith("zram"):
                    size_file = os.path.join(sys_zram, dev, "disksize")
                    if os.path.exists(size_file):
                        with open(size_file, "r") as f:
                            bytes_val = int(f.read().strip())
                            total_mb += int(bytes_val / (1024 * 1024))
        if total_mb > 0:
            return total_mb
    except Exception:
        pass

    try:
        out = subprocess.check_output(["zramctl", "-b", "--noheadings", "-o", "DISKSIZE"], text=True, stderr=subprocess.DEVNULL)
        for line in out.strip().splitlines():
            line = line.strip()
            if line.isdigit():
                total_mb += int(int(line) / (1024 * 1024))
    except Exception:
        pass

    return total_mb


class NodeInfo:
    def __init__(self, meta: NodeRegisterRequest):
        self.node_id = meta.node_id
        self.node_name = meta.node_name
        self.ip_address = meta.ip_address
        self.hardware_tier = meta.hardware_tier if isinstance(meta.hardware_tier, str) else meta.hardware_tier.value
        self.is_master_node = meta.is_master_node
        
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
        
        # 커스텀 티어 저장소 (기본 3대 빌트인 티어 포함)
        self.custom_tiers: Dict[str, CustomTierResponse] = {
            "standard_ssd": CustomTierResponse(
                tier_id="standard_ssd",
                name="표준 SSD (Standard)",
                multiplier=1.0,
                description="일반적인 엔트리/생존 서버를 위한 경제적인 표준 스토리지",
                assigned_node_ids=["master-local"],
                is_builtin=True
            ),
            "high_nvme": CustomTierResponse(
                tier_id="high_nvme",
                name="초고속 NVMe (High Speed)",
                multiplier=1.3,
                description="Gen4/Gen5 NVMe SSD 기반 대규모 엔티티 및 빠른 청크 로딩 지원",
                assigned_node_ids=["master-local"],
                is_builtin=True
            ),
            "extreme_dedicated": CustomTierResponse(
                tier_id="extreme_dedicated",
                name="단독 전용 (Extreme Dedicated)",
                multiplier=1.8,
                description="CPU 단독 코어 및 ZRAM 격리 샌드박스를 제공하는 하이엔드 티어",
                assigned_node_ids=["master-local"],
                is_builtin=True
            )
        }

        # 글로벌 스왑 및 ZRAM 환경설정
        self.swap_config: SwapConfigModel = SwapConfigModel(
            swap_ratio=1.5,
            zram_compression_algo="zstd",
            swappiness=60,
            enable_generational_zgc=True
        )

    # -----------------------------------------------------------------------
    # 커스텀 티어 생성, 조회, 삭제 (Node Grouping)
    # -----------------------------------------------------------------------
    def get_all_tiers(self) -> List[CustomTierResponse]:
        return list(self.custom_tiers.values())

    def create_custom_tier(self, payload: CustomTierCreate) -> CustomTierResponse:
        tier_obj = CustomTierResponse(
            tier_id=payload.tier_id,
            name=payload.name,
            multiplier=payload.multiplier,
            description=payload.description,
            assigned_node_ids=payload.assigned_node_ids,
            is_builtin=False,
            created_at=datetime.utcnow()
        )
        self.custom_tiers[payload.tier_id] = tier_obj

        # 할당된 노드들의 기본 티어 및 배율 동기화
        for node_id in payload.assigned_node_ids:
            if node_id in self.nodes:
                self.nodes[node_id].hardware_tier = payload.tier_id
                self.nodes[node_id].billing_multiplier = payload.multiplier

        print(f"[Scheduler] Custom Tier Created: [{payload.tier_id}] {payload.name} (Multiplier: {payload.multiplier}x, Nodes: {payload.assigned_node_ids})")
        return tier_obj

    def delete_custom_tier(self, tier_id: str) -> bool:
        if tier_id in self.custom_tiers:
            if self.custom_tiers[tier_id].is_builtin:
                raise HTTPException(status_code=400, detail="기본 내장 티어는 삭제할 수 없습니다.")
            del self.custom_tiers[tier_id]
            return True
        return False

    # -----------------------------------------------------------------------
    # 스왑 비율 및 ZRAM 설정
    # -----------------------------------------------------------------------
    def get_swap_config(self) -> SwapConfigModel:
        return self.swap_config

    def update_swap_config(self, cfg: SwapConfigModel) -> SwapConfigModel:
        self.swap_config = cfg
        print(f"[Scheduler] Global Swap Config Updated: SwapRatio={cfg.swap_ratio}x, Algo={cfg.zram_compression_algo}, Swappiness={cfg.swappiness}")
        return self.swap_config

    # -----------------------------------------------------------------------
    # 노드 등록 및 상태 모니터링
    # -----------------------------------------------------------------------
    def register_node(self, req: NodeRegisterRequest) -> NodeInfo:
        node = NodeInfo(req)
        self.nodes[req.node_id] = node
        print(f"[Scheduler] Registered Node: {node.node_id} ({node.node_name}) Tier: {node.hardware_tier} Multiplier: {node.billing_multiplier}x (MasterNode: {node.is_master_node})")
        return node

    def set_node_multiplier(self, node_id: str, multiplier: float) -> bool:
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
        try:
            mem = psutil.virtual_memory()
            cpu_cores = psutil.cpu_count(logical=True) or 4
            total_ram_mb = int(mem.total / (1024 * 1024))
            total_zram_mb = get_safe_zram_total_mb()

            master_req = NodeRegisterRequest(
                node_id="master-local",
                node_name="Master Node (Local Container Engine)",
                ip_address="127.0.0.1",
                hardware_tier="high_nvme",
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
        try:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            cpu_pct = psutil.cpu_percent(interval=None)
            
            running_cnt = 0
            try:
                out = subprocess.check_output(["docker", "ps", "-q"], text=True, stderr=subprocess.DEVNULL)
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

    # -----------------------------------------------------------------------
    # 지능형 노드 스케줄러 (커스텀 티어 지원)
    # -----------------------------------------------------------------------
    def select_best_node(self, required_ram_mb: int, preferred_tier: Optional[str] = None, preferred_node_id: Optional[str] = None) -> NodeInfo:
        if preferred_node_id and preferred_node_id in self.nodes:
            target = self.nodes[preferred_node_id]
            if target.latest_health:
                avail_ram = target.latest_health.ram_total_mb - target.latest_health.ram_used_mb
                if avail_ram >= required_ram_mb:
                    return target

        now = time.time()
        available_candidates: List[NodeInfo] = []

        for node_id, node in self.nodes.items():
            if node.is_master_node:
                self.update_master_local_health()

            if not node.is_master_node and (now - node.last_heartbeat > 30):
                continue

            health = node.latest_health
            if not health:
                continue

            ram_ratio = health.ram_used_mb / max(health.ram_total_mb, 1)
            zram_ratio = health.zram_used_mb / max(health.zram_total_mb, 1) if health.zram_total_mb > 0 else 0.0

            if ram_ratio >= MAX_RAM_USAGE_RATIO:
                continue
            if zram_ratio >= MAX_ZRAM_USAGE_RATIO:
                continue
            if health.cpu_usage_pct >= MAX_CPU_USAGE_PCT:
                continue

            available_ram = health.ram_total_mb - health.ram_used_mb
            if available_ram < required_ram_mb:
                continue

            available_candidates.append(node)

        if not available_candidates:
            if "master-local" in self.nodes:
                return self.nodes["master-local"]

            raise HTTPException(
                status_code=503,
                detail="클러스터 내 가용 자원이 충분한 노드가 없습니다. 잠시 후 다시 시도하십시오."
            )

        if preferred_tier and preferred_tier in self.custom_tiers:
            assigned_nodes = self.custom_tiers[preferred_tier].assigned_node_ids
            if assigned_nodes:
                tier_matched = [n for n in available_candidates if n.node_id in assigned_nodes]
                if tier_matched:
                    available_candidates = tier_matched

        def score(n: NodeInfo) -> float:
            h = n.latest_health
            avail_ram = h.ram_total_mb - h.ram_used_mb
            cpu_free = 100.0 - h.cpu_usage_pct
            return (avail_ram * 0.7) + (cpu_free * 30.0)

        best_node = max(available_candidates, key=score)
        return best_node

scheduler = NodeScheduler()
