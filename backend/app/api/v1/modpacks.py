"""
modpacks.py - Modpack Search, Package Manager & One-Click Importer Trigger
"""
import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from app.services.modpack_importer import ModpackImporter
from app.core.config import settings

router = APIRouter(prefix="/modpacks", tags=["Modpack Ecosystem"])

@router.post("/import/mrpack")
async def import_modrinth_pack(
    server_id: str = Form(...),
    file: UploadFile = File(...)
):
    """
    .mrpack 파일 업로드 및 서버 mods/config 폴더로 자동 디스패치
    """
    if not file.filename.endswith(".mrpack"):
        raise HTTPException(status_code=400, detail=".mrpack 확장자 파일만 지원합니다.")

    target_dir = Path(f"/var/mc_servers/{server_id}")
    target_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".mrpack", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        importer = ModpackImporter(target_server_dir=target_dir)
        manifest = await importer.import_mrpack(tmp_path)
        return {
            "status": "success",
            "modpack_name": manifest.name,
            "version": manifest.version,
            "loader": manifest.loader,
            "minecraft_version": manifest.minecraft_version,
            "downloaded_files_count": len([f for f in manifest.files if not f.is_client_only]),
            "filtered_client_mods_count": len([f for f in manifest.files if f.is_client_only]),
            "message": "모드팩이 성공적으로 컨테이너 디렉토리에 설치되었습니다."
        }
    finally:
        if tmp_path.exists():
            os.remove(tmp_path)

@router.get("/search/modrinth")
async def search_modrinth_mods(query: str, loader: str = "fabric", mc_version: str = "1.20.4"):
    """
    Modrinth API 프록시 검색 (UI Package Manager 연동)
    """
    # 실제 환경에서는 Modrinth Lab API 직접 연동
    return {
        "query": query,
        "loader": loader,
        "version": mc_version,
        "results": [
            {
                "project_id": "spark",
                "title": "Spark Profiler",
                "description": "A performance profiling plugin/mod for Minecraft clients, servers, and proxies.",
                "server_side": "required",
                "client_side": "optional",
                "downloads": 1540200
            },
            {
                "project_id": "ferrite-core",
                "title": "FerriteCore",
                "description": "Memory usage optimizations for Minecraft.",
                "server_side": "required",
                "client_side": "required",
                "downloads": 894000
            }
        ]
    }
