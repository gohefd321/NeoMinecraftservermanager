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

# 2. OS 및 아키텍처 식별
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
        # EPEL 저장소 활성화 (RHEL/CentOS/Rocky/Alma용)
        if [[ "$OS_ID" =~ ^(rhel|centos|rocky|almalinux)$ ]]; then
            $PKG_MGR install -y -q epel-release || true
        fi
        $PKG_MGR install -y -q \
            ca-certificates curl gnupg2 jq git python3 python3-pip \
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

# 3. Docker & Docker Compose 설치 (공통 공식 스크립트 활용)
echo -e "${BLUE}>>> [2/5] Verifying Docker and Container Isolation Engine...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Docker is not detected. Installing Docker via official script...${NC}"
    curl -fsSL https://get.docker.com | sh
fi

systemctl enable --now docker

# 4. 플랫폼 디렉토리 배치 및 Git 레포지토리 클론
INSTALL_DIR="/opt/nextgen-mc-platform"
echo -e "${BLUE}>>> [3/5] Setting up platform directory and cloning from GitHub...${NC}"
mkdir -p "${INSTALL_DIR}"
mkdir -p /etc/nextgen-mc
mkdir -p /var/mc_servers
mkdir -p /var/log/nextgen-mc

GIT_REPO_URL="https://github.com/gohefd321/NeoMinecraftservermanager.git"
TMP_CLONE_DIR="/tmp/neo_mc_clone"

echo "Cloning repository from: ${GIT_REPO_URL} ..."
rm -rf "${TMP_CLONE_DIR}"
git clone --quiet "${GIT_REPO_URL}" "${TMP_CLONE_DIR}"

cp -r "${TMP_CLONE_DIR}"/. "${INSTALL_DIR}/"
rm -rf "${TMP_CLONE_DIR}"
echo -e "${GREEN}Successfully downloaded source code from GitHub.${NC}"

# 5. AppArmor / SELinux 보안 프로파일 처리
echo -e "${BLUE}>>> [4/5] Configuring Security Isolation Profiles...${NC}"
if command -v apparmor_parser &> /dev/null && [ -f "${INSTALL_DIR}/security/apparmor/minecraft-secure.profile" ]; then
    apparmor_parser -r -W "${INSTALL_DIR}/security/apparmor/minecraft-secure.profile" || true
    echo -e "${GREEN}AppArmor Profile [minecraft-secure] registered.${NC}"
elif command -v getenforce &> /dev/null; then
    echo -e "${YELLOW}SELinux detected ($(getenforce)). Ensure proper container policies if required.${NC}"
fi

# 6. Systemd 서비스 템플릿 복사
if [ -f "${INSTALL_DIR}/setup-wizard/service_templates/mc-master.service" ]; then
    cp "${INSTALL_DIR}/setup-wizard/service_templates/mc-master.service" /etc/systemd/system/
    cp "${INSTALL_DIR}/setup-wizard/service_templates/mc-worker.service" /etc/systemd/system/
    systemctl daemon-reload
else
    echo -e "${YELLOW}Warning: Systemd templates not found. Setup wizard might fail if structure is incorrect.${NC}"
fi

# 7. Setup Wizard 컴파일 및 실행
echo -e "${BLUE}>>> [5/5] Launching Web Setup Wizard on port 8080...${NC}"
cd "${INSTALL_DIR}/setup-wizard"

go build -o /tmp/setup-wizard main.go
chmod +x /tmp/setup-wizard

SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")
echo -e "${GREEN}================================================================================"
echo -e "🎉 Installation pre-requisites completed!"
echo -e "👉 Please open your browser and navigate to the Web Setup Wizard:"
echo -e "    🌐  http://${SERVER_IP}:8080   (or http://localhost:8080)"
echo -e "================================================================================${NC}"

# 웹 위저드 프로세스 실행
/tmp/setup-wizard
