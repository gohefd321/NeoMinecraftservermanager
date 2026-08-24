"""
cpu_scheduler.py - Intelligent Least-Used Core Affinity & Graceful Clamping Scheduler
Features:
1. Least-Allocated Core Priority: Assigns CPU cores with lowest allocation frequency to prevent core overlapping & cache thrashing.
2. Auto Core Clamping: Automatically clamps requested vCPUs to the node's maximum available cores if requested cores exceed capacity.
3. Multi-worker sync & dynamic core usage accounting.
"""
import os
import psutil
from typing import Dict, List, Tuple, Any

class CpuCoreScheduler:
    def __init__(self):
        self.total_cores: int = os.cpu_count() or psutil.cpu_count(logical=True) or 4
        # 코어 번호(0 ~ total_cores-1)별 현재 할당된 컨테이너 수
        self.core_usage: Dict[int, int] = {i: 0 for i in range(self.total_cores)}

    def get_node_max_cores(self) -> int:
        return self.total_cores

    def allocate_cores(self, requested_cores: int) -> Tuple[str, int, bool, int]:
        """
        코어 할당 함수
        Returns:
            cpuset_str (str): 예 "0,2,3"
            actual_cores (int): 실제 할당된 코어 수
            was_clamped (bool): 노드 최대 코어 수 초과로 자동 축소되었는지 여부
            max_cores (int): 노드 전체 코어 수
        """
        was_clamped = False
        actual_cores = requested_cores

        # 1. 노드 용량 초과 시 최대 vCPU 수로 자동 클램핑
        if actual_cores > self.total_cores:
            actual_cores = self.total_cores
            was_clamped = True
        elif actual_cores < 1:
            actual_cores = 1

        # 2. 사용 빈도수가 가장 낮은 코어부터 오름차순 정렬 (Least-Used First)
        sorted_cores = sorted(self.core_usage.items(), key=lambda item: (item[1], item[0]))
        
        selected_core_ids = [core_id for core_id, _ in sorted_cores[:actual_cores]]
        selected_core_ids.sort()

        # 3. 점유 카운트 증가
        for cid in selected_core_ids:
            self.core_usage[cid] += 1

        cpuset_str = ",".join(str(cid) for cid in selected_core_ids)
        return cpuset_str, actual_cores, was_clamped, self.total_cores

    def release_cores(self, cpuset_str: str):
        """서버 정지/삭제 시 할당했던 코어의 점유 카운트 복구"""
        if not cpuset_str:
            return
        try:
            parts = cpuset_str.split(",")
            for p in parts:
                cid = int(p.strip())
                if cid in self.core_usage:
                    self.core_usage[cid] = max(0, self.core_usage[cid] - 1)
        except Exception as e:
            print(f"[CpuScheduler Release Warning] {e}")

    def get_core_distribution(self) -> Dict[str, Any]:
        """어드민 및 모니터링용 전체 코어 점유 현황"""
        return {
            "total_cores": self.total_cores,
            "core_usage": self.core_usage
        }

cpu_scheduler = CpuCoreScheduler()
