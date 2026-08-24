"""
schema.py - Pydantic Request/Response Models and Enums (Pydantic v2 Compatible)
Supports:
- Free Default Domain vs Premium Custom Domain (1,000 KRW toggle)
- Integer RAM Allocation & Live Cost Calculator
- server.properties Comprehensive GUI Config Editor
- Modrinth & CurseForge Tag/Category Indexes, Infinite Scroll, and 1-Click Auto-Updater
- Server Engine & Version Switcher with Mod Dependency Warnings
- Modpack Direct ZIP / mrpack Importer
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
    FOLIA = "FOLIA"
    FABRIC = "FABRIC"
    
    # 대형 모드팩
    FORGE = "FORGE"
    NEOFORGE = "NEOFORGE"
    SPONGE = "SPONGE"

    # 공식 및 클래식
    VANILLA = "VANILLA"
    SPIGOT = "SPIGOT"
    CRAFTBUKKIT = "CRAFTBUKKIT"

    # 프록시 게이트웨이
    VELOCITY = "VELOCITY"
    BUNGEECORD = "BUNGEECORD"
    WATERFALL = "WATERFALL"

class ServerPreset(str, Enum):
    BUILDER_FLAT = "BUILDER_FLAT"
    SURVIVAL_SMP = "SURVIVAL_SMP"
    MODPACK_READY = "MODPACK_READY"
    ADVANCED_CUSTOM = "ADVANCED_CUSTOM"
    PROXY_NETWORK = "PROXY_NETWORK"

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
# Custom Tier & Swap Configuration Models
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
    swap_ratio: float = Field(default=1.5, ge=0.0, le=5.0)
    zram_compression_algo: str = Field(default="zstd")
    swappiness: int = Field(default=60, ge=0, le=200)
    enable_generational_zgc: bool = Field(default=True)

# ---------------------------------------------------------------------------
# Dynamic Billing Configuration (RAM-Based Pricing Included)
# ---------------------------------------------------------------------------
class BillingRateConfig(BaseModel):
    base_container_per_min: float = Field(default=0.20, ge=0.0, le=100.0)
    per_ram_gb_rate: float = Field(default=0.08, ge=0.0, le=10.0)
    per_chunk_rate: float = Field(default=0.0005, ge=0.0, le=1.0)
    per_player_rate: float = Field(default=0.0500, ge=0.0, le=1.0)
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
    is_adult_verified: bool = Field(...)

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
# Domain Check & Pricing (Free default vs Optional 1,000 KRW Custom)
# ---------------------------------------------------------------------------
class DomainCheckResponse(BaseModel):
    slug: str
    is_available: bool
    is_premium: bool = True
    custom_fee_krw: int = 1000
    suggested_slugs: List[str] = Field(default_factory=list)
    message: str

# ---------------------------------------------------------------------------
# Minecraft Server Models (Free Auto Domain vs Premium Domain)
# ---------------------------------------------------------------------------
class ServerDeployRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=64)
    domain_slug: Optional[str] = None # None이면 무료 자동 도메인 발급
    is_custom_domain: bool = False # False면 무료 자동 도메인, True면 1,000원 차감
    preset_type: ServerPreset = ServerPreset.SURVIVAL_SMP
    server_type: Union[ServerType, str] = ServerType.PAPER
    mc_version: str = Field(default="26.2")
    allocated_ram_mb: int = Field(default=4096, ge=1024, le=131072)
    hardware_tier_preference: Optional[str] = "high_nvme"
    preferred_node_id: Optional[str] = None
    target_user_id: Optional[str] = None
    enable_crossplay: bool = True
    enable_zgc: bool = True
    modpack_id: Optional[str] = None
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

class ServerVersionChangeRequest(BaseModel):
    server_type: str
    mc_version: str
    force: bool = False

class ServerControlRequest(BaseModel):
    action: str = Field(..., pattern=r"^(start|stop|restart|kill|backup)$")

class RconExecuteRequest(BaseModel):
    command: str = Field(..., max_length=256)

# ---------------------------------------------------------------------------
# server.properties GUI Model
# ---------------------------------------------------------------------------
class ServerPropertiesModel(BaseModel):
    server_port: int = 25565
    gamemode: str = "survival"
    difficulty: str = "easy"
    pvp: bool = True
    max_players: int = 20
    motd: str = "A NextGen MC Cloud Hosted Server"
    online_mode: bool = True
    enable_rcon: bool = True
    view_distance: int = 10
    simulation_distance: int = 8
    allow_flight: bool = False
    spawn_protection: int = 16
    white_list: bool = False
    enforce_whitelist: bool = False
    hardcore: bool = False
    spawn_monsters: bool = True
    spawn_animals: bool = True
    spawn_npcs: bool = True
    allow_nether: bool = True
    generate_structures: bool = True
    level_seed: str = ""
    extra_properties: Dict[str, str] = Field(default_factory=dict)

# ---------------------------------------------------------------------------
# File Explorer Models
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
# Modrinth & CurseForge Mod Marketplace Models
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
    project_type: str = "mod" # "mod" or "modpack"
    loaders: List[str] = Field(default_factory=list)
    game_versions: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    source: str = "modrinth" # "modrinth" or "curseforge"
    installed_version: Optional[str] = None
    latest_version: Optional[str] = None
    has_update: bool = False

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
    source: str = "modrinth"
    download_url: Optional[str] = None
    filename: Optional[str] = None

class ModInstallRequest(BaseModel):
    mod_id: str
    version_id: Optional[str] = None
    project_type: str = "mod"
    source: str = "modrinth"
    download_url: Optional[str] = None
    filename: Optional[str] = None

class InstalledModItem(BaseModel):
    id: str
    filename: str
    title: str
    current_version: str
    latest_version: str
    has_update: bool
    source: str
    project_type: str

class ModUpdateRequest(BaseModel):
    mod_ids: List[str] = Field(default_factory=list) # 빈 리스트면 전체 업데이트

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
