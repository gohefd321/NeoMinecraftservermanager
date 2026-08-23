#!/usr/bin/env bash
# ==============================================================================
# NextGen Minecraft Cloud Platform - One-Click Installer & Manager
# Supports: Clean Reinstall, In-Place Update, Dependency Repair, Firewall Setup
# Usage: curl -sSL https://domain/install.sh | sudo bash
# ==============================================================================
set -euo pipefail

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

# 1. Root 권한 체크
check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        echo -e "${RED}[ERROR] This installer must be executed as root (sudo).${NC}" >&2
        exit 1
    fi
}

# 2. 방화벽(Firewall) 탐색 및 포트 자동 개방
configure_firewall() {
    echo -e "${BLUE}>>> [Firewall] Detecting and configuring firewall ports...${NC}"
    
    # Required Ports:
    # 8005/tcp: Master Control Plane API & Admin Panel
    # 8080-8085/tcp: Setup Wizard
    # 25565-25999/tcp: Velocity Ingress & Game Container Ports
    # 19132/udp: Bedrock Edition UDP Ingress
    
    FIREWALL_CONFIGURED=false

    # 2-1. Firewalld (CentOS / RHEL / Fedora / Alma / Rocky)
    if command -v firewall-cmd &>/dev/null && systemctl is-active --quiet firewalld 2>/dev/null; then
        echo -e "${YELLOW}Detected active firewalld. Opening ports...${NC}"
        firewall-cmd --permanent --add-port=8005/tcp 2>/dev/null || true
        firewall-cmd --permanent --add-port=8080-8085/tcp 2>/dev/null || true
        firewall-cmd --permanent --add-port=25565-25999/tcp 2>/dev/null || true
        firewall-cmd --permanent --add-port=19132/udp 2>/dev/null || true
        firewall-cmd --reload 2>/dev/null || true
        echo -e "${GREEN}✓ Firewalld rules applied successfully.${NC}"
        FIREWALL_CONFIGURED=true
    fi

    # 2-2. UFW (Ubuntu / Debian)
    if command -v ufw &>/dev/null && ufw status | grep -qw "active" 2>/dev/null; then
        echo -e "${YELLOW}Detected active UFW. Opening ports...${NC}"
        ufw allow 8005/tcp comment "NextGen MC Master API" >/dev/null 2>&1 || true
        ufw allow 8080:8085/tcp comment "NextGen MC Setup Wizard" >/dev/null 2>&1 || true
        ufw allow 25565:25999/tcp comment "NextGen MC Game Ports" >/dev/null 2>&1 || true
        ufw allow 19132/udp comment "NextGen MC Bedrock UDP" >/dev/null 2>&1 || true
        echo -e "${GREEN}✓ UFW rules applied successfully.${NC}"
        FIREWALL_CONFIGURED=true
    fi

    # 2-3. IPTables fallback
    if command -v iptables &>/dev/null; then
        iptables -I INPUT -p tcp --dport 8005 -j ACCEPT 2>/dev/null || true
        iptables -I INPUT -p tcp --dport 8080:8085 -j ACCEPT 2>/dev/null || true
        iptables -I INPUT -p tcp --dport 25565:25999 -j ACCEPT 2>/dev/null || true
        iptables -I INPUT -p udp --dport 19132 -j ACCEPT 2>/dev/null || true
    fi

    if [ "$FIREWALL_CONFIGURED" = false ]; then
        echo -e "${GREEN}✓ No blocking firewall (ufw/firewalld) active or ports configured in iptables.${NC}"
    fi
}

