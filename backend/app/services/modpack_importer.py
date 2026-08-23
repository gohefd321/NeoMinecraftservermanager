"""
modpack_importer.py - Secure Modpack Importer & Package Manager
Supports Modrinth (.mrpack) and CurseForge (manifest.json)
Security: Zip Slip Defense, SSRF URL Validation, SHA-1/512 Integrity Check, Client-Only Mod Blacklisting
"""
import os
import io
import json
import zipfile
import asyncio
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
from pydantic import BaseModel, Field
from app.core.security import validate_url_safety, sanitize_relative_path

# ---------------------------------------------------------------------------
# 클라이언트 전용 모드 블랙리스트 (서버 런타임 크래시 방어)
# ---------------------------------------------------------------------------
CLIENT_ONLY_MOD_PATTERNS: Set[str] = {
    # 렌더링 / 쉐이더 / HUD
    "iris", "oculus", "optifine", "rubidium", "embeddium", "sodium", "sodium-extra",
    "reeses-sodium-options", "entityculling", "ferritecore-client", "canvas",
    "xaeros-minimap", "xaeros-world-map", "journeymap", "voxelmap", "mapwriter",
    "appleskin", "wthit", "jade", "hwyla", "jei", "rei", "emi",
    "presence-footsteps", "sound-physics-remastered", "dynamiclights", "physics-mod",
    "lambdynamiclights", "continuity", "indium", "cloth-config-client"
}


class DownloadTask(BaseModel):
    file_path: Path
    url: str
    sha1: Optional[str] = None
    sha512: Optional[str] = None
    file_size: Optional[int] = None
    is_client_only: bool = False


class ModpackManifest(BaseModel):
    name: str
    version: str
    loader: str
    minecraft_version: str
    files: List[DownloadTask] = Field(default_factory=list)


