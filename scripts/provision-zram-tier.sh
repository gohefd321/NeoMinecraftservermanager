#!/usr/bin/env bash
# ==============================================================================
# provision-zram-tier.sh
# Tiered Memory Architecture Provisioning:
# Tier 1 (RAM) -> Tier 2 (ZRAM LZ4/ZSTD, Priority 32767) -> Tier 3 (NVMe Swap, Priority 10)
# ==============================================================================
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "[ERROR] This script requires root privileges." >&2
    exit 1
fi

echo "================================================================================"
echo ">>> [1/4] Applying Linux Kernel Virtual Memory & I/O Tuning..."
echo "================================================================================"

cat << 'EOF' > /etc/sysctl.d/99-tiered-memory.conf
# Aggressively utilize ZRAM compressed RAM swap before hitting NVMe swap
vm.swappiness = 130
vm.vfs_cache_pressure = 50
vm.dirty_background_ratio = 5
vm.dirty_ratio = 10
# Avoid compaction stalls in high memory allocation workloads
vm.extfrag_threshold = 500
# Enable cgroup memory pressure events
vm.zone_reclaim_mode = 0
EOF

sysctl --system > /dev/null

echo "================================================================================"
echo ">>> [2/4] Initializing Tier 2 ZRAM Block Device (LZ4, Priority 32767)..."
echo "================================================================================"

# Unload existing zram if active
swapoff -a || true
modprobe -r zram 2>/dev/null || true
modprobe zram num_devices=1

# Calculate 60% of total physical RAM for ZRAM compressed block
TOTAL_MEM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
ZRAM_SIZE_KB=$((TOTAL_MEM_KB * 60 / 100))

# Configure zram0 with LZ4 compression algorithm
zramctl /dev/zram0 --algorithm lz4 --size "${ZRAM_SIZE_KB}K"
mkswap /dev/zram0 > /dev/null
# Activate ZRAM with the highest swap priority (32767)
swapon -p 32767 /dev/zram0

echo "[SUCCESS] ZRAM Tier 2 activated:"
zramctl

echo "================================================================================"
echo ">>> [3/4] Initializing Tier 3 NVMe Fallback Swap (Priority 10)..."
echo "================================================================================"

NVME_SWAPFILE="/var/swap_nvme_tier3.img"
if [ ! -f "$NVME_SWAPFILE" ]; then
    echo "Allocating 12GB NVMe Swapfile at ${NVME_SWAPFILE}..."
    fallocate -l 12G "$NVME_SWAPFILE" || dd if=/dev/zero of="$NVME_SWAPFILE" bs=1M count=12288
    chmod 600 "$NVME_SWAPFILE"
    mkswap "$NVME_SWAPFILE" > /dev/null
fi

# Activate NVMe swap with low priority (10)
swapon -p 10 "$NVME_SWAPFILE"

echo "================================================================================"
echo ">>> [4/4] Multi-Tier Swap Verification:"
echo "================================================================================"
swapon --show
echo "Tiered Memory subsystem initialized successfully."
