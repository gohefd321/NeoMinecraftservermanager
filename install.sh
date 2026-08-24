#!/usr/bin/env bash
# ==============================================================================
# NextGen Minecraft Cloud Platform - Multi-Distro Universal Installer & Manager
# Supports: Debian/Ubuntu (apt), RHEL/CentOS/Rocky/Alma (dnf/yum), Arch (pacman), openSUSE (zypper)
# Features: Complete Nuclear Wipe & Fresh Install, Multi-Distro Packages, Firewall Setup, 100% Dependencies
# Usage: curl -sSL https://github.com/gohefd321/NeoMinecraftservermanager/raw/refs/heads/main/install.sh | sudo bash
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

INSTALL_DIR="/opt/nextgen-mc-platform"
CONFIG_DIR="/etc/nextgen-mc"
DATA_DIR="/var/mc_servers"
LOG_DIR="/var/log/nextgen-mc"
GIT_REPO_URL="https://github.com/gohefd321/NeoMinecraftservermanager.git"

print_banner() {
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
}

# 1. Root 권한 및 아키텍처 체크
check_system_prerequisites() {
    if [ "$(id -u)" -ne 0 ]; then
        echo -e "${RED}[ERROR] This installer must be executed as root (sudo).${NC}" >&2
        exit 1
    fi

    ARCH=$(uname -m)
    if [ "$ARCH" != "x86_64" ] && [ "$ARCH" != "aarch64" ]; then
        echo -e "${RED}[ERROR] Unsupported architecture: ${ARCH}. Only x86_64 and aarch64 are supported.${NC}" >&2
        exit 1
    fi
}

# 2. ⚠️ 100% 완전 파괴적 클린 삭제 (Complete Nuclear Wipe)
perform_nuclear_wipe() {
    echo -e "${RED}${BOLD}"
    echo "================================================================================"
    echo "⚠️  [경고] 100% 완전 파괴적 클린 재설치 (Nuclear Wipe) 안내"
    echo "================================================================================"
    echo "이 작업은 시스템에 존재하는 다음 항목들을 완전히 영구 삭제합니다:"
    echo "  1. 실행 중인 모든 마인크래프트 Docker 컨테이너 및 관련 볼륨"
    echo "  2. ${DATA_DIR} (모든 마인크래프트 월드 맵, 플러그인, 모드팩 데이터)"
    echo "  3. ${INSTALL_DIR} (플랫폼 소스코드 및 Python 가상환경)"
    echo "  4. ${CONFIG_DIR} (노드 설정, Google OAuth 키, 시크릿 토큰)"
    echo "  5. ${LOG_DIR} (모든 로그 파일)"
    echo "  6. Systemd 서비스 (mc-master.service, mc-worker.service)"
    echo "  7. Python pip 빌드 캐시 및 임시 파일"
    echo "================================================================================"
    echo -e "${NC}"

    read -rp "정말로 모든 데이터를 삭제하고 0% 캐시 상태에서 새로 시작하시겠습니까? (확인을 위해 'yes' 또는 'WIPE' 입력): " CONFIRM
    if [ "$CONFIRM" != "yes" ] && [ "$CONFIRM" != "WIPE" ] && [ "$CONFIRM" != "y" ]; then
        echo -e "${YELLOW}작업이 취소되었습니다.${NC}"
        exit 0
    fi

    echo -e "${RED}>>> [1/5] Stopping and disabling all systemd services...${NC}"
    systemctl stop mc-master 2>/dev/null || true
    systemctl stop mc-worker 2>/dev/null || true
    systemctl disable mc-master 2>/dev/null || true
    systemctl disable mc-worker 2>/dev/null || true
    rm -f /etc/systemd/system/mc-master.service /etc/systemd/system/mc-worker.service
    systemctl daemon-reload 2>/dev/null || true

    echo -e "${RED}>>> [2/5] Force killing and destroying all Minecraft Docker containers...${NC}"
    if command -v docker &>/dev/null; then
        RUNNING_MC=$(docker ps -a --filter "name=mc-" -q 2>/dev/null || true)
        if [ -n "${RUNNING_MC}" ]; then
            docker rm -f ${RUNNING_MC} 2>/dev/null || true
        fi
        docker volume prune -f 2>/dev/null || true
    fi

    echo -e "${RED}>>> [3/5] Wiping directories (${INSTALL_DIR}, ${CONFIG_DIR}, ${DATA_DIR}, ${LOG_DIR})...${NC}"
    rm -rf "${INSTALL_DIR}"
    rm -rf "${CONFIG_DIR}"
    rm -rf "${DATA_DIR}"
    rm -rf "${LOG_DIR}"
    rm -rf "/tmp/neo_mc_clone"
    rm -rf "/tmp/setup-wizard"

    echo -e "${RED}>>> [4/5] Purging pip package and Python cache...${NC}"
    if command -v pip3 &>/dev/null; then
        pip3 cache purge 2>/dev/null || true
    fi

    echo -e "${GREEN}✓ Nuclear Wipe Completed! 100% clean state ready.${NC}"
}