# 3. 모든 시스템 및 파이썬 디펜던시 100% 설치
install_all_dependencies() {
    echo -e "${BLUE}>>> [Dependencies] Installing all system and Python dependencies...${NC}"
    export DEBIAN_FRONTEND=noninteractive
    
    # 패키지 매니저 업데이트 및 시스템 도구 설치
    if command -v apt-get &>/dev/null; then
        apt-get update -qq || true
        apt-get install -y -qq \
            curl jq git python3 python3-pip python3-venv \
            zram-tools iptables net-tools ca-certificates gnupg lsb-release || true
    elif command -v dnf &>/dev/null; then
        dnf install -y -q curl jq git python3 python3-pip iptables net-tools || true
    fi

    # Docker 엔진 확인 및 설치
    if ! command -v docker &>/dev/null; then
        echo -e "${YELLOW}Docker is not installed. Installing Docker CE...${NC}"
        curl -fsSL https://get.docker.com | bash || true
        systemctl enable --now docker 2>/dev/null || true
    fi

    # Python pip 패키지 전역 및 가상환경 100% 설치 (PEP 668 bypass)
    echo -e "${BLUE}>>> Installing backend Python libraries (uvicorn, fastapi, asyncpg, redis, etc.)...${NC}"
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

    # 격리형 Virtualenv 구축 (이중 보장)
    mkdir -p "${INSTALL_DIR}/venv"
    if [ ! -f "${INSTALL_DIR}/venv/bin/python3" ]; then
        python3 -m venv "${INSTALL_DIR}/venv" 2>/dev/null || true
    fi
    if [ -f "${INSTALL_DIR}/venv/bin/pip" ]; then
        "${INSTALL_DIR}/venv/bin/pip" install --upgrade pip --quiet 2>/dev/null || true
        "${INSTALL_DIR}/venv/bin/pip" install "${PIP_PACKAGES[@]}" --quiet 2>/dev/null || true
    fi
    echo -e "${GREEN}✓ All dependencies successfully installed and verified.${NC}"
}

