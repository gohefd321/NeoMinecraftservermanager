#!/usr/bin/env bash
# ==============================================================================
# NextGen Minecraft Cloud Platform - Multi-Distro Installer & Provisioner
# ==============================================================================
set -euo pipefail

# ANSI Color Codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${CYAN}"
echo "================================================================================"
echo "   _  __         __  ____                                     _____                                             "
echo "  / |/ /__ ___  /  |/  (_)__  ___ ___________ _/ _/ /____ ___ _____  _____ ______ _  ___ ____  ___ ____ ____ ____"
echo " /    / -_) _ \/ /|_/ / / _ \/ -_) __/ __/ _ \`/ _/ __(_-</ -_) __/ |/ / -_) __/  ' \/ _ \`/ _ \/ _ \`/ _ \`/ -_) __/"
echo "/_/|_/\__/\___/_/  /_/_/_//_/\__/\__/_/   \_,_/_/ \__/___/\__/_/  |___/\__/_/ /_/_/_/\_,_/_//_/\_,_/\_, /\__/_/   "
echo "                                                                                                /___/          "
echo "        Next-Gen Cloud-Native Minecraft Hosting Platform Installer             "
echo "================================================================================"
echo -e "${NC}"

# 1. Root 권한 체크
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}[ERROR] This installer must be executed as root (sudo).${NC}" >&2
    exit 1
fi

# 2. 완전 파괴적 클린 재설치 (Nuclear Wipe) 옵션 확인
INSTALL_DIR="/opt/nextgen-mc-platform"
CONFIG_DIR="/etc/nextgen-mc"
DATA_DIR="/var/mc_servers"
LOG_DIR="/var/log/nextgen-mc"

CLI_ACTION="${1:-}"

if [ "$CLI_ACTION" = "--wipe" ] || [ "$CLI_ACTION" = "--clean" ]; then
    WIPE_CHOICE="yes"
elif [ -d "${INSTALL_DIR}" ] || [ -f "${CONFIG_DIR}/node.env" ]; then
    echo -e "${YELLOW}${BOLD}⚠️  기존에 설치된 NextGen MC Platform 환경이 감지되었습니다.${NC}"
    echo ""
    echo "  [1] 일반 설치 / 업데이트 (기존 데이터 및 월드 보존)"
    echo -e "  [2] ${RED}${BOLD}⚠️  100% 완전 파괴적 클린 재설치 (Nuclear Wipe)${NC}"
    echo "      (모든 컨테이너·월드·설정·캐시 영구 삭제 후 0% 캐시 상태에서 완전 새로 시작)"
    echo "  [3] 취소 (Exit)"
    echo ""
    read -rp "선택 (1-3, 기본값: 1): " USER_SELECT
    USER_SELECT="${USER_SELECT:-1}"

    if [ "$USER_SELECT" = "2" ]; then
        echo -e "${RED}${BOLD}"
        echo "================================================================================"
        echo "⚠️  [경고] 이 작업은 다음 항목들을 완전히 영구 삭제합니다:"
        echo "  - 모든 마인크래프트 Docker 컨테이너 및 볼륨"
        echo "  - ${DATA_DIR} (모든 서버 월드 맵, 플러그인, 모드팩)"
        echo "  - ${INSTALL_DIR} (플랫폼 코드 및 Python venv)"
        echo "  - ${CONFIG_DIR} (노드 설정 및 API 키)"
        echo "  - pip 및 패키지 빌드 캐시"
        echo "================================================================================"
        echo -e "${NC}"
        read -rp "정말로 모든 데이터를 영구 삭제하고 새로 시작하시겠습니까? (yes/N): " CONFIRM_INPUT
        if [[ "$CONFIRM_INPUT" =~ ^[Yy]([Ee][Ss])?$ ]]; then
            WIPE_CHOICE="yes"
        else
            echo "취소되었습니다."
            exit 0
        fi
    elif [ "$USER_SELECT" = "3" ]; then
        echo "설치를 종료합니다."
        exit 0
    else
        WIPE_CHOICE="no"
    fi
else
    WIPE_CHOICE="no"
fi