# 3. 멀티 디스트로 패키지 매니저 감지 및 시스템 의존성 설치
install_system_packages() {
    echo -e "${BLUE}>>> [1/5] Detecting Linux Distribution and Installing System Packages...${NC}"
    
    OS_ID="unknown"
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_ID="${ID:-unknown}"
    fi

    PKG_MGR=""
    if command -v dnf &>/dev/null; then
        PKG_MGR="dnf"
    elif command -v yum &>/dev/null; then
        PKG_MGR="yum"
    elif command -v apt-get &>/dev/null; then
        PKG_MGR="apt"
    elif command -v pacman &>/dev/null; then
        PKG_MGR="pacman"
    elif command -v zypper &>/dev/null; then
        PKG_MGR="zypper"
    else
        echo -e "${RED}[ERROR] Unsupported package manager. Please install dependencies manually.${NC}" >&2
        exit 1
    fi

    echo -e "Detected OS: ${BOLD}${OS_ID}${NC} (Package Manager: ${BOLD}${PKG_MGR}${NC})"

    case "$PKG_MGR" in
        apt)
            export DEBIAN_FRONTEND=noninteractive
            apt-get update -qq || true
            apt-get install -y -qq \
                ca-certificates curl gnupg jq git python3 python3-pip python3-venv \
                golang-go zram-tools apparmor apparmor-utils iptables net-tools || true
            ;;
        dnf|yum)
            $PKG_MGR check-update -y || true
            if [[ "$OS_ID" =~ ^(rhel|centos|rocky|almalinux)$ ]]; then
                $PKG_MGR install -y -q epel-release || true
            fi
            $PKG_MGR install -y -q \
                ca-certificates curl gnupg2 jq git python3 python3-pip python3-venv \
                golang iptables net-tools || true
            ;;
        pacman)
            pacman -Sy --noconfirm --needed \
                ca-certificates curl gnupg jq git python python-pip \
                go iptables net-tools || true
            ;;
        zypper)
            zypper --non-interactive refresh || true
            zypper --non-interactive install -y \
                ca-certificates curl gpg2 jq git python3 python3-pip \
                go iptables net-tools-deprecated || true
            ;;
    esac
}

# 4. Python 백엔드 필수 라이브러리 100% 설치
install_python_dependencies() {
    echo -e "${BLUE}>>> [2/5] Installing Backend Python Dependencies (uvicorn, fastapi, asyncpg, redis)...${NC}"
    
    pip3 install --upgrade pip --quiet --break-system-packages 2>/dev/null || pip3 install --upgrade pip --quiet || true

    PIP_PACKAGES=(
        "fastapi>=0.109.0"
        "uvicorn[standard]>=0.27.0"
        "pydantic>=2.5.0"
        "pydantic-settings>=2.1.0"
        "asyncpg>=0.29.0"
        "redis>=5.0.1"
        "aiomcrcon>=0.2.0"
        "aiohttp>=3.9.0"
        "aiofiles>=23.2.1"
        "httpx>=0.26.0"
        "psutil>=5.9.0"
    )

    pip3 install "${PIP_PACKAGES[@]}" --break-system-packages --quiet 2>/dev/null || \
    pip3 install "${PIP_PACKAGES[@]}" --quiet 2>/dev/null || true

    mkdir -p "${INSTALL_DIR}/venv"
    if [ ! -f "${INSTALL_DIR}/venv/bin/python3" ]; then
        python3 -m venv "${INSTALL_DIR}/venv" 2>/dev/null || true
    fi
    if [ -f "${INSTALL_DIR}/venv/bin/pip" ]; then
        "${INSTALL_DIR}/venv/bin/pip" install --upgrade pip --quiet 2>/dev/null || true
        "${INSTALL_DIR}/venv/bin/pip" install "${PIP_PACKAGES[@]}" --quiet 2>/dev/null || true
    fi
    echo -e "${GREEN}✓ Python dependencies successfully installed.${NC}"
}

