#!/usr/bin/env bash
# ==============================================================================
# rootless-docker-setup.sh
# Rootless Docker Installer & Privilege Separation Configuration
# ==============================================================================
set -euo pipefail

TARGET_USER="${1:-mcnode}"

echo ">>> [1/3] Creating dedicated non-root execution user: ${TARGET_USER}..."
if ! id -u "${TARGET_USER}" >/dev/null 2>&1; then
    useradd -m -s /bin/bash -u 1500 "${TARGET_USER}"
fi

# subuid, subgid 설정
echo ">>> [2/3] Configuring subuid/subgid subordinate mappings..."
if ! grep -q "^${TARGET_USER}:" /etc/subuid; then
    echo "${TARGET_USER}:100000:65536" >> /etc/subuid
fi
if ! grep -q "^${TARGET_USER}:" /etc/subgid; then
    echo "${TARGET_USER}:100000:65536" >> /etc/subgid
fi

# systemd lingering 활성화 (로그아웃 후에도 데몬 유지)
loginctl enable-linger "${TARGET_USER}" || true

# Rootless Docker 필수 패키지 설치
echo ">>> [3/3] Installing rootless prerequisites..."
apt-get install -y -qq uidmap dbus-user-session fuse-overlayfs iptables slirp4netns

echo "Rootless environment prepared for user ${TARGET_USER}."
echo "To initialize Docker rootless daemon under this user:"
echo "  sudo -u ${TARGET_USER} dockerd-rootless-setuptool.sh install"
