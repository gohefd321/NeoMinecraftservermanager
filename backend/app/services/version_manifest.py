"""
version_manifest.py - Real-Time Mojang Official Version Manifest Resolver
Fetches and provides all official releases (e.g. 26.2, 1.20.4, 1.16.5) and snapshots (e.g. 26.3-snapshot-9)
directly from Mojang API with intelligent caching.
"""
import time
import httpx
from typing import Dict, List, Any, Optional

MOJANG_MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"

class VersionManifestService:
    def __init__(self):
        self._cached_manifest: Optional[Dict[str, Any]] = None
        self._last_fetched: float = 0.0
        self._cache_ttl_seconds: int = 1800  # 30 min cache

        # Fallback reliable list
        self._fallback_releases = [
            "26.2", "26.1.2", "26.1.1", "26.1", "1.20.4", "1.20.2", "1.20.1", "1.19.4", "1.16.5", "1.12.2"
        ]
        self._fallback_snapshots = [
            "26.3-snapshot-9", "26.3-snapshot-8", "26.2-rc-2", "24w14a"
        ]

    async def get_version_manifest(self, force_refresh: bool = False) -> Dict[str, Any]:
        now = time.time()
        if not force_refresh and self._cached_manifest and (now - self._last_fetched < self._cache_ttl_seconds):
            return self._cached_manifest

        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                resp = await client.get(MOJANG_MANIFEST_URL)
                if resp.status_code == 200:
                    data = resp.json()
                    latest = data.get("latest", {})
                    all_versions = data.get("versions", [])

                    releases = [v["id"] for v in all_versions if v.get("type") == "release"]
                    snapshots = [v["id"] for v in all_versions if v.get("type") == "snapshot"]

                    latest_rel = latest.get("release") or (releases[0] if releases else "26.2")
                    latest_snap = latest.get("snapshot") or (snapshots[0] if snapshots else "26.3-snapshot-9")

                    manifest = {
                        "latest_release": latest_rel,
                        "latest_snapshot": latest_snap,
                        "releases": releases[:50],       # Top 50 releases
                        "snapshots": snapshots[:40],     # Top 40 snapshots
                        "all_releases_count": len(releases),
                        "all_snapshots_count": len(snapshots),
                        "total_versions": len(all_versions),
                        "source": "mojang_official_live"
                    }
                    self._cached_manifest = manifest
                    self._last_fetched = now
                    return manifest
        except Exception as e:
            print(f"[VersionManifest] Warning: Failed to fetch Mojang manifest ({e}). Using fallback.")

        fallback_manifest = {
            "latest_release": "26.2",
            "latest_snapshot": "26.3-snapshot-9",
            "releases": self._fallback_releases,
            "snapshots": self._fallback_snapshots,
            "all_releases_count": len(self._fallback_releases),
            "all_snapshots_count": len(self._fallback_snapshots),
            "total_versions": len(self._fallback_releases) + len(self._fallback_snapshots),
            "source": "fallback_cache"
        }
        return fallback_manifest

version_service = VersionManifestService()