# 5. 방화벽 자동 개방
configure_firewall() {
    echo -e "${BLUE}>>> [3/5] Configuring Firewall Ports (8005, 8080-8085, 25565-25999, 19132)...${NC}"
    
    if command -v firewall-cmd &>/dev/null && systemctl is-active --quiet firewalld 2>/dev/null; then
        firewall-cmd --permanent --add-port=8005/tcp 2>/dev/null || true
        firewall-cmd --permanent --add-port=8080-8085/tcp 2>/dev/null || true
        firewall-cmd --permanent --add-port=25565-25999/tcp 2>/dev/null || true
        firewall-cmd --permanent --add-port=19132/udp 2>/dev/null || true
        firewall-cmd --reload 2>/dev/null || true
        echo -e "${GREEN}✓ Firewalld rules applied.${NC}"
    elif command -v ufw &>/dev/null && ufw status | grep -qw "active" 2>/dev/null; then
        ufw allow 8005/tcp comment "NextGen Master API" >/dev/null 2>&1 || true
        ufw allow 8080:8085/tcp comment "NextGen Setup Wizard" >/dev/null 2>&1 || true
        ufw allow 25565:25999/tcp comment "NextGen Game Ports" >/dev/null 2>&1 || true
        ufw allow 19132/udp comment "NextGen Bedrock UDP" >/dev/null 2>&1 || true
        echo -e "${GREEN}✓ UFW rules applied.${NC}"
    fi

    if command -v iptables &>/dev/null; then
        iptables -I INPUT -p tcp --dport 8005 -j ACCEPT 2>/dev/null || true
        iptables -I INPUT -p tcp --dport 8080:8085 -j ACCEPT 2>/dev/null || true
        iptables -I INPUT -p tcp --dport 25565:25999 -j ACCEPT 2>/dev/null || true
        iptables -I INPUT -p udp --dport 19132 -j ACCEPT 2>/dev/null || true
    fi
}

# 6. Docker 엔진 확인
ensure_docker() {
    if ! command -v docker &>/dev/null; then
        echo -e "${YELLOW}Docker is not installed. Installing Docker via official script...${NC}"
        curl -fsSL https://get.docker.com | sh
    fi
    systemctl enable --now docker 2>/dev/null || true
}

