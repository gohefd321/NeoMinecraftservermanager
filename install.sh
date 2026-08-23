#!/usr/bin/env bash
# ==============================================================================
# NextGen Minecraft Cloud Platform - One-Click Installer & Provisioner
# Usage: curl -sSL https://domain/install.sh | sudo bash
# ==============================================================================
set -euo pipefail

# ANSI Color Codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${CYAN}"
echo "================================================================================"
echo "   _  __         __  ____                       _____                                                            "
echo "  / |/ /__ ___  /  |/  (_)__  ___ ___________ _/ _/ /____ ___ _____  _____ ______ _  ___ ____  ___ ____ ____ ____"
echo " /    / -_) _ \/ /|_/ / / _ \/ -_) __/ __/ _ `/ _/ __(_-</ -_) __/ |/ / -_) __/  ' \/ _ `/ _ \/ _ `/ _ `/ -_) __/"
echo "/_/|_/\__/\___/_/  /_/_/_//_/\__/\__/_/  \_,_/_/ \__/___/\__/_/  |___/\__/_/ /_/_/_/\_,_/_//_/\_,_/\_, /\__/_/   "
echo "                                                                                                  /___/          "
echo "        Next-Gen Cloud-Native Minecraft Hosting Platform Installer             "
echo "================================================================================"
echo -e "${NC}"

# 1. Root 권한 체크
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}[ERROR] This installer must be executed as root (sudo).${NC}" >&2
    exit 1
fi

# 2. OS 및 아키텍처 식별
ARCH=$(uname -m)
if [ "$ARCH" != "x86_64" ] && [ "$ARCH" != "aarch64" ]; then
    echo -e "${RED}[ERROR] Unsupported architecture: ${ARCH}. Only x86_64 and aarch64 are supported.${NC}" >&2
    exit 1
fi

echo -e "${BLUE}>>> [1/5] Updating system packages & installing core dependencies...${NC}"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    jq \
    git \
    python3 \
    python3-pip \
    python3-venv \
    golang-go \
    zram-tools \
    apparmor \
    apparmor-utils \
    iptables \
    net-tools

# 3. Docker & Docker Compose 설치 (미설치 시)
echo -e "${BLUE}>>> [2/5] Verifying Docker and Container Isolation Engine...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Docker is not detected. Installing Docker CE Official Repository...${NC}"
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg --yes
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

systemctl enable --now docker

# 4. 플랫폼 디렉토리 배치
INSTALL_DIR="/opt/nextgen-mc-platform"
echo -e "${BLUE}>>> [3/5] Setting up platform directory at ${INSTALL_DIR}...${NC}"
mkdir -p "${INSTALL_DIR}"
mkdir -p /etc/nextgen-mc
mkdir -p /var/mc_servers
mkdir -p /var/log/nextgen-mc

# 로컬 스크립트 복사 또는 클론
if [ -d "/home/bettercallsixseven/nextgen-mc-platform" ]; then
    cp -r /home/bettercallsixseven/nextgen-mc-platform/* "${INSTALL_DIR}/"
fi

# 5. AppArmor 프로파일 로드
echo -e "${BLUE}>>> [4/5] Loading Custom AppArmor Sandboxing Profiles...${NC}"
if [ -f "${INSTALL_DIR}/security/apparmor/minecraft-secure.profile" ]; then
    apparmor_parser -r -W "${INSTALL_DIR}/security/apparmor/minecraft-secure.profile" || true
    echo -e "${GREEN}AppArmor Profile [minecraft-secure] registered.${NC}"
fi

# 6. Systemd 서비스 템플릿 복사
cp "${INSTALL_DIR}/setup-wizard/service_templates/mc-master.service" /etc/systemd/system/
cp "${INSTALL_DIR}/setup-wizard/service_templates/mc-worker.service" /etc/systemd/system/
systemctl daemon-reload

# 7. Setup Wizard 컴파일 및 실행
echo -e "${BLUE}>>> [5/5] Launching Web Setup Wizard on port 8080...${NC}"
cd "${INSTALL_DIR}"

# Go 웹서버 빌드
cd "${INSTALL_DIR}/setup-wizard"
go build -o /tmp/setup-wizard main.go
chmod +x /tmp/setup-wizard

SERVER_IP=$(hostname -I | awk '{print $1}')
echo -e "${GREEN}================================================================================"
echo -e "🎉 Installation pre-requisites completed!"
echo -e "👉 Please open your browser and navigate to the Web Setup Wizard:"
echo -e "   🌐  http://${SERVER_IP}:8080   (or http://localhost:8080)"
echo -e "================================================================================${NC}"

# 웹 위저드 프로세스 실행 (포그라운드 대기)
/tmp/setup-wizard