class ModpackImporter:
    def __init__(self, target_server_dir: Path, curseforge_api_key: Optional[str] = None):
        self.target_dir = target_server_dir.resolve()
        self.mods_dir = self.target_dir / "mods"
        self.curseforge_api_key = curseforge_api_key
        self.cf_base_url = "https://api.curseforge.com/v1"
        self.semaphore = asyncio.Semaphore(16)

    def _is_safe_path(self, target_file_path: Path) -> bool:
        """Zip Slip 방어: 대상 경로가 target_dir 내부에 위치하는지 엄격히 검증"""
        try:
            resolved = target_file_path.resolve()
            return str(resolved).startswith(str(self.target_dir))
        except Exception:
            return False

    def _is_client_only_mod(self, filename: str, env_rules: Optional[Dict[str, str]] = None) -> bool:
        if env_rules and env_rules.get("server") == "unsupported":
            return True

        normalized = filename.lower().replace("_", "-").replace(" ", "-")
        for pattern in CLIENT_ONLY_MOD_PATTERNS:
            if pattern in normalized:
                return True
        return False

    async def _write_file_async(self, path: Path, content: bytes):
        def _write():
            with open(path, "wb") as f:
                f.write(content)
        await asyncio.to_thread(_write)

    async def _verify_and_write(self, session: Any, task: DownloadTask) -> bool:
        if task.is_client_only:
            return False

        if not self._is_safe_path(task.file_path):
            print(f"[SECURITY ALERT] Path traversal blocked: {task.file_path}")
            return False

        # SSRF 방어 검증
        try:
            validate_url_safety(task.url)
        except Exception as e:
            print(f"[SECURITY BLOCKED] Unsafe URL rejected: {task.url} ({e})")
            return False

        task.file_path.parent.mkdir(parents=True, exist_ok=True)

        async with self.semaphore:
            try:
                import aiohttp
                async with session.get(task.url, timeout=aiohttp.ClientTimeout(total=180)) as resp:
                    if resp.status != 200:
                        raise RuntimeError(f"HTTP Status {resp.status}")

                    content = await resp.read()

                    # SHA-1 무결성 검증
                    if task.sha1:
                        calc_sha1 = hashlib.sha1(content).hexdigest()
                        if calc_sha1.lower() != task.sha1.lower():
                            raise ValueError(f"SHA-1 Mismatch on {task.file_path.name}")

                    # SHA-512 무결성 검증
                    if task.sha512:
                        calc_sha512 = hashlib.sha512(content).hexdigest()
                        if calc_sha512.lower() != task.sha512.lower():
                            raise ValueError(f"SHA-512 Mismatch on {task.file_path.name}")

                    await self._write_file_async(task.file_path, content)
                    return True
            except Exception as e:
                print(f"[ERROR] Failed to download {task.file_path.name}: {e}")
                return False

    # -----------------------------------------------------------------------
    # 1. Modrinth (.mrpack) 파서
    # -----------------------------------------------------------------------
    async def import_mrpack(self, mrpack_path: Path) -> ModpackManifest:
        with zipfile.ZipFile(mrpack_path, "r") as archive:
            if "modrinth.index.json" not in archive.namelist():
                raise ValueError("올바르지 않은 .mrpack 형식입니다: modrinth.index.json 누락")

            index_data = json.loads(archive.read("modrinth.index.json").decode("utf-8"))
            dependencies = index_data.get("dependencies", {})
            loader = "fabric"
            for k in ["fabric-loader", "forge", "neoforge", "quilt-loader"]:
                if k in dependencies:
                    loader = k
                    break

            manifest = ModpackManifest(
                name=index_data.get("name", "Modrinth Modpack"),
                version=index_data.get("versionId", "1.0.0"),
                loader=loader,
                minecraft_version=dependencies.get("minecraft", "unknown"),
            )

            for file_info in index_data.get("files", []):
                raw_path = file_info.get("path", "")
                sanitized_rel = sanitize_relative_path(raw_path)
                downloads = file_info.get("downloads", [])
                if not downloads:
                    continue

                hashes = file_info.get("hashes", {})
                env = file_info.get("env", {})
                is_client = self._is_client_only_mod(Path(sanitized_rel).name, env)

                target_dest = self.target_dir / sanitized_rel
                task = DownloadTask(
                    file_path=target_dest,
                    url=downloads[0],
                    sha1=hashes.get("sha1"),
                    sha512=hashes.get("sha512"),
                    file_size=file_info.get("fileSize"),
                    is_client_only=is_client,
                )
                manifest.files.append(task)

            # Overrides 복사 (Zip Slip 방어)
            for override_dir in ["overrides", "server-overrides"]:
                for file_entry in archive.namelist():
                    if file_entry.startswith(f"{override_dir}/") and not file_entry.endswith("/"):
                        rel_path = sanitize_relative_path(file_entry[len(override_dir) + 1:])
                        dest_path = self.target_dir / rel_path
                        if self._is_safe_path(dest_path):
                            dest_path.parent.mkdir(parents=True, exist_ok=True)
                            with archive.open(file_entry) as src, open(dest_path, "wb") as dst:
                                dst.write(src.read())

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                coros = [self._verify_and_write(session, t) for t in manifest.files]
                await asyncio.gather(*coros)
        except ImportError:
            print("[Modpack Importer] aiohttp not installed. Skipping live network download.")

        return manifest

    # -----------------------------------------------------------------------
    # 2. CurseForge (manifest.json) 파서
    # -----------------------------------------------------------------------
    async def import_curseforge_zip(self, zip_path: Path) -> ModpackManifest:
        if not self.curseforge_api_key:
            raise ValueError("CurseForge API Key가 설정되지 않았습니다.")

        with zipfile.ZipFile(zip_path, "r") as archive:
            if "manifest.json" not in archive.namelist():
                raise ValueError("올바르지 않은 CurseForge 팩 형식입니다: manifest.json 누락")

            raw_manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            mc_info = raw_manifest.get("minecraft", {})
            loaders = mc_info.get("modLoaders", [])
            loader = loaders[0].get("id") if loaders else "forge"

            manifest = ModpackManifest(
                name=raw_manifest.get("name", "CurseForge Modpack"),
                version=raw_manifest.get("version", "1.0.0"),
                loader=loader,
                minecraft_version=mc_info.get("version", "unknown"),
            )

            overrides_dir_name = raw_manifest.get("overrides", "overrides")
            for file_entry in archive.namelist():
                if file_entry.startswith(f"{overrides_dir_name}/") and not file_entry.endswith("/"):
                    rel_path = sanitize_relative_path(file_entry[len(overrides_dir_name) + 1:])
                    dest_path = self.target_dir / rel_path
                    if self._is_safe_path(dest_path):
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(file_entry) as src, open(dest_path, "wb") as dst:
                            dst.write(src.read())

        try:
            import aiohttp
            headers = {
                "x-api-key": self.curseforge_api_key,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            async with aiohttp.ClientSession(headers=headers) as session:
                for file_meta in raw_manifest.get("files", []):
                    project_id = file_meta.get("projectID")
                    file_id = file_meta.get("fileID")

                    cf_url = f"{self.cf_base_url}/mods/{project_id}/files/{file_id}"
                    async with session.get(cf_url) as resp:
                        if resp.status == 200:
                            file_data = (await resp.json()).get("data", {})
                            filename = file_data.get("fileName")
                            download_url = file_data.get("downloadUrl")

                            if not download_url:
                                download_url = f"https://edge.forgecdn.net/files/{file_id // 1000}/{file_id % 1000}/{filename}"

                            is_client = self._is_client_only_mod(filename)
                            manifest.files.append(
                                DownloadTask(
                                    file_path=self.mods_dir / filename,
                                    url=download_url,
                                    is_client_only=is_client
                                )
                            )

                coros = [self._verify_and_write(session, t) for t in manifest.files]
                await asyncio.gather(*coros)
        except ImportError:
            print("[Modpack Importer] aiohttp not installed. Skipping live network download.")

        return manifest
