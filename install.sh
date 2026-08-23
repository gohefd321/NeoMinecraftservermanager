#!/usr/bin/env bash
# ==============================================================================
# NextGen Minecraft Cloud Platform - One-Click Installer & Provisioner
# Usage: curl -sSL https://domain/install.sh | sudo bash
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}"
echo "================================================================================"
echo "   ____  ___          __  ______              __  ___      ____  __       __  "
echo "  / __ \/ _ \        / / / / __ \____ ___  __/ / / (_)___ / __ \/ /______/ /_ "
echo " / / / / / / / ___  / /_/ / / / / __ `/ / / / /_/ / / __ \ / / / / / __  / __/ "
echo "/ /_/ / /_/ / /__/ / __  / /_/ / /_/ / /_/ / __  / / / / // /_/ / / /_/ / /_   "
echo "\____/\____/      /_/ /_/\____/\__, /\__,_/_/ /_/_/_/ /_(_)____/_/\__,_/\__/   "
echo "                              /____/                                           "
echo "        Next-Gen Cloud-Native Minecraft Hosting Platform Installer             "
echo "================================================================================"
echo -e "${NC}"

# 1. Root 권한 체크
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}[ERROR] This installer must be executed as root (sudo).${NC}" >&2
    exit 1
fi

echo -e "${BLUE}>>> [1/6] Updating system packages & installing core dependencies...${NC}"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq || true
apt-get install -y -qq \
    curl \
    jq \
    git \
    python3 \
    python3-pip \
    python3-venv \
    zram-tools \
    iptables \
    net-tools || true

# 2. Docker 확인 및 설치
echo -e "${BLUE}>>> [2/6] Verifying Docker and Container Isolation Engine...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Docker is not detected. Installing Docker CE...${NC}"
    curl -fsSL https://get.docker.com | bash || true
fi
systemctl enable --now docker 2>/dev/null || true

# 3. 플랫폼 디렉토리 배치
INSTALL_DIR="/opt/nextgen-mc-platform"
echo -e "${BLUE}>>> [3/6] Setting up platform directory at ${INSTALL_DIR}...${NC}"
mkdir -p "${INSTALL_DIR}"
mkdir -p /etc/nextgen-mc
mkdir -p /var/mc_servers
mkdir -p /var/log/nextgen-mc

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -d "${SCRIPT_DIR}" ] && [ "${SCRIPT_DIR}" != "${INSTALL_DIR}" ]; then
    cp -r "${SCRIPT_DIR}"/* "${INSTALL_DIR}/" || true
fi

# 4. Python 전용 가상환경 생성 및 의존성 설치 (uvicorn, fastapi 등)
echo -e "${BLUE}>>> [4/6] Initializing Isolated Python Virtualenv & Dependencies...${NC}"
VENV_DIR="${INSTALL_DIR}/venv"
if [ ! -d "${VENV_DIR}" ]; then
    python3 -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/pip" install --upgrade pip -q
if [ -f "${INSTALL_DIR}/backend/requirements.txt" ]; then
    echo "Installing backend dependencies in ${VENV_DIR}..."
    "${VENV_DIR}/bin/pip" install -r "${INSTALL_DIR}/backend/requirements.txt" -q
fi
if [ -f "${INSTALL_DIR}/worker/requirements.txt" ]; then
    "${VENV_DIR}/bin/pip" install -r "${INSTALL_DIR}/worker/requirements.txt" -q
fi

# 5. 보안 프로파일 및 Systemd 서비스 템플릿 복사
echo -e "${BLUE}>>> [5/6] Configuring Security Isolation Profiles & Services...${NC}"
if command -v apparmor_parser &> /dev/null && [ -f "${INSTALL_DIR}/security/apparmor/minecraft-secure.profile" ]; then
    apparmor_parser -r -W "${INSTALL_DIR}/security/apparmor/minecraft-secure.profile" 2>/dev/null || true
fi

if command -v getenforce &> /dev/null && [ "$(getenforce)" = "Enforcing" ]; then
    chcon -Rt container_file_t /var/mc_servers 2>/dev/null || true
fi

if [ -d "${INSTALL_DIR}/setup-wizard/service_templates" ]; then
    cp "${INSTALL_DIR}/setup-wizard/service_templates/mc-master.service" /etc/systemd/system/ 2>/dev/null || true
    cp "${INSTALL_DIR}/setup-wizard/service_templates/mc-worker.service" /etc/systemd/system/ 2>/dev/null || true
    systemctl daemon-reload 2>/dev/null || true
fi

# 6. Web Setup Wizard 실행
echo -e "${BLUE}>>> [6/6] Launching Web Setup Wizard...${NC}"
chmod +x "${INSTALL_DIR}/setup-wizard/server.py" 2>/dev/null || true
python3 "${INSTALL_DIR}/setup-wizard/server.py"
