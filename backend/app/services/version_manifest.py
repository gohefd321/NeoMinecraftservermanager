"""
version_manifest.py - Mojang Official Version Manifest Resolver
Fetches and caches all Minecraft versions (Releases, Snapshots, Pre-releases, RCs) directly from Mojang API.
"""
import time
import httpx
from typing import Dict, List, Any, Optional

MOJANG_MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"

class VersionManifestService:
    def __init__(self):
        self._cached_manifest: Optional[Dict[str, Any]] = None
        self._last_fetched: float = 0.0
        self._cache_ttl_seconds: int = 3600  # 1 hour cache

        # Fallback reliable list if internet is restricted or offline
        self._fallback_releases = [
            "1.21", "1.20.4", "1.20.2", "1.20.1", "1.19.4", "1.19.2",
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
                    latest = data.get("latest", {"release": "1.20.4", "snapshot": "24w14a"})
                    all_versions = data.get("versions", [])

                    releases = [v["id"] for v in all_versions if v.get("type") == "release"]
                    snapshots = [v["id"] for v in all_versions if v.get("type") == "snapshot"]

                    manifest = {
                        "latest_release": latest.get("release", "1.20.4"),
                        "latest_snapshot": latest.get("snapshot", "24w14a"),
                        "releases": releases[:40],       # Top 40 releases
                        "snapshots": snapshots[:30],     # Top 30 snapshots
                        "all_releases_count": len(releases),
                        "all_snapshots_count": len(snapshots),
                        "total_versions": len(all_versions),
                        "source": "mojang_official"
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
