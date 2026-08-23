"""
test_platform.py - Platform Security, Scheduler, Dynamic Billing & Master-as-Worker Tests
"""
import sys
import os
import asyncio
from pathlib import Path
import pytest
from fastapi import HTTPException

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.security import sanitize_rcon_command, validate_url_safety, sanitize_relative_path
from app.services.node_scheduler import NodeScheduler, HardwareTier, scheduler
from app.models.schema import NodeRegisterRequest, NodeHealthReport, BillingRateConfig
from app.services.billing_engine import BillingEngine, billing_engine
from app.services.modpack_importer import ModpackImporter

def test_rcon_command_sanitization():
    """RCON 명령어 살균 및 인젝션 방어 테스트"""
    assert sanitize_rcon_command("say Hello World") == "say Hello World"
    assert sanitize_rcon_command("/tp Player1 100 64 200") == "tp Player1 100 64 200"
    assert sanitize_rcon_command("save-all") == "save-all"

    with pytest.raises(HTTPException):
        sanitize_rcon_command("say hello; rm -rf /")

    with pytest.raises(HTTPException):
        sanitize_rcon_command("say hello \n stop")

    with pytest.raises(HTTPException):
        sanitize_rcon_command("say `cat /etc/passwd`")

    with pytest.raises(HTTPException):
        sanitize_rcon_command("execute run custom_unknown_command")

def test_ssrf_url_validation():
    """SSRF 방어 테스트"""
    assert validate_url_safety("https://cdn.modrinth.com/data/xyz/file.jar") == "https://cdn.modrinth.com/data/xyz/file.jar"
    assert validate_url_safety("http://edge.forgecdn.net/files/123/mod.jar") == "http://edge.forgecdn.net/files/123/mod.jar"

    with pytest.raises(HTTPException):
        validate_url_safety("http://localhost:8080/secret")

    with pytest.raises(HTTPException):
        validate_url_safety("http://127.0.0.1:6379")

    with pytest.raises(HTTPException):
        validate_url_safety("http://169.254.169.254/latest/meta-data")

def test_dynamic_admin_billing_rate_adjustment():
    """어드민 동적 과금 요율(기본비, 청크, 플레이어, 티어 배율) 변경 테스트"""
    engine = BillingEngine()
    
    # 1. 초기 기본 요율 확인
    # 100 chunks, 5 players, standard node (1.0x) -> 0.50 + 100*0.001 (0.1) + 5*0.1 (0.5) = 1.10 KRW
    assert engine.compute_minute_cost(chunks=100, players=5, node_id="test-std-node") == 1.10

    # 2. 어드민이 청크당 요율을 0.005원으로 인상, 플레이어당 요율을 0.20원으로 인상
    new_rates = BillingRateConfig(
        base_container_per_min=1.00, # 기본비 인상
        per_chunk_rate=0.0050,       # 청크당 인상
        per_player_rate=0.2000,      # 플레이어당 인상
        tier_multipliers={"standard_ssd": 1.0, "high_nvme": 1.5, "extreme_dedicated": 2.0}
    )
    asyncio.run(engine.update_billing_rates(new_rates))

    # 3. 새로운 요율 적용 검증: 1.00 + 100*0.005 (0.5) + 5*0.20 (1.0) = 2.50 KRW
    assert engine.compute_minute_cost(chunks=100, players=5, node_id="test-std-node") == 2.50

def test_master_as_worker_local_container_support():
    """Master 노드 자체 로컬 워커 등록 및 스케줄링 테스트"""
    test_sched = NodeScheduler()
    test_sched.register_master_as_local_worker()

    assert "master-local" in test_sched.nodes
    master_node = test_sched.nodes["master-local"]
    assert master_node.is_master_node is True
    assert master_node.total_ram_mb > 0

    # Master 노드를 선호 노드로 지정하여 스케줄링 요청 시 정상 할당
    selected = test_sched.select_best_node(required_ram_mb=2048, preferred_node_id="master-local")
    assert selected.node_id == "master-local"

def test_custom_node_multiplier_override():
    """어드민 페이지에서 특정 노드의 배율만 개별 변경하는 기능 테스트"""
    test_sched = NodeScheduler()
    test_sched.register_node(NodeRegisterRequest(
        node_id="worker-seoul-01",
        node_name="Seoul NVMe Worker",
        ip_address="10.0.0.20",
        hardware_tier=HardwareTier.HIGH_NVME,
        custom_multiplier=1.3,
        total_ram_mb=32768,
        total_zram_mb=16384,
        total_cpu_cores=16
    ))

    assert test_sched.get_tier_multiplier("worker-seoul-01") == 1.3

    # 어드민이 해당 노드를 1.7x 배율로 즉시 수정
    test_sched.set_node_multiplier("worker-seoul-01", 1.7)
    assert test_sched.get_tier_multiplier("worker-seoul-01") == 1.7

def test_client_only_mod_filter():
    """클라이언트 전용 모드 블랙리스트 필터링 테스트"""
    importer = ModpackImporter(target_server_dir=Path("/tmp/test_mc_srv"))
    assert importer._is_client_only_mod("Iris-Shaders-1.20.4.jar") is True
    assert importer._is_client_only_mod("xaeros-minimap-v23.jar") is True
    assert importer._is_client_only_mod("sodium-fabric-mc1.20.4.jar") is True
    assert importer._is_client_only_mod("fabric-api-0.92.0.jar") is False