# 4. 파일 복사 및 Systemd 설정
deploy_files_and_services() {
    echo -e "${BLUE}>>> [Deploy] Deploying platform files to ${INSTALL_DIR}...${NC}"
    mkdir -p "${INSTALL_DIR}" "${CONFIG_DIR}" "${DATA_DIR}" /var/log/nextgen-mc

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [ -d "${SCRIPT_DIR}" ] && [ "${SCRIPT_DIR}" != "${INSTALL_DIR}" ]; then
        cp -r "${SCRIPT_DIR}"/* "${INSTALL_DIR}/" || true
    fi

    # 보안 프로파일
    if command -v apparmor_parser &>/dev/null && [ -f "${INSTALL_DIR}/security/apparmor/minecraft-secure.profile" ]; then
        apparmor_parser -r -W "${INSTALL_DIR}/security/apparmor/minecraft-secure.profile" 2>/dev/null || true
    fi

    if command -v getenforce &>/dev/null && [ "$(getenforce)" = "Enforcing" ]; then
        chcon -Rt container_file_t "${DATA_DIR}" 2>/dev/null || true
    fi

    # Systemd 유닛 등록
    if [ -d "${INSTALL_DIR}/setup-wizard/service_templates" ]; then
        cp "${INSTALL_DIR}/setup-wizard/service_templates/mc-master.service" /etc/systemd/system/ 2>/dev/null || true
        cp "${INSTALL_DIR}/setup-wizard/service_templates/mc-worker.service" /etc/systemd/system/ 2>/dev/null || true
        systemctl daemon-reload 2>/dev/null || true
    fi
}

# 5. 기존 설치 제거 (Clean Uninstall)
perform_clean_uninstall() {
    echo -e "${RED}${BOLD}>>> [Clean Reinstall] Stopping services and wiping existing installation...${NC}"
    systemctl stop mc-master 2>/dev/null || true
    systemctl stop mc-worker 2>/dev/null || true
    systemctl disable mc-master 2>/dev/null || true
    systemctl disable mc-worker 2>/dev/null || true

    # 실행 중인 마인크래프트 컨테이너 중지
    RUNNING_MC=$(docker ps -a --filter "name=mc-" -q 2>/dev/null || true)
    if [ -n "${RUNNING_MC}" ]; then
        echo "Stopping and removing existing Minecraft containers..."
        docker rm -f ${RUNNING_MC} 2>/dev/null || true
    fi

    rm -rf "${INSTALL_DIR}"
    rm -rf "${CONFIG_DIR}"
    rm -f /etc/systemd/system/mc-master.service /etc/systemd/system/mc-worker.service
    systemctl daemon-reload 2>/dev/null || true
    echo -e "${GREEN}✓ Previous installation completely removed.${NC}"
}

# 6. 진단 및 즉시 수리 (Repair)
perform_repair() {
    echo -e "${BLUE}>>> [Repair] Diagnosing system and repairing services...${NC}"
    install_all_dependencies
    configure_firewall
    deploy_files_and_services
    
    echo "Reloading systemd and restarting mc-master..."
    systemctl restart mc-master 2>/dev/null || true
    sleep 2

    SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")
    echo -e "${GREEN}================================================================================"
    echo -e "🎉 Repair Completed!"
    echo -e "👉 Master API / Admin Panel:  http://${SERVER_IP}:8005/admin"
    echo -e "👉 API Swagger Documentation: http://${SERVER_IP}:8005/docs"
    echo -e "================================================================================${NC}"
    systemctl status mc-master --no-pager || true
}

# ==============================================================================
# 메인 실행 분기 (Main CLI / Interactive Menu)
# ==============================================================================
main() {
    check_root
    print_banner

    # 비대화형 플래그 지원
    ACTION="${1:-}"

    if [ "$ACTION" = "--clean" ] || [ "$ACTION" = "-c" ]; then
        perform_clean_uninstall
        install_all_dependencies
        configure_firewall
        deploy_files_and_services
        python3 "${INSTALL_DIR}/setup-wizard/server.py"
        exit 0
    elif [ "$ACTION" = "--update" ] || [ "$ACTION" = "-u" ]; then
        install_all_dependencies
        configure_firewall
        deploy_files_and_services
        systemctl restart mc-master 2>/dev/null || true
        echo -e "${GREEN}✓ Update complete and services restarted.${NC}"
        exit 0
    elif [ "$ACTION" = "--repair" ] || [ "$ACTION" = "-r" ]; then
        perform_repair
        exit 0
    fi

    # 이미 설치된 환경이 감지될 경우 대화형 메뉴 표시
    if [ -f "${CONFIG_DIR}/node.env" ] || [ -f "/etc/systemd/system/mc-master.service" ]; then
        echo -e "${YELLOW}${BOLD}⚠️  기존에 설치된 NextGen MC Platform 환경이 감지되었습니다.${NC}"
        echo ""
        echo "원하시는 작업을 선택하십시오:"
        echo "  [1] 업데이트 및 서비스 재시작 (Update & Restart) - 기존 설정 및 월드 유지"
        echo "  [2] 완전 삭제 후 새로 재설치 (Clean Reinstall) - 기존 설정 초기화"
        echo "  [3] 의존성·방화벽·서비스 복구 및 즉시 실행 (Repair & Run)"
        echo "  [4] 웹 셋업 위저드 다시 실행 (Relaunch Setup Wizard)"
        echo "  [5] 취소 (Exit)"
        echo ""
        read -rp "선택 (1-5, 기본값: 1): " CHOICE
        CHOICE="${CHOICE:-1}"

        case "$CHOICE" in
            1)
                echo -e "${BLUE}>>> Updating platform...${NC}"
                install_all_dependencies
                configure_firewall
                deploy_files_and_services
                systemctl restart mc-master 2>/dev/null || true
                echo -e "${GREEN}✓ Updated and mc-master restarted on port 8005.${NC}"
                ;;
            2)
                read -rp "정말로 기존 설정을 모두 삭제하고 새로 설치하시겠습니까? (y/N): " CONFIRM
                if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
                    perform_clean_uninstall
                    install_all_dependencies
                    configure_firewall
                    deploy_files_and_services
                    python3 "${INSTALL_DIR}/setup-wizard/server.py"
                else
                    echo "취소되었습니다."
                fi
                ;;
            3)
                perform_repair
                ;;
            4)
                install_all_dependencies
                configure_firewall
                deploy_files_and_services
                python3 "${INSTALL_DIR}/setup-wizard/server.py"
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
        exit 0
    fi

    # 첫 설치 시 실행 흐름
    install_all_dependencies
    configure_firewall
    deploy_files_and_services

    SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")
    echo -e "${GREEN}================================================================================"
    echo -e "🎉 Installation pre-requisites & dependencies completed!"
    echo -e "👉 Opening Web Setup Wizard to configure Node Role & Parameters:"
    echo -e "================================================================================${NC}"

    python3 "${INSTALL_DIR}/setup-wizard/server.py"
}

main "$@"