if [ "${WIPE_CHOICE:-no}" = "yes" ]; then
    echo -e "${RED}>>> [Nuclear Wipe] Wiping all existing containers, files, services and caches...${NC}"
    systemctl stop mc-master 2>/dev/null || true
    systemctl stop mc-worker 2>/dev/null || true
    systemctl disable mc-master 2>/dev/null || true
    systemctl disable mc-worker 2>/dev/null || true
    rm -f /etc/systemd/system/mc-master.service /etc/systemd/system/mc-worker.service
    systemctl daemon-reload 2>/dev/null || true

    if command -v docker &>/dev/null; then
        RUNNING_MC=$(docker ps -a --filter "name=mc-" -q 2>/dev/null || true)
        if [ -n "${RUNNING_MC}" ]; then
            docker rm -f ${RUNNING_MC} 2>/dev/null || true
        fi
        docker volume prune -f 2>/dev/null || true
    fi

    rm -rf "${INSTALL_DIR}" "${CONFIG_DIR}" "${DATA_DIR}" "${LOG_DIR}" /tmp/neo_mc_clone /tmp/setup-wizard
    if command -v pip3 &>/dev/null; then
        pip3 cache purge 2>/dev/null || true
    fi
    echo -e "${GREEN}✓ Complete clean wipe accomplished. Starting fresh install from 0% cache.${NC}"
fi

# 3. OS 및 아키텍처 식별
ARCH=$(uname -m)
if [ "$ARCH" != "x86_64" ] && [ "$ARCH" != "aarch64" ]; then
    echo -e "${RED}[ERROR] Unsupported architecture: ${ARCH}. Only x86_64 and aarch64 are supported.${NC}" >&2
    exit 1
fi

# OS 배포판 및 패키지 매니저 감지
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_ID="${ID:-unknown}"
    OS_LIKE="${ID_LIKE:-}"
else
    echo -e "${RED}[ERROR] Cannot detect Linux distribution (/etc/os-release not found).${NC}" >&2
    exit 1
fi

# 패키지 매니저 분기 확인
if command -v dnf &> /dev/null; then
    PKG_MGR="dnf"
elif command -v yum &> /dev/null; then
    PKG_MGR="yum"
elif command -v apt-get &> /dev/null; then
    PKG_MGR="apt"
elif command -v pacman &> /dev/null; then
    PKG_MGR="pacman"
elif command -v zypper &> /dev/null; then
    PKG_MGR="zypper"
else
    echo -e "${RED}[ERROR] Unsupported package manager. Please install dependencies manually.${NC}" >&2
    exit 1
fi

echo -e "${BLUE}>>> [1/5] Updating system packages & installing core dependencies (${PKG_MGR})...${NC}"

case "$PKG_MGR" in
    apt)
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -qq
        apt-get install -y -qq \
            ca-certificates curl gnupg jq git python3 python3-pip python3-venv \
            golang-go apparmor apparmor-utils iptables net-tools
        ;;
    dnf|yum)
        $PKG_MGR check-update -y || true
        if [[ "$OS_ID" =~ ^(rhel|centos|rocky|almalinux)$ ]]; then
            $PKG_MGR install -y -q epel-release || true
        fi
        $PKG_MGR install -y -q \
            ca-certificates curl gnupg2 jq git python3 python3-pip python3-venv \
            golang iptables net-tools
        ;;
    pacman)
        pacman -Sy --noconfirm --needed \
            ca-certificates curl gnupg jq git python python-pip \
            go iptables net-tools
        ;;
    zypper)
        zypper --non-interactive refresh
        zypper --non-interactive install -y \
            ca-certificates curl gpg2 jq git python3 python3-pip \
            go iptables net-tools-deprecated
        ;;
esac

# Python 백엔드 필수 의존성 설치
pip3 install --upgrade pip --quiet --break-system-packages 2>/dev/null || pip3 install --upgrade pip --quiet || true
pip3 install "fastapi>=0.109.0" "uvicorn[standard]>=0.27.0" "pydantic>=2.5.0" "pydantic-settings>=2.1.0" \
             "asyncpg>=0.29.0" "redis>=5.0.1" "aiomcrcon>=0.2.0" "aiohttp>=3.9.0" "aiofiles>=23.2.1" \
             "httpx>=0.26.0" "psutil>=5.9.0" --break-system-packages --quiet 2>/dev/null || true

# 방화벽 포트 자동 개방 (8005, 8080-8085, 25565-25999, 19132)
if command -v firewall-cmd &>/dev/null && systemctl is-active --quiet firewalld 2>/dev/null; then
    firewall-cmd --permanent --add-port=8005/tcp --add-port=8080-8085/tcp --add-port=25565-25999/tcp --add-port=19132/udp 2>/dev/null || true
    firewall-cmd --reload 2>/dev/null || true
