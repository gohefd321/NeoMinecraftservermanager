"""
version_manifest.py - Robust Mojang Official Version Manifest Resolver
Filters only valid Minecraft version formats (e.g. 1.20.4, 1.20.2, 1.16.5, 24w09a, 1.21-pre1)
and guards against any unexpected API formats.
"""
import re
import time
import httpx
from typing import Dict, List, Any, Optional

MOJANG_MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"

# 유효한 마인크래프트 버전 정규식 (1.x.x 또는 2xWxxa 스냅샷)
VALID_RELEASE_REGEX = re.compile(r"^1\.\d+(\.\d+)?$")
VALID_SNAPSHOT_REGEX = re.compile(r"^(\d{2}w\d{2}[a-z]|1\.\d+(\.\d+)?-(pre|rc)\d+)$")

class VersionManifestService:
    def __init__(self):
        self._cached_manifest: Optional[Dict[str, Any]] = None
        self._last_fetched: float = 0.0
        self._cache_ttl_seconds: int = 3600  # 1 hour cache

        # Fallback reliable list
        self._fallback_releases = [
            "1.20.4", "1.20.2", "1.20.1", "1.19.4", "1.19.2",
            "1.18.2", "1.17.1", "1.16.5", "1.12.2", "1.8.9", "1.7.10"
        ]
        self._fallback_snapshots = [
            "24w14a", "24w13a", "24w09a", "1.21-pre1", "1.20.5-pre2"
        ]

    async def get_version_manifest(self, force_refresh: bool = False) -> Dict[str, Any]:
        now = time.time()
        if not force_refresh and self._cached_manifest and (now - self._last_fetched < self._cache_ttl_seconds):
            return self._cached_manifest

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(MOJANG_MANIFEST_URL)
                if resp.status_code == 200:
                    data = resp.json()
                    all_versions = data.get("versions", [])

                    # 정규식으로 유효한 버전만 엄격하게 필터링
                    filtered_releases = []
                    filtered_snapshots = []

                    for v in all_versions:
                        v_id = v.get("id", "")
                        v_type = v.get("type", "")
                        if v_type == "release" and VALID_RELEASE_REGEX.match(v_id):
                            filtered_releases.append(v_id)
                        elif v_type == "snapshot" and (VALID_SNAPSHOT_REGEX.match(v_id) or VALID_RELEASE_REGEX.match(v_id)):
                            filtered_snapshots.append(v_id)

                    # 기본 릴리즈가 없으면 fallback 주입
                    if not filtered_releases:
                        filtered_releases = self._fallback_releases
                    if not filtered_snapshots:
                        filtered_snapshots = self._fallback_snapshots

                    latest_rel = filtered_releases[0] if filtered_releases else "1.20.4"
                    latest_snap = filtered_snapshots[0] if filtered_snapshots else "24w14a"

                    manifest = {
                        "latest_release": latest_rel,
                        "latest_snapshot": latest_snap,
                        "releases": filtered_releases[:40],
                        "snapshots": filtered_snapshots[:30],
                        "all_releases_count": len(filtered_releases),
                        "all_snapshots_count": len(filtered_snapshots),
                        "total_versions": len(filtered_releases) + len(filtered_snapshots),
                        "source": "mojang_official_filtered"
                    }
                    self._cached_manifest = manifest
                    self._last_fetched = now
                    return manifest
        except Exception as e:
            print(f"[VersionManifest] Warning: Failed to fetch Mojang manifest ({e}). Using reliable fallback.")

        fallback_manifest = {
            "latest_release": "1.20.4",
            "latest_snapshot": "24w14a",
            "releases": self._fallback_releases,
            "snapshots": self._fallback_snapshots,
            "all_releases_count": len(self._fallback_releases),
            "all_snapshots_count": len(self._fallback_snapshots),
            "total_versions": len(self._fallback_releases) + len(self._fallback_snapshots),
            "source": "fallback_cache"
        }
        return fallback_manifest

version_service = VersionManifestService()
