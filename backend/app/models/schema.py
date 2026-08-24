"""
schema.py - Pydantic Request/Response Models and Enums (Pydantic v2 Compatible)
Supports:
- RAM-based Pricing Calculation (per_ram_gb_rate) & Dynamic Tier Multipliers
- Integer RAM Allocation (Custom RAM size in MB or GB)
- Real-Time 1-Minute Estimated Cost Calculator
- File Explorer & Mod Marketplace & Domain Checks
"""
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class HardwareTier(str, Enum):
    STANDARD_SSD = "standard_ssd"           # 기본 SSD
    HIGH_NVME = "high_nvme"                 # 고성능 NVMe
    EXTREME_DEDICATED = "extreme_dedicated" # 단독 전용
    CUSTOM = "custom"                       # 어드민 생성 커스텀 티어

class ServerType(str, Enum):
    # 주류 및 최적화
    PAPER = "PAPER"
    PURPUR = "PURPUR"
    FOLIA = "FOLIA"                         # PaperMC 멀티스레드 리전 기반 차세대 코어
    FABRIC = "FABRIC"
    
    # 대형 모드팩
    FORGE = "FORGE"                         # 일반 공식 Forge
    NEOFORGE = "NEOFORGE"
    SPONGE = "SPONGE"                       # SpongeVanilla / SpongeForge

    # 공식 및 클래식
    VANILLA = "VANILLA"                     # 모장 공식 바닐라 (스냅샷 완벽 호환)
    SPIGOT = "SPIGOT"                       # 전통적인 스피곳
    CRAFTBUKKIT = "CRAFTBUKKIT"             # 클래식 크래프트버킷

    # 프록시 게이트웨이
    VELOCITY = "VELOCITY"                   # Velocity L4 Proxy
    BUNGEECORD = "BUNGEECORD"               # BungeeCord Proxy
    WATERFALL = "WATERFALL"                 # Waterfall Proxy

class ServerPreset(str, Enum):
    BUILDER_FLAT = "BUILDER_FLAT"           # 건축 서버 (평지, 월드에딧, 최적화)
    SURVIVAL_SMP = "SURVIVAL_SMP"           # 야생 서버 (야생맵, TPA/Home, Spark)
    ADVANCED_CUSTOM = "ADVANCED_CUSTOM"     # 고급 커스텀 서버 (모든 구동기 및 스냅샷)
    PROXY_NETWORK = "PROXY_NETWORK"         # Velocity / BungeeCord 프록시 게이트웨이

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
# Custom Tier (Node Grouping) & Swap Configuration Models
# ---------------------------------------------------------------------------
class CustomTierCreate(BaseModel):
    tier_id: str = Field(..., pattern=r"^[a-z0-9_-]{3,32}$")
    name: str = Field(..., min_length=2, max_length=64)
    multiplier: float = Field(..., ge=0.1, le=10.0)
    description: str = Field(default="", max_length=256)
    assigned_node_ids: List[str] = Field(default_factory=list)

class CustomTierResponse(BaseModel):
    tier_id: str
    name: str
    multiplier: float
    description: str
    assigned_node_ids: List[str]
    is_builtin: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

class SwapConfigModel(BaseModel):
    swap_ratio: float = Field(default=1.5, ge=0.0, le=5.0, description="RAM 대비 스왑 할당 비율 (예: 1.5배)")
    zram_compression_algo: str = Field(default="zstd", description="ZRAM 압축 알고리즘 (zstd, lz4, lzo-rle)")
    swappiness: int = Field(default=60, ge=0, le=200, description="커널 swappiness 수치")
    enable_generational_zgc: bool = Field(default=True, description="JDK 21+ Generational ZGC 기본 활성화 여부")

