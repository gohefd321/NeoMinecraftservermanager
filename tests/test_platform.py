"""
test_platform.py - Platform Security, Scheduler & Billing Validation Tests
"""
import sys
import os
from pathlib import Path
import pytest
from fastapi import HTTPException

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.security import sanitize_rcon_command, validate_url_safety, sanitize_relative_path
from app.services.node_scheduler import NodeScheduler, HardwareTier, scheduler
from app.models.schema import NodeRegisterRequest, NodeHealthReport
from app.services.billing_engine import BillingEngine
from app.services.modpack_importer import ModpackImporter

def test_rcon_command_sanitization():
    """RCON 명령어 살균 및 인젝션 방어 테스트"""
    # 1. 정상 명령어 허용
    assert sanitize_rcon_command("say Hello World") == "say Hello World"
    assert sanitize_rcon_command("/tp Player1 100 64 200") == "tp Player1 100 64 200"
    assert sanitize_rcon_command("save-all") == "save-all"

    # 2. 쉘 메타문자 및 CRLF 인젝션 차단
    with pytest.raises(HTTPException):
        sanitize_rcon_command("say hello; rm -rf /")

    with pytest.raises(HTTPException):
        sanitize_rcon_command("say hello \n stop")

    with pytest.raises(HTTPException):
        sanitize_rcon_command("say `cat /etc/passwd`")

    # 3. 비인가 위험 명령어 차단
    with pytest.raises(HTTPException):
        sanitize_rcon_command("execute run custom_unknown_command")

def test_ssrf_url_validation():
    """SSRF 방어 테스트"""
    # 1. 안전한 공인 URL 허용
    assert validate_url_safety("https://cdn.modrinth.com/data/xyz/file.jar") == "https://cdn.modrinth.com/data/xyz/file.jar"
    assert validate_url_safety("http://edge.forgecdn.net/files/123/mod.jar") == "http://edge.forgecdn.net/files/123/mod.jar"

    # 2. 로컬 루프백 차단
    with pytest.raises(HTTPException):
        validate_url_safety("http://localhost:8080/secret")

    with pytest.raises(HTTPException):
        validate_url_safety("http://127.0.0.1:6379")

    # 3. 클라우드 메타데이터 및 사설망 차단
    with pytest.raises(HTTPException):
        validate_url_safety("http://169.254.169.254/latest/meta-data")

    with pytest.raises(HTTPException):
        validate_url_safety("http://192.168.1.50/admin")

    with pytest.raises(HTTPException):
        validate_url_safety("http://10.0.0.1/flag")

def test_path_traversal_sanitization():
    """Path Traversal (Zip Slip) 방어 테스트"""
    assert sanitize_relative_path("mods/fabric-api.jar") == "mods/fabric-api.jar"

    with pytest.raises(HTTPException):
        sanitize_relative_path("../../../etc/shadow")

    with pytest.raises(HTTPException):
        sanitize_relative_path("/etc/passwd")

def test_node_scheduler_and_tiered_multipliers():
    """스케줄러 자원 가용성 및 차등 배율 테스트"""
    test_sched = NodeScheduler()

    # 노드 1: 표준 SSD (1.0x) - 정상 여유
    n1_req = NodeRegisterRequest(
        node_id="node-ssd-01",
        node_name="SSD Standard Node",
        ip_address="10.0.0.10",
        hardware_tier=HardwareTier.STANDARD_SSD,
        total_ram_mb=16384,
        total_zram_mb=8192,
        total_cpu_cores=8
    )
    test_sched.register_node(n1_req)
    test_sched.update_health(NodeHealthReport(
        node_id="node-ssd-01",
        cpu_usage_pct=20.0,
        ram_used_mb=4096,
        ram_total_mb=16384,
        zram_used_mb=500,
        zram_total_mb=8192,
        nvme_swap_used_mb=0,
        disk_io_wait_pct=0.1,
        running_containers_count=2
    ))

    # 노드 2: 고성능 NVMe (1.3x) - 과부하(RAM 92% 임계치 도달)
    n2_req = NodeRegisterRequest(
        node_id="node-nvme-02",
        node_name="NVMe Overloaded Node",
        ip_address="10.0.0.11",
        hardware_tier=HardwareTier.HIGH_NVME,
        total_ram_mb=16384,
        total_zram_mb=8192,
        total_cpu_cores=8
    )
    test_sched.register_node(n2_req)
    test_sched.update_health(NodeHealthReport(
        node_id="node-nvme-02",
        cpu_usage_pct=50.0,
        ram_used_mb=15200, # 92.7% used (>=90%)
        ram_total_mb=16384,
        zram_used_mb=2000,
        zram_total_mb=8192,
        nvme_swap_used_mb=100,
        disk_io_wait_pct=0.2,
        running_containers_count=6
    ))

    # 과부하 노드는 배제되고 여유가 있는 n1이 선정되어야 함
    selected = test_sched.select_best_node(required_ram_mb=4096)
    assert selected.node_id == "node-ssd-01"
    assert test_sched.get_tier_multiplier("node-ssd-01") == 1.0
    assert test_sched.get_tier_multiplier("node-nvme-02") == 1.3

def test_billing_engine_cost_calculation():
    """1분 단위 차등 과금 연산 테스트"""
    # 전역 scheduler에 노드 등록
    scheduler.register_node(NodeRegisterRequest(
        node_id="global-ssd-01",
        node_name="Global SSD Node",
        ip_address="127.0.0.1",
        hardware_tier=HardwareTier.STANDARD_SSD,
        total_ram_mb=8192,
        total_zram_mb=4096,
        total_cpu_cores=4
    ))
    scheduler.register_node(NodeRegisterRequest(
        node_id="global-nvme-02",
        node_name="Global NVMe Node",
        ip_address="127.0.0.1",
        hardware_tier=HardwareTier.HIGH_NVME,
        total_ram_mb=8192,
        total_zram_mb=4096,
        total_cpu_cores=4
    ))

    engine = BillingEngine()
    cost_std = engine.compute_minute_cost(chunks=100, players=5, node_id="global-ssd-01")
    # Base 0.50 + 100*0.001 (0.1) + 5*0.1 (0.5) = 1.10 KRW
    assert cost_std == 1.10

    cost_nvme = engine.compute_minute_cost(chunks=100, players=5, node_id="global-nvme-02")
    # 1.10 * 1.3 = 1.43 KRW
    assert cost_nvme == 1.43

def test_client_only_mod_filter():
    """클라이언트 전용 모드 블랙리스트 필터링 테스트"""
    importer = ModpackImporter(target_server_dir=Path("/tmp/test_mc_srv"))
    assert importer._is_client_only_mod("Iris-Shaders-1.20.4.jar") is True
    assert importer._is_client_only_mod("xaeros-minimap-v23.jar") is True
    assert importer._is_client_only_mod("sodium-fabric-mc1.20.4.jar") is True
    assert importer._is_client_only_mod("fabric-api-0.92.0.jar") is False
    assert importer._is_client_only_mod("Lithium-1.20.4.jar") is False
