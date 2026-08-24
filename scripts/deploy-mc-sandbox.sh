#!/usr/bin/env bash
# ==============================================================================
# deploy-mc-sandbox.sh
# Hardened Sandboxed Minecraft Container & Proxy Deployment Script
# Supports All Server Cores:
# - Optimization: PAPER, PURPUR, FOLIA (Multi-threaded Region)
# - Modded: FABRIC, FORGE (Official), NEOFORGE, SPONGE (SpongeVanilla)
# - Official & Classic: VANILLA (Mojang Official with Snapshot support), SPIGOT, CRAFTBUKKIT
# - Proxies: VELOCITY (L4 Ingress Proxy), BUNGEECORD, WATERFALL
# ==============================================================================
set -euo pipefail

SERVER_ID="${1:-mc-server-01}"
HOST_PORT="${2:-25565}"
RCON_PORT="${3:-25575}"
RAM_MB="${4:-4096}"
SWAP_TOTAL_MB="${5:-6144}"
SERVER_TYPE="${6:-PAPER}"
MC_VERSION="${7:-26.2}"
RCON_PASS="${8:-SafeRconKey999!}"
ENABLE_CROSSPLAY="${9:-false}"
CPU_CORES="${10:-2}"
CPUSET_CPUS="${11:-}"

# CPU Pinning 옵션 처리 (지정된 경우에만 cpuset-cpus 전달)
CPUSET_DOCKER_ARG=()
if [ -n "${CPUSET_CPUS}" ]; then
    CPUSET_DOCKER_ARG=(--cpuset-cpus="${CPUSET_CPUS}")
fi

# 데이터 저장 디렉토리 생성 (권한 실패 시 fallback)
DATA_DIR="/var/mc_servers/${SERVER_ID}"
if ! mkdir -p "${DATA_DIR}" 2>/dev/null; then
    DATA_DIR="/tmp/mc_servers/${SERVER_ID}"
    mkdir -p "${DATA_DIR}" 2>/dev/null || true
fi

echo "================================================================================"
echo ">>> [Deploying Hardened Container] ID: ${SERVER_ID} on Port ${HOST_PORT}"
echo "    Core: ${SERVER_TYPE} | MC Version: ${MC_VERSION} | RAM: ${RAM_MB}MB | Swap: ${SWAP_TOTAL_MB}MB"
echo "================================================================================"

# 1. Java 21+ Generational ZGC & Optimized Aikar's Flags
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

if [ "${SERVER_TYPE}" = "FOLIA" ]; then
    JVM_FLAGS+=("-Dpaper.use-optimized-compact=true")
fi

JVM_OPTS_STR="${JVM_FLAGS[*]}"

# 2. 크로스플레이 헬퍼 (Geyser / Floodgate / ViaVersion 플러그인 주입)
EXTRA_ENV_ARGS=()
if [ "$ENABLE_CROSSPLAY" = "true" ] && [ "${SERVER_TYPE}" != "VANILLA" ]; then
    EXTRA_ENV_ARGS+=(
        "-e" "SPIGET_RESOURCES=24490,27448"
    )
fi

# 3. itzg TYPE 매핑 변환
ITZG_TYPE="${SERVER_TYPE}"
case "${SERVER_TYPE}" in
    SPONGE)
        ITZG_TYPE="SPONGEVANILLA"
        ;;
    BUNGEECORD)
        ITZG_TYPE="WATERFALL"
        ;;
    VANILLA)
        ITZG_TYPE="VANILLA"
        ;;
    *)
        ITZG_TYPE="${SERVER_TYPE}"
        ;;
esac

# 4. Seccomp / AppArmor 설정 존재 여부 체크
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

# 5. 기존 컨테이너 정리
docker rm -f "${SERVER_ID}" 2>/dev/null || true

# 6. 프록시(Velocity/Bungee) 또는 게임 서버 분기 배포
if [ "${SERVER_TYPE}" = "VELOCITY" ] || [ "${SERVER_TYPE}" = "BUNGEECORD" ] || [ "${SERVER_TYPE}" = "WATERFALL" ]; then
    echo "Deploying High-Performance L4 Proxy (${SERVER_TYPE}) with ${CPU_CORES} vCPUs (Pinning: ${CPUSET_CPUS:-All})..."
    docker run -d \
        --name "${SERVER_ID}" \
        --restart unless-stopped \
        --memory="${RAM_MB}m" \
        --memory-swap="${SWAP_TOTAL_MB}m" \
        --oom-kill-disable \
        --cpus="${CPU_CORES}" \
        "${CPUSET_DOCKER_ARG[@]}" \
        --cap-drop=ALL \
        --security-opt no-new-privileges:true \
        "${APPARMOR_ARG[@]}" \
        "${SECCOMP_ARG[@]}" \
        -p "${HOST_PORT}:25565/tcp" \
        -p "${RCON_PORT}:25575/tcp" \
        -v "${DATA_DIR}:/server:rw" \
        -e TYPE="${ITZG_TYPE}" \
        -e MEMORY="${HEAP_MB}M" \
        -e JVM_OPTS="${JVM_OPTS_STR}" \
        itzg/bungeecord:latest 2>/dev/null || \
    docker run -d \
        --name "${SERVER_ID}" \
        --restart unless-stopped \
        --memory="${RAM_MB}m" \
        --memory-swap="${SWAP_TOTAL_MB}m" \
        --oom-kill-disable \
        --cpus="${CPU_CORES}" \
        "${CPUSET_DOCKER_ARG[@]}" \
        -p "${HOST_PORT}:25565/tcp" \
        -p "${RCON_PORT}:25575/tcp" \
        -v "${DATA_DIR}:/data:rw" \
        -e EULA=TRUE \
        -e TYPE="${ITZG_TYPE}" \
        -e VERSION="${MC_VERSION}" \
        -e MEMORY="${HEAP_MB}M" \
        itzg/minecraft-server:latest
else
    echo "Deploying Isolated Minecraft Game Container (${SERVER_TYPE}) with ${CPU_CORES} vCPUs (Pinning: ${CPUSET_CPUS:-All})..."
    docker run -d \
        --name "${SERVER_ID}" \
        --restart unless-stopped \
        --memory="${RAM_MB}m" \
        --memory-swap="${SWAP_TOTAL_MB}m" \
        --oom-kill-disable \
        --cpus="${CPU_CORES}" \
        "${CPUSET_DOCKER_ARG[@]}" \
        --cap-drop=ALL \
        --security-opt no-new-privileges:true \
        "${APPARMOR_ARG[@]}" \
        "${SECCOMP_ARG[@]}" \
        -p "${HOST_PORT}:25565/tcp" \
        -p "${RCON_PORT}:25575/tcp" \
        -v "${DATA_DIR}:/data:rw" \
        -e EULA=TRUE \
        -e VERSION="${MC_VERSION}" \
        -e TYPE="${ITZG_TYPE}" \
        -e MEMORY="${HEAP_MB}M" \
        -e JVM_OPTS="${JVM_OPTS_STR}" \
        -e RCON_ENABLED=true \
        -e RCON_PASSWORD="${RCON_PASS}" \
        -e RCON_PORT=25575 \
        "${EXTRA_ENV_ARGS[@]}" \
        itzg/minecraft-server:latest
fi

echo ">>> [SUCCESS] Container ${SERVER_ID} (${SERVER_TYPE} ${MC_VERSION}) deployed successfully."