# ---------------------------------------------------------------------------
# Dynamic Billing Configuration (RAM-Based Pricing Included)
# ---------------------------------------------------------------------------
class BillingRateConfig(BaseModel):
    base_container_per_min: float = Field(default=0.20, ge=0.0, le=100.0, description="기본 컨테이너 유지비 (분당 KRW)")
    per_ram_gb_rate: float = Field(default=0.08, ge=0.0, le=10.0, description="점유/할당 RAM 1GB당 분당 단가 (KRW)")
    per_chunk_rate: float = Field(default=0.0005, ge=0.0, le=1.0, description="로드된 청크당 분당 단가 (KRW)")
    per_player_rate: float = Field(default=0.0500, ge=0.0, le=1.0, description="동접 플레이어당 분당 단가 (KRW)")
    tier_multipliers: Dict[str, float] = Field(default_factory=dict)

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
        description="19세 이상 법정 성인 확인 필수 체크박스"
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
    hardware_tier: str = "standard_ssd"
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
# Domain Check & Pricing
# ---------------------------------------------------------------------------
class DomainCheckResponse(BaseModel):
    slug: str
    is_available: bool
    is_premium: bool = False
    custom_fee_krw: int = 1000
    suggested_slugs: List[str] = Field(default_factory=list)
    message: str

# ---------------------------------------------------------------------------
# Minecraft Server Models (Integer RAM direct input supported)
# ---------------------------------------------------------------------------
class ServerDeployRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=64)
    domain_slug: str = Field(..., pattern=r"^[a-z0-9-]{3,32}$")
    preset_type: ServerPreset = ServerPreset.SURVIVAL_SMP
    server_type: Union[ServerType, str] = ServerType.PAPER
    mc_version: str = Field(default="26.2")
    allocated_ram_mb: int = Field(default=4096, ge=1024, le=131072, description="정수로 직접 지정하는 최대 램 용량 (MB 단위, 예: 4096, 6144, 8192, 12288, 16384)")
    hardware_tier_preference: Optional[str] = "high_nvme"
    preferred_node_id: Optional[str] = None
    target_user_id: Optional[str] = None
    is_custom_domain: bool = False
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
    server_type: str
    mc_version: str
    allocated_ram_mb: int
    estimated_cost_per_min: float = 0.0
    status: ServerStatus
    billing_multiplier: float
    full_domain: str
    is_local_master: bool = False

class ServerControlRequest(BaseModel):
    action: str = Field(..., pattern=r"^(start|stop|restart|kill|backup)$")

class RconExecuteRequest(BaseModel):
    command: str = Field(..., max_length=256)

# ---------------------------------------------------------------------------
# File Explorer & Config Editor Models
# ---------------------------------------------------------------------------
class FileItem(BaseModel):
    name: str
    path: str
    is_dir: bool
    size_bytes: int
    modified_at: str
    is_editable: bool = False

class FileContentRead(BaseModel):
    path: str
    content: str
    size_bytes: int
    is_readonly: bool = False

class FileContentSave(BaseModel):
    path: str
    content: str

# ---------------------------------------------------------------------------
# Modrinth & CurseForge Mod Marketplace Models (Prism Launcher Style)
# ---------------------------------------------------------------------------
class ModSearchItem(BaseModel):
    id: str
    slug: str
    title: str
    description: str
    author: str
    icon_url: Optional[str] = None
    downloads: int = 0
    follows: int = 0
    project_type: str = "mod"
    loaders: List[str] = Field(default_factory=list)
    game_versions: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    source: str = "modrinth"

class ModDetailResponse(BaseModel):
    id: str
    slug: str
    title: str
    description: str
    body_markdown: str
    author: str
    icon_url: Optional[str] = None
    banner_url: Optional[str] = None
    downloads: int
    loaders: List[str]
    game_versions: List[str]
    project_type: str
    download_url: Optional[str] = None
    filename: Optional[str] = None

class ModInstallRequest(BaseModel):
    mod_id: str
    version_id: Optional[str] = None
    project_type: str = "mod"
    download_url: Optional[str] = None
    filename: Optional[str] = None

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
