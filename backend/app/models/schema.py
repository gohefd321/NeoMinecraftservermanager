"""
schema.py - Pydantic Request/Response Models and Enums (Pydantic v2 Compatible)
"""
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class HardwareTier(str, Enum):
    STANDARD_SSD = "standard_ssd"           # 1.0x 배율
    HIGH_NVME = "high_nvme"                 # 1.3x 배율
    EXTREME_DEDICATED = "extreme_dedicated" # 1.8x 배율

class ServerType(str, Enum):
    PAPER = "PAPER"
    FABRIC = "FABRIC"
    NEOFORGE = "NEOFORGE"
    FORGE = "FORGE"
    PURPUR = "PURPUR"

class ServerStatus(str, Enum):
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    SUSPENDED = "SUSPENDED"
    PROVISIONING = "PROVISIONING"
    ERROR = "ERROR"

# ---------------------------------------------------------------------------
# User & Auth Models (19세 이상 법정 연령 확인 필수)
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
    created_at: datetime
    balance_krw: float = 0.0

# ---------------------------------------------------------------------------
# Node & Cluster Scheduling Models (차등 과금 및 자원 가용성)
# ---------------------------------------------------------------------------
class NodeRegisterRequest(BaseModel):
    node_id: str
    node_name: str
    ip_address: str
    hardware_tier: HardwareTier = HardwareTier.STANDARD_SSD
    total_ram_mb: int
    total_zram_mb: int
    total_cpu_cores: int

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
# Minecraft Server Models
# ---------------------------------------------------------------------------
class ServerDeployRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=32)
    domain_slug: str = Field(..., pattern=r"^[a-z0-9-]{3,32}$")
    server_type: ServerType = ServerType.PAPER
    mc_version: str = "1.20.4"
    allocated_ram_mb: int = Field(default=4096, ge=2048, le=32768)
    hardware_tier_preference: Optional[HardwareTier] = HardwareTier.HIGH_NVME
    enable_crossplay: bool = True
    enable_zgc: bool = True
    modpack_url: Optional[str] = None

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
# AI Diagnostics & Support Ticket Models
# ---------------------------------------------------------------------------
class AIReportResponse(BaseModel):
    server_id: str
    root_cause_summary: str
    culprits: List[str]
    actionable_steps: List[str]
    requires_admin_ticket: bool

class HelpdeskTicketCreate(BaseModel):
    server_id: str
    title: str
    user_message: str
    ai_report_json: Optional[Dict[str, Any]] = None
    system_log_snippet: Optional[str] = None
