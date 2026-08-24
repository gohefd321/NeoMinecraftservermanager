"""
file_manager.py - Sandboxed Minecraft Server File System & World Archiver
Supports:
- Safe path resolution (prevents path traversal / Directory Traversal attacks)
- File Explorer & Config Editing (server.properties, paper.yml, etc.)
- File Upload & Download
- One-click World ZIP Archive Streaming
"""
import os
import io
import zipfile
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import HTTPException
from app.models.schema import FileItem, FileContentRead

EDITABLE_EXTENSIONS = {
    ".properties", ".yml", ".yaml", ".json", ".toml", ".txt", ".log",
    ".cfg", ".conf", ".sh", ".env", ".mcmeta"
}

class ServerFileManager:
    def get_server_root(self, server_id: str) -> str:
        # 1. /var/mc_servers
        primary_dir = f"/var/mc_servers/{server_id}"
        if os.path.exists(primary_dir):
            return primary_dir
        
        # 2. /tmp/mc_servers
        fallback_dir = f"/tmp/mc_servers/{server_id}"
        if os.path.exists(fallback_dir):
            return fallback_dir

        # 없으면 기본 디렉토리 및 필수 config 초기 생성
        os.makedirs(fallback_dir, exist_ok=True)
        self._init_default_configs(fallback_dir, server_id)
        return fallback_dir

    def _init_default_configs(self, root_dir: str, server_id: str):
        props_path = os.path.join(root_dir, "server.properties")
        if not os.path.exists(props_path):
            with open(props_path, "w", encoding="utf-8") as f:
                f.write(
                    f"# Minecraft Server Properties for {server_id}\n"
                    "server-port=25565\n"
                    "gamemode=survival\n"
                    "difficulty=easy\n"
                    "pvp=true\n"
                    "max-players=20\n"
                    "motd=A NextGen MC Cloud Hosted Server\n"
                    "online-mode=true\n"
                    "enable-rcon=true\n"
                    "view-distance=10\n"
                    "simulation-distance=8\n"
                )
        os.makedirs(os.path.join(root_dir, "plugins"), exist_ok=True)
        os.makedirs(os.path.join(root_dir, "mods"), exist_ok=True)
        os.makedirs(os.path.join(root_dir, "config"), exist_ok=True)
        os.makedirs(os.path.join(root_dir, "world"), exist_ok=True)

    def _resolve_safe_path(self, server_id: str, rel_path: str) -> str:
        root = self.get_server_root(server_id)
        clean_rel = rel_path.strip().lstrip("/")
        abs_path = os.path.abspath(os.path.join(root, clean_rel))
        
        # 경로 순회(Path Traversal) 방지
        if not abs_path.startswith(os.path.abspath(root)):
            raise HTTPException(status_code=403, detail="허가되지 않은 상위 디렉터리 접근입니다.")
        return abs_path

    def list_files(self, server_id: str, rel_path: str = "") -> List[FileItem]:
        target_dir = self._resolve_safe_path(server_id, rel_path)
        if not os.path.exists(target_dir):
            return []

        items: List[FileItem] = []
        try:
            for entry in os.scandir(target_dir):
                entry_rel = os.path.relpath(entry.path, self.get_server_root(server_id))
                stat = entry.stat()
                mod_time = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                ext = os.path.splitext(entry.name)[1].lower()
                is_editable = entry.is_file() and (ext in EDITABLE_EXTENSIONS or entry.name in ("server.properties", "eula.txt"))

                items.append(FileItem(
                    name=entry.name,
                    path=entry_rel,
                    is_dir=entry.is_dir(),
                    size_bytes=stat.st_size if entry.is_file() else 0,
                    modified_at=mod_time,
                    is_editable=is_editable
                ))
        except Exception as e:
            print(f"[FileManager Error] {e}")

        # 폴더 우선, 그 후 파일명 순 정렬
        items.sort(key=lambda x: (not x.is_dir, x.name.lower()))
        return items

    def read_file_content(self, server_id: str, rel_path: str) -> FileContentRead:
        target_file = self._resolve_safe_path(server_id, rel_path)
        if not os.path.exists(target_file) or not os.path.isfile(target_file):
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

        size = os.path.getsize(target_file)
        if size > 5 * 1024 * 1024:  # 5MB 제한
            raise HTTPException(status_code=400, detail="텍스트 에디터는 5MB 이하 파일만 열 수 있습니다. 다운로드를 이용하세요.")

        try:
            with open(target_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return FileContentRead(path=rel_path, content=content, size_bytes=size)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"파일을 읽는 도중 오류가 발생했습니다: {str(e)}")

    def save_file_content(self, server_id: str, rel_path: str, content: str):
        target_file = self._resolve_safe_path(server_id, rel_path)
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        try:
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(content)
            return {"status": "saved", "path": rel_path, "size_bytes": len(content.encode('utf-8'))}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"파일 저장 실패: {str(e)}")

    def save_uploaded_file(self, server_id: str, rel_path: str, filename: str, file_bytes: bytes):
        target_dir = self._resolve_safe_path(server_id, rel_path)
        os.makedirs(target_dir, exist_ok=True)
        target_file = os.path.join(target_dir, filename)
        
        with open(target_file, "wb") as f:
            f.write(file_bytes)
        return {"status": "uploaded", "filename": filename, "size_bytes": len(file_bytes)}

    def create_world_archive_stream(self, server_id: str) -> io.BytesIO:
        root = self.get_server_root(server_id)
        zip_buffer = io.BytesIO()

        world_folders = ["world", "world_nether", "world_the_end"]
        found_any = False

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for folder_name in world_folders:
                folder_path = os.path.join(root, folder_name)
                if os.path.exists(folder_path):
                    found_any = True
                    for dirpath, dirnames, filenames in os.walk(folder_path):
                        for filename in filenames:
                            file_full_path = os.path.join(dirpath, filename)
                            arcname = os.path.relpath(file_full_path, root)
                            zip_file.write(file_full_path, arcname)

            if not found_any:
                # 월드 폴더가 없으면 기본 README 파일 압축
                zip_file.writestr("README.txt", f"World archive for {server_id} is being generated.")

        zip_buffer.seek(0)
        return zip_buffer

file_manager = ServerFileManager()
