"""
schema.py - Pydantic Request/Response Models and Enums (Pydantic v2 Compatible)
Supported Minecraft Versions: Exactly 3 Versions ("1.20.4", "1.20.2", "1.16.5")
Supported Presets: Creative Builder, Survival SMP, Custom Advanced
"""
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class HardwareTier(str, Enum):
    STANDARD_SSD = "standard_ssd"           # 1.0x 기본 배율
    HIGH_NVME = "high_nvme"                 # 1.3x 기본 배율
    EXTREME_DEDICATED = "extreme_dedicated" # 1.8x 기본 배율

class ServerType(str, Enum):
    PAPER = "PAPER"
    FABRIC = "FABRIC"
    NEOFORGE = "NEOFORGE"
    PURPUR = "PURPUR"

class ServerPreset(str, Enum):
    BUILDER_FLAT = "BUILDER_FLAT"       # 건축 서버 (평지, 월드에딧, 최적화 플러그인)
    SURVIVAL_SMP = "SURVIVAL_SMP"       # 야생 서버 (야생맵, TPA/Home 플러그인, 최적화 플러그인)
    ADVANCED_CUSTOM = "ADVANCED_CUSTOM" # 고급 사용자 맞춤 개설

class SupportedMCVersion(str, Enum):
    V_1_20_4 = "1.20.4"
    V_1_20_2 = "1.20.2"
    V_1_16_5 = "1.16.5"

class ServerStatus(str, Enum):
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    SUSPENDED = "SUSPENDED"
    PROVISIONING = "PROVISIONING"
    ERROR = "ERROR"

class TicketStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"

# ---------------------------------------------------------------------------
# Dynamic Billing Configuration
# ---------------------------------------------------------------------------
class BillingRateConfig(BaseModel):
    base_container_per_min: float = Field(
        default=0.50, ge=0.0, le=100.0,
        description="컨테이너 분당 기본 유지비용 (KRW)"
    )
    per_chunk_rate: float = Field(
        default=0.0010, ge=0.0, le=1.0,
        description="로드된 청크 1개당 분당 요율 (KRW)"
    )
    per_player_rate: float = Field(
        default=0.1000, ge=0.0, le=10.0,
        description="접속 플레이어 1인당 분당 요율 (KRW)"
    )
    tier_multipliers: Dict[str, float] = Field(
        default={
            HardwareTier.STANDARD_SSD.value: 1.0,
            HardwareTier.HIGH_NVME.value: 1.3,
            HardwareTier.EXTREME_DEDICATED.value: 1.8,
        },
        description="하드웨어 스펙 티어별 과금 배율"
    )

class NodeMultiplierUpdate(BaseModel):
    node_id: str
    custom_multiplier: float = Field(..., ge=0.1, le=10.0)

# ---------------------------------------------------------------------------
# User & Admin Account Management Models
# ---------------------------------------------------------------------------
class UserRegisterRequest(BaseModel):
    email: EmailStr
    oauth_provider: str = "google"
    oauth_token: str
    is_adult_verified: bool = Field(
        ...,
        description="대한민국 청소년 보호법 및 이용약관에 따른 19세 이상 법정 성인 확인 필수 체크박스"
    )

class UserResponse(BaseModel):
    id: str
    email: str
    is_adult_verified: bool
    status: str = "ACTIVE"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    balance_krw: float = 0.0

class AdminCreditAdjustRequest(BaseModel):
    user_id: str
    amount_krw: float
    reason: str = "어드민 직접 조정 / 보상 지급"

# ---------------------------------------------------------------------------
# Node & Cluster Scheduling Models
# ---------------------------------------------------------------------------
class NodeRegisterRequest(BaseModel):
    node_id: str
    node_name: str
    ip_address: str
    hardware_tier: HardwareTier = HardwareTier.STANDARD_SSD
    custom_multiplier: Optional[float] = None
    total_ram_mb: int
    total_zram_mb: int
    total_cpu_cores: int
    is_master_node: bool = False

class NodeHealthReport(BaseModel):
    node_id: str
    cpu_usage_pct: float
    ram_used_mb: int
    ram_total_mb: int
    zram_used_mb: int
    zram_total_mb: int
    nvme_swap_used_mb: int
    disk_io_wait_pct: float
    running_containers_count: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# ---------------------------------------------------------------------------
# Minecraft Server Models (3 Presets & Exact 3 Versions)
# ---------------------------------------------------------------------------
class ServerDeployRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=32)
    domain_slug: str = Field(..., pattern=r"^[a-z0-9-]{3,32}$")
    preset_type: ServerPreset = ServerPreset.SURVIVAL_SMP
    server_type: ServerType = ServerType.PAPER
    mc_version: SupportedMCVersion = SupportedMCVersion.V_1_20_4
    allocated_ram_mb: int = Field(default=4096, ge=2048, le=32768)
    hardware_tier_preference: Optional[HardwareTier] = HardwareTier.HIGH_NVME
    preferred_node_id: Optional[str] = None
    target_user_id: Optional[str] = None
    enable_crossplay: bool = True
    enable_zgc: bool = True
    modpack_url: Optional[str] = None

class ServerResponse(BaseModel):
    id: str
    name: str
    domain_slug: str
    preset_type: ServerPreset
    node_id: str
    node_ip: str
    port: int
    rcon_port: int
    server_type: ServerType
    mc_version: str
    allocated_ram_mb: int
    status: ServerStatus
    billing_multiplier: float
    full_domain: str
    is_local_master: bool = False

class ServerControlRequest(BaseModel):
    action: str = Field(..., pattern=r"^(start|stop|restart|kill|backup)$")

class RconExecuteRequest(BaseModel):
    command: str = Field(..., max_length=256)

# ---------------------------------------------------------------------------
# Telemetry & Billing Models
# ---------------------------------------------------------------------------
class TelemetryReportPayload(BaseModel):
    server_id: str
    user_id: str
    node_id: str
    loaded_chunks: int = Field(default=0, ge=0)
    active_players: int = Field(default=0, ge=0)
    tps: float = Field(default=20.0, ge=0.0, le=20.0)
    cpu_pct: float = 0.0
    mem_used_mb: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class CreditTopupRequest(BaseModel):
    amount_krw: float = Field(..., ge=1000, le=1000000)
    payment_method: str = "toss_payments"
    payment_key: str

# ---------------------------------------------------------------------------
# AI Diagnostics & Helpdesk Ticket Management
# ---------------------------------------------------------------------------
class AIReportResponse(BaseModel):
    server_id: str
    root_cause_summary: str
    culprits: List[str]
    actionable_steps: List[str]
    requires_admin_ticket: bool

class HelpdeskTicket(BaseModel):
    id: str
    server_id: str
    user_email: str
    title: str
    user_message: str
    status: TicketStatus = TicketStatus.OPEN
    admin_response: Optional[str] = None
    ai_report_json: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None

class HelpdeskTicketCreate(BaseModel):
    server_id: str
    user_email: str = "user@domain.com"
    title: str
    user_message: str
    ai_report_json: Optional[Dict[str, Any]] = None
    system_log_snippet: Optional[str] = None

class TicketResolveRequest(BaseModel):
    ticket_id: str
    status: TicketStatus
    admin_response: str
