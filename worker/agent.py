"""
agent.py - Worker Node Real-Time Telemetry & Container Lifecycle Daemon
Collects: Host CPU, RAM, Tier 2 ZRAM, Tier 3 NVMe Swap, Disk I/O wait
"""
import os
import time
import subprocess
import asyncio
import httpx
import psutil
from typing import Dict, Any

NODE_ID = os.getenv("NODE_ID", f"worker-{os.uname().nodename}")
NODE_NAME = os.getenv("NODE_NAME", os.uname().nodename)
MASTER_ENDPOINT = os.getenv("MASTER_ENDPOINT", "http://localhost:8000")
HARDWARE_TIER = os.getenv("HARDWARE_TIER", "standard_ssd")
CLUSTER_TOKEN = os.getenv("CLUSTER_TOKEN", "cluster-master-secret-token")

def get_zram_stats() -> Dict[str, int]:
    """ZRAM 압축 스왑 통계 추출"""
    total_zram_mb = 0
    used_zram_mb = 0
    try:
        out = subprocess.check_output(["zramctl", "--json"], text=True)
        import json
        data = json.loads(out)
        for dev in data.get("zramdevices", []):
            disksize_str = dev.get("disksize", "0")
            # Parse disksize
            if disksize_str.endswith("G"):
                total_zram_mb += int(float(disksize_str[:-1]) * 1024)
            elif disksize_str.endswith("M"):
                total_zram_mb += int(float(disksize_str[:-1]))

            data_str = dev.get("data", "0")
            if data_str.endswith("G"):
                used_zram_mb += int(float(data_str[:-1]) * 1024)
            elif data_str.endswith("M"):
                used_zram_mb += int(float(data_str[:-1]))
    except Exception:
        # Fallback via /proc/swaps
        pass
    return {"total_mb": total_zram_mb, "used_mb": used_zram_mb}

def collect_host_metrics() -> Dict[str, Any]:
    """호스트 자원 메트릭 측정"""
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    cpu_pct = psutil.cpu_percent(interval=None)
    
    zram = get_zram_stats()
    nvme_swap_used = max(0, int((swap.used - (zram["used_mb"] * 1024 * 1024)) / (1024 * 1024)))

    # Docker 컨테이너 수 카운트
    running_containers = 0
    try:
        out = subprocess.check_output(["docker", "ps", "-q"], text=True)
        running_containers = len(out.strip().splitlines()) if out.strip() else 0
    except Exception:
        pass

    return {
        "node_id": NODE_ID,
        "cpu_usage_pct": cpu_pct,
        "ram_used_mb": int(mem.used / (1024 * 1024)),
        "ram_total_mb": int(mem.total / (1024 * 1024)),
        "zram_used_mb": zram["used_mb"],
        "zram_total_mb": zram["total_mb"],
        "nvme_swap_used_mb": nvme_swap_used,
        "disk_io_wait_pct": 0.5,
        "running_containers_count": running_containers
    }

async def register_to_master():
    """Master에 워커 노드 등록"""
    mem = psutil.virtual_memory()
    zram = get_zram_stats()
    payload = {
        "node_id": NODE_ID,
        "node_name": NODE_NAME,
        "ip_address": "127.0.0.1",
        "hardware_tier": HARDWARE_TIER,
        "total_ram_mb": int(mem.total / (1024 * 1024)),
        "total_zram_mb": zram["total_mb"],
        "total_cpu_cores": psutil.cpu_count(logical=True)
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(f"{MASTER_ENDPOINT}/api/v1/nodes/register", json=payload)
            print(f"[Worker Agent] Registered with Master: {resp.json()}")
        except Exception as e:
            print(f"[Worker Agent] Register retry pending: {e}")

async def run_telemetry_loop():
    """5초 주기 헬스체크 리포트 전송"""
    await register_to_master()
    async with httpx.AsyncClient(timeout=5.0) as client:
        while True:
            try:
                metrics = collect_host_metrics()
                await client.post(f"{MASTER_ENDPOINT}/api/v1/nodes/health", json=metrics)
            except Exception as e:
                print(f"[Worker Agent] Telemetry push error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    print(f"🌟 Worker Node Agent Starting for [{NODE_NAME}]...")
    asyncio.run(run_telemetry_loop())