elif command -v ufw &>/dev/null && ufw status | grep -qw "active" 2>/dev/null; then
    ufw allow 8005/tcp comment "NextGen Master API" >/dev/null 2>&1 || true
    ufw allow 8080:8085/tcp comment "NextGen Setup Wizard" >/dev/null 2>&1 || true
    ufw allow 25565:25999/tcp comment "NextGen Game Ports" >/dev/null 2>&1 || true
    ufw allow 19132/udp comment "NextGen Bedrock UDP" >/dev/null 2>&1 || true
fi

# 4. Docker & Docker Compose 설치 (공통 공식 스크립트 활용)
echo -e "${BLUE}>>> [2/5] Verifying Docker and Container Isolation Engine...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Docker is not detected. Installing Docker via official script...${NC}"
    curl -fsSL https://get.docker.com | sh
fi

systemctl enable --now docker

# 5. 플랫폼 디렉토리 배치 및 Git 레포지토리 클론
echo -e "${BLUE}>>> [3/5] Setting up platform directory and cloning from GitHub...${NC}"
mkdir -p "${INSTALL_DIR}"
mkdir -p "${CONFIG_DIR}"
mkdir -p "${DATA_DIR}"
mkdir -p "${LOG_DIR}"

GIT_REPO_URL="https://github.com/gohefd321/NeoMinecraftservermanager.git"
TMP_CLONE_DIR="/tmp/neo_mc_clone"

# 로컬에 이미 최신 파일이 있으면 로컬 복사 우선, 없으면 git clone
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "${SCRIPT_DIR}/backend/app/main.py" ]; then
    echo "Deploying from local repository..."
    cp -r "${SCRIPT_DIR}"/* "${INSTALL_DIR}/" || true
else
    echo "Cloning repository from: ${GIT_REPO_URL} ..."
    rm -rf "${TMP_CLONE_DIR}"
    git clone --quiet "${GIT_REPO_URL}" "${TMP_CLONE_DIR}"
    cp -r "${TMP_CLONE_DIR}"/. "${INSTALL_DIR}/"
    rm -rf "${TMP_CLONE_DIR}"
fi
echo -e "${GREEN}Successfully deployed platform files.${NC}"

# 6. AppArmor / SELinux 보안 프로파일 처리
echo -e "${BLUE}>>> [4/5] Configuring Security Isolation Profiles...${NC}"
if command -v apparmor_parser &> /dev/null && [ -f "${INSTALL_DIR}/security/apparmor/minecraft-secure.profile" ]; then
    apparmor_parser -r -W "${INSTALL_DIR}/security/apparmor/minecraft-secure.profile" || true
    echo -e "${GREEN}AppArmor Profile [minecraft-secure] registered.${NC}"
elif command -v getenforce &> /dev/null; then
    echo -e "${YELLOW}SELinux detected ($(getenforce)). Ensure proper container policies if required.${NC}"
fi

# 7. Systemd 서비스 템플릿 복사
if [ -f "${INSTALL_DIR}/setup-wizard/service_templates/mc-master.service" ]; then
    cp "${INSTALL_DIR}/setup-wizard/service_templates/mc-master.service" /etc/systemd/system/
    cp "${INSTALL_DIR}/setup-wizard/service_templates/mc-worker.service" /etc/systemd/system/
    systemctl daemon-reload
else
    echo -e "${YELLOW}Warning: Systemd templates not found.${NC}"
fi

# 8. Setup Wizard 실행
echo -e "${BLUE}>>> [5/5] Launching Web Setup Wizard on port 8080...${NC}"
SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")

if [ -f "${INSTALL_DIR}/setup-wizard/main.go" ] && command -v go &>/dev/null; then
    cd "${INSTALL_DIR}/setup-wizard"
    go build -o /tmp/setup-wizard main.go 2>/dev/null || true
    if [ -f /tmp/setup-wizard ]; then
        chmod +x /tmp/setup-wizard
        echo -e "${GREEN}================================================================================"
        echo -e "🎉 Installation pre-requisites completed!"
        echo -e "👉 Please open your browser and navigate to the Web Setup Wizard:"
        echo -e "    🌐  http://${SERVER_IP}:8080   (or http://localhost:8080)"
        echo -e "================================================================================${NC}"
        exec /tmp/setup-wizard
    fi
fi

# Python Setup Wizard Fallback
python3 "${INSTALL_DIR}/setup-wizard/server.py"
