"""
security.py - Security, Sanitization, SSRF Defense, and Authentication
"""
import re
import hmac
import json
import base64
import ipaddress
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional, Any
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

security_bearer = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# 1. RCON & Command Injection Sanitizer
# ---------------------------------------------------------------------------
DANGEROUS_COMMAND_REGEX = re.compile(r"[\r\n;&|`$><]")

SAFE_RCON_COMMANDS = {
    "say", "tellraw", "title", "tp", "teleport", "time", "weather",
    "gamemode", "difficulty", "give", "clear", "kick", "ban", "pardon",
    "whitelist", "op", "deop", "save-all", "save-off", "save-on", "stop",
    "spark", "tps", "list", "seed", "gamerule", "locate", "worldborder"
}

def sanitize_rcon_command(command: str) -> str:
    """
    RCON 명령어 살균 및 인젝션 방어
    - CRLF 줄바꿈 주입 차단
    - 쉘 실행 특수문자 차단
    - 화이트리스트 프리픽스 검증
    """
    cleaned = command.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="명령어가 비어 있습니다.")

    if DANGEROUS_COMMAND_REGEX.search(cleaned):
        raise HTTPException(
            status_code=400,
            detail="명령어에 금지된 특수문자(\\r, \\n, ;, &, |, `, $, >, <)가 포함되어 있습니다."
        )

    parts = cleaned.split()
    cmd_name = parts[0].lower()
    if cmd_name.startswith("/"):
        cmd_name = cmd_name[1:]
        cleaned = cleaned[1:]

    if cmd_name not in SAFE_RCON_COMMANDS:
        raise HTTPException(
            status_code=403,
            detail=f"허용되지 않은 RCON 명령어입니다: '{cmd_name}'. 승인된 명령어만 실행 가능합니다."
        )

    return cleaned


# ---------------------------------------------------------------------------
# 2. SSRF (Server-Side Request Forgery) Defense
# ---------------------------------------------------------------------------
BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback
    ipaddress.ip_network("10.0.0.0/8"),        # Private RFC1918
    ipaddress.ip_network("172.16.0.0/12"),     # Private RFC1918
    ipaddress.ip_network("192.168.0.0/16"),    # Private RFC1918
    ipaddress.ip_network("169.254.0.0/16"),    # Link-local / Metadata
    ipaddress.ip_network("::1/128"),           # IPv6 Loopback
    ipaddress.ip_network("fc00::/7"),          # IPv6 Unique Local
    ipaddress.ip_network("fe80::/10"),         # IPv6 Link-Local
]

def validate_url_safety(target_url: str) -> str:
    """
    외부 모드팩 다운로드 및 웹훅 URL의 SSRF 취약점을 방어
    """
    parsed = urllib.parse.urlparse(target_url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="HTTP 및 HTTPS URL만 허용됩니다.")

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=400, detail="유효하지 않은 도메인 또는 URL입니다.")

    if hostname.lower() in ("localhost", "127.0.0.1", "0.0.0.0", "metadata.google.internal", "169.254.169.254"):
        raise HTTPException(status_code=400, detail="내부 및 메타데이터 주소로의 접근은 금지되어 있습니다.")

    try:
        ip = ipaddress.ip_address(hostname)
        for net in BLOCKED_IP_NETWORKS:
            if ip in net:
                raise HTTPException(status_code=400, detail="사설 네트워크 IP 접근이 거부되었습니다.")
    except ValueError:
        pass

    return target_url


# ---------------------------------------------------------------------------
# 3. Path Traversal Defense (Zip Slip 방어)
# ---------------------------------------------------------------------------
def sanitize_relative_path(path_str: str) -> str:
    """Path Traversal (../) 차단 및 정규화"""
    normalized = urllib.parse.unquote(path_str).replace("\\", "/")
    if "../" in normalized or normalized.startswith("/") or ":" in normalized:
        raise HTTPException(status_code=400, detail=f"악의적인 경로 탐색 시도가 감지되었습니다: {path_str}")
    return normalized


# ---------------------------------------------------------------------------
# 4. Standard / Fallback JWT Authentication
# ---------------------------------------------------------------------------
def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')

def _b64_decode(data_str: str) -> bytes:
    padding = '=' * (4 - (len(data_str) % 4)) if len(data_str) % 4 != 0 else ''
    return base64.urlsafe_b64decode(data_str + padding)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    try:
        from jose import jwt
        to_encode = data.copy()
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    except ImportError:
        # Fallback Standard JWT 구현 (외부 패키지 미설치 환경 호환)
        header = {"alg": "HS256", "typ": "JWT"}
        to_encode = data.copy()
        expire = int((datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))).timestamp())
        to_encode.update({"exp": expire})
        
        header_b64 = _b64_encode(json.dumps(header).encode())
        payload_b64 = _b64_encode(json.dumps(to_encode).encode())
        signature = hmac.new(
            settings.JWT_SECRET.encode(),
            f"{header_b64}.{payload_b64}".encode(),
            "sha256"
        ).digest()
        sig_b64 = _b64_encode(signature)
        return f"{header_b64}.{payload_b64}.{sig_b64}"

def decode_access_token(token: str) -> dict:
    try:
        from jose import jwt, JWTError
        try:
            return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="인증 토큰이 유효하지 않거나 만료되었습니다."
            )
    except ImportError:
        parts = token.split(".")
        if len(parts) != 3:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="토큰 형식이 올바르지 않습니다.")
        
        header_b64, payload_b64, sig_b64 = parts
        expected_sig = _b64_encode(hmac.new(
            settings.JWT_SECRET.encode(),
            f"{header_b64}.{payload_b64}".encode(),
            "sha256"
        ).digest())

        if not hmac.compare_digest(sig_b64, expected_sig):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="토큰 서명이 일치하지 않습니다.")

        payload = json.loads(_b64_decode(payload_b64).decode())
        if "exp" in payload and payload["exp"] < int(datetime.utcnow().timestamp()):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="토큰이 만료되었습니다.")
        return payload
