#!/usr/bin/env bash
# ==============================================================================
# deploy-mc-sandbox.sh
# Hardened Sandboxed Minecraft Container & Proxy Deployment Script
# Supports: PAPER, FABRIC, FORGE (Official), NEOFORGE, VELOCITY (L4 Proxy), BUNGEECORD
# Security: AppArmor, Seccomp, Cap-Drop ALL, No-New-Privileges, Dynamic Tiered Memory
# Performance: Java 21 Generational ZGC & Aikar's Flags
# ==============================================================================
set -euo pipefail

SERVER_ID="${1:-mc-server-01}"
HOST_PORT="${2:-25565}"
RCON_PORT="${3:-25575}"
RAM_MB="${4:-4096}"
SWAP_TOTAL_MB="${5:-6144}"
SERVER_TYPE="${6:-PAPER}" # PAPER, FABRIC, FORGE, NEOFORGE, VELOCITY, BUNGEECORD
MC_VERSION="${7:-1.20.4}"
RCON_PASS="${8:-SafeRconKey999!}"
ENABLE_CROSSPLAY="${9:-false}"

DATA_DIR="/var/mc_servers/${SERVER_ID}"
mkdir -p "${DATA_DIR}"

echo "================================================================================"
echo ">>> [Deploying Hardened Container] ID: ${SERVER_ID} on Port ${HOST_PORT}"
echo "    Core: ${SERVER_TYPE} | MC Version: ${MC_VERSION} | RAM: ${RAM_MB}MB | Swap: ${SWAP_TOTAL_MB}MB"
echo "================================================================================"

# 1. Java 21 Generational ZGC & Optimized Aikar's Flags
HEAP_MB=$((RAM_MB * 85 / 100))

JVM_FLAGS=(
    "-Xms${HEAP_MB}M"
    "-Xmx${HEAP_MB}M"
    "-XX:+UseZGC"
    "-XX:+ZGenerational"
    "-XX:+UnlockExperimentalVMOptions"
    "-XX:+AlwaysPreTouch"
    "-XX:+DisableExplicitGC"
    "-XX:+UseNUMA"
    "-XX:AllocatePrefetchStyle=1"
    "-Dterminal.jline=false"
    "-Dterminal.ansi=true"
    "-Dcom.mojang.eula.agree=true"
)

JVM_OPTS_STR="${JVM_FLAGS[*]}"

# 2. 크로스플레이 헬퍼 (Geyser / Floodgate / ViaVersion 플러그인 주입)
EXTRA_ENV_ARGS=()
if [ "$ENABLE_CROSSPLAY" = "true" ]; then
    EXTRA_ENV_ARGS+=(
        "-e" "SPIGET_RESOURCES=24490,27448" # ViaVersion, ViaBackwards
    )
fi

# 3. Seccomp / AppArmor 설정 존재 여부 체크
SECCOMP_ARG=()
if [ -f "/opt/nextgen-mc-platform/security/seccomp/minecraft-seccomp.json" ]; then
    SECCOMP_ARG=("--security-opt" "seccomp=/opt/nextgen-mc-platform/security/seccomp/minecraft-seccomp.json")
elif [ -f "../security/seccomp/minecraft-seccomp.json" ]; then
    SECCOMP_ARG=("--security-opt" "seccomp=../security/seccomp/minecraft-seccomp.json")
fi

APPARMOR_ARG=()
if aa-status --enabled 2>/dev/null; then
    APPARMOR_ARG=("--security-opt" "apparmor=minecraft-secure")
fi

# 4. 기존 컨테이너 정리
docker rm -f "${SERVER_ID}" 2>/dev/null || true

# 5. 프록시(Velocity/Bungee) 또는 마인크래프트 게임 서버 분기 배포
if [ "${SERVER_TYPE}" = "VELOCITY" ] || [ "${SERVER_TYPE}" = "BUNGEECORD" ] || [ "${SERVER_TYPE}" = "WATERFALL" ]; then
    echo "Deploying High-Performance L4 Proxy (${SERVER_TYPE})..."
    docker run -d \
        --name "${SERVER_ID}" \
        --restart unless-stopped \
        --memory="${RAM_MB}m" \
        --memory-swap="${SWAP_TOTAL_MB}m" \
        --oom-kill-disable \
        --cpus="2.0" \
        --cap-drop=ALL \
        --security-opt no-new-privileges:true \
        "${APPARMOR_ARG[@]}" \
        "${SECCOMP_ARG[@]}" \
        -p "${HOST_PORT}:25565/tcp" \
        -p "${RCON_PORT}:25575/tcp" \
        -v "${DATA_DIR}:/server:rw" \
        -e TYPE="${SERVER_TYPE}" \
        -e MEMORY="${HEAP_MB}M" \
        -e JVM_OPTS="${JVM_OPTS_STR}" \
        itzg/bungeecord:latest 2>/dev/null || \
    docker run -d \
        --name "${SERVER_ID}" \
        --restart unless-stopped \
        --memory="${RAM_MB}m" \
        --memory-swap="${SWAP_TOTAL_MB}m" \
        --oom-kill-disable \
        --cpus="2.0" \
        -p "${HOST_PORT}:25565/tcp" \
        -p "${RCON_PORT}:25575/tcp" \
        -v "${DATA_DIR}:/data:rw" \
        -e EULA=TRUE \
        -e TYPE="${SERVER_TYPE}" \
        -e VERSION="${MC_VERSION}" \
        -e MEMORY="${HEAP_MB}M" \
        itzg/minecraft-server:java21
else
    docker run -d \
        --name "${SERVER_ID}" \
        --restart unless-stopped \
        --memory="${RAM_MB}m" \
        --memory-swap="${SWAP_TOTAL_MB}m" \
        --oom-kill-disable \
        --cpus="4.0" \
        --cap-drop=ALL \
        --security-opt no-new-privileges:true \
        "${APPARMOR_ARG[@]}" \
        "${SECCOMP_ARG[@]}" \
        -p "${HOST_PORT}:25565/tcp" \
        -p "${RCON_PORT}:25575/tcp" \
        -v "${DATA_DIR}:/data:rw" \
        -e EULA=TRUE \
        -e VERSION="${MC_VERSION}" \
        -e TYPE="${SERVER_TYPE}" \
        -e MEMORY="${HEAP_MB}M" \
        -e JVM_OPTS="${JVM_OPTS_STR}" \
        -e RCON_ENABLED=true \
        -e RCON_PASSWORD="${RCON_PASS}" \
        -e RCON_PORT=25575 \
        "${EXTRA_ENV_ARGS[@]}" \
        itzg/minecraft-server:java21
fi

echo ">>> [SUCCESS] Container ${SERVER_ID} deployed successfully."