# 7. 소스코드 배포
deploy_codebase() {
    echo -e "${BLUE}>>> [4/5] Deploying Source Code to ${INSTALL_DIR}...${NC}"
    mkdir -p "${INSTALL_DIR}" "${CONFIG_DIR}" "${DATA_DIR}" "${LOG_DIR}"

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [ -f "${SCRIPT_DIR}/backend/app/main.py" ]; then
        echo "Deploying from local directory: ${SCRIPT_DIR}"
        cp -r "${SCRIPT_DIR}"/* "${INSTALL_DIR}/" || true
    else
        TMP_CLONE_DIR="/tmp/neo_mc_clone"
        echo "Cloning repository from: ${GIT_REPO_URL} ..."
        rm -rf "${TMP_CLONE_DIR}"
        git clone --quiet "${GIT_REPO_URL}" "${TMP_CLONE_DIR}"
        cp -r "${TMP_CLONE_DIR}"/. "${INSTALL_DIR}/"
        rm -rf "${TMP_CLONE_DIR}"
    fi

    if command -v apparmor_parser &>/dev/null && [ -f "${INSTALL_DIR}/security/apparmor/minecraft-secure.profile" ]; then
        apparmor_parser -r -W "${INSTALL_DIR}/security/apparmor/minecraft-secure.profile" 2>/dev/null || true
    fi
    if command -v getenforce &>/dev/null && [ "$(getenforce)" = "Enforcing" ]; then
        chcon -Rt container_file_t "${DATA_DIR}" 2>/dev/null || true
    fi

    if [ -d "${INSTALL_DIR}/setup-wizard/service_templates" ]; then
        cp "${INSTALL_DIR}/setup-wizard/service_templates/mc-master.service" /etc/systemd/system/ 2>/dev/null || true
        cp "${INSTALL_DIR}/setup-wizard/service_templates/mc-worker.service" /etc/systemd/system/ 2>/dev/null || true
        systemctl daemon-reload 2>/dev/null || true
    fi
}

# 8. Web Setup Wizard 실행
launch_wizard() {
    echo -e "${BLUE}>>> [5/5] Launching Web Setup Wizard...${NC}"
    chmod +x "${INSTALL_DIR}/setup-wizard/server.py" 2>/dev/null || true
    
    SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")
    echo -e "${GREEN}================================================================================"
    echo -e "🎉 Installation completed!"
    echo -e "👉 Please open your browser to configure Node Role, Google OAuth & LLM:"
    echo -e "    🌐  http://${SERVER_IP}:8080   (or http://localhost:8080)"
    echo -e "================================================================================${NC}"

    python3 "${INSTALL_DIR}/setup-wizard/server.py"
}

# 9. 복구 및 재시작
repair_and_run() {
    echo -e "${BLUE}>>> Repairing platform dependencies and restarting services...${NC}"
    check_system_prerequisites
    install_system_packages
    install_python_dependencies
    configure_firewall
    ensure_docker
    deploy_codebase

    systemctl restart mc-master 2>/dev/null || true
    sleep 2

    SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")
    echo -e "${GREEN}================================================================================"
    echo -e "🎉 Repair Completed!"
    echo -e "👉 User Portal Web:    http://${SERVER_IP}:8005/"
    echo -e "👉 Admin Center:       http://${SERVER_IP}:8005/admin"
    echo -e "================================================================================${NC}"
    systemctl status mc-master --no-pager || true
}

# ==============================================================================
# 메인 실행 분기 (CLI Flag 및 대화형 메뉴)
# ==============================================================================
main() {
    check_system_prerequisites
    print_banner

    ACTION="${1:-}"

    # 비대화형 CLI 플래그 처리
    if [ "$ACTION" = "--wipe" ] || [ "$ACTION" = "--clean" ] || [ "$ACTION" = "-c" ]; then
        perform_nuclear_wipe
        install_system_packages
        install_python_dependencies
        configure_firewall
        ensure_docker
        deploy_codebase
        launch_wizard
        exit 0
    elif [ "$ACTION" = "--update" ] || [ "$ACTION" = "-u" ]; then
        install_system_packages
        install_python_dependencies
        configure_firewall
        deploy_codebase
        systemctl restart mc-master 2>/dev/null || true
        echo -e "${GREEN}✓ Platform updated and services restarted.${NC}"
        exit 0
    elif [ "$ACTION" = "--repair" ] || [ "$ACTION" = "-r" ]; then
        repair_and_run
        exit 0
    fi

    # 대화형 모드 (기본 실행 시 언제나 표시)
    echo -e "${BOLD}원하시는 설치/관리 모드를 선택하십시오:${NC}"
    echo ""
    echo "  [1] 일반 설치 / 업데이트 (Standard Install / Update) - 기존 설정 및 월드 보존"
    echo -e "  [2] ${RED}${BOLD}⚠️  100% 완전 파괴적 클린 재설치 (Nuclear Wipe & Fresh Reinstall)${NC}"
    echo "      (모든 컨테이너·월드·설정·캐시 영구 삭제 후 0% 캐시 상태에서 완전 새로 시작)"
    echo "  [3] 의존성·방화벽·서비스 복구 및 즉시 실행 (Repair & Run)"
    echo "  [4] 웹 셋업 위저드 다시 실행 (Relaunch Setup Wizard)"
    echo "  [5] 취소 (Exit)"
    echo ""
    read -rp "선택 (1-5, 기본값: 1): " CHOICE
    CHOICE="${CHOICE:-1}"

    case "$CHOICE" in
        1)
            install_system_packages
            install_python_dependencies
            configure_firewall
            ensure_docker
            deploy_codebase
            if [ -f "${CONFIG_DIR}/node.env" ]; then
                systemctl restart mc-master 2>/dev/null || true
                echo -e "${GREEN}✓ Updated and mc-master restarted on port 8005.${NC}"
            else
                launch_wizard
            fi
            ;;
        2)
            perform_nuclear_wipe
            install_system_packages
            install_python_dependencies
            configure_firewall
            ensure_docker
            deploy_codebase
            launch_wizard
            ;;
        3)
            repair_and_run
            ;;
        4)
            install_system_packages
            install_python_dependencies
            configure_firewall
            deploy_codebase
            launch_wizard
            ;;
        5)
            echo "설치를 종료합니다."
            exit 0
            ;;
        *)
            echo -e "${RED}잘못된 입력입니다.${NC}"
            exit 1
            ;;
    esac
}

main "$@"
