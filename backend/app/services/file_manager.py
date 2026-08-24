"""
file_manager.py - Sandboxed Minecraft Server File System, Properties Editor & World Archiver
Supports:
- Safe path resolution (prevents directory traversal)
- server.properties GUI key-value parser & writer
- File Explorer & Config Editing
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
from app.models.schema import FileItem, FileContentRead, ServerPropertiesModel

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
                    "allow-flight=false\n"
                    "spawn-protection=16\n"
                    "white-list=false\n"
                    "enforce-whitelist=false\n"
                    "hardcore=false\n"
                    "spawn-monsters=true\n"
                    "spawn-animals=true\n"
                    "spawn-npcs=true\n"
                    "allow-nether=true\n"
                    "generate-structures=true\n"
                    "level-seed=\n"
                )
        os.makedirs(os.path.join(root_dir, "plugins"), exist_ok=True)
        os.makedirs(os.path.join(root_dir, "mods"), exist_ok=True)
        os.makedirs(os.path.join(root_dir, "config"), exist_ok=True)
        os.makedirs(os.path.join(root_dir, "world"), exist_ok=True)

    def _resolve_safe_path(self, server_id: str, rel_path: str) -> str:
        root = self.get_server_root(server_id)
        clean_rel = rel_path.strip().lstrip("/")
        abs_path = os.path.abspath(os.path.join(root, clean_rel))
        if not abs_path.startswith(os.path.abspath(root)):
            raise HTTPException(status_code=403, detail="허가되지 않은 상위 디렉터리 접근입니다.")
        return abs_path

    def get_parsed_properties(self, server_id: str) -> ServerPropertiesModel:
        root = self.get_server_root(server_id)
        props_path = os.path.join(root, "server.properties")
        if not os.path.exists(props_path):
            self._init_default_configs(root, server_id)

        props: Dict[str, Any] = {}
        extra: Dict[str, str] = {}

        try:
            with open(props_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if k == "server-port": props["server_port"] = int(v) if v.isdigit() else 25565
                    elif k == "gamemode": props["gamemode"] = v
                    elif k == "difficulty": props["difficulty"] = v
                    elif k == "pvp": props["pvp"] = (v.lower() == "true")
                    elif k == "max-players": props["max_players"] = int(v) if v.isdigit() else 20
                    elif k == "motd": props["motd"] = v
                    elif k == "online-mode": props["online_mode"] = (v.lower() == "true")
                    elif k == "enable-rcon": props["enable_rcon"] = (v.lower() == "true")
                    elif k == "view-distance": props["view_distance"] = int(v) if v.isdigit() else 10
                    elif k == "simulation-distance": props["simulation_distance"] = int(v) if v.isdigit() else 8
                    elif k == "allow-flight": props["allow_flight"] = (v.lower() == "true")
                    elif k == "spawn-protection": props["spawn_protection"] = int(v) if v.isdigit() else 16
                    elif k == "white-list": props["white_list"] = (v.lower() == "true")
                    elif k == "enforce-whitelist": props["enforce_whitelist"] = (v.lower() == "true")
                    elif k == "hardcore": props["hardcore"] = (v.lower() == "true")
                    elif k == "spawn-monsters": props["spawn_monsters"] = (v.lower() == "true")
                    elif k == "spawn-animals": props["spawn_animals"] = (v.lower() == "true")
                    elif k == "spawn-npcs": props["spawn_npcs"] = (v.lower() == "true")
                    elif k == "allow-nether": props["allow_nether"] = (v.lower() == "true")
                    elif k == "generate-structures": props["generate_structures"] = (v.lower() == "true")
                    elif k == "level-seed": props["level_seed"] = v
                    else: extra[k] = v
        except Exception as e:
            print(f"[Properties Read Error] {e}")

        props["extra_properties"] = extra
        return ServerPropertiesModel(**props)

    def save_parsed_properties(self, server_id: str, model: ServerPropertiesModel):
        root = self.get_server_root(server_id)
        props_path = os.path.join(root, "server.properties")

        lines = [
            f"# Minecraft Server Properties (Updated {datetime.utcnow().isoformat()})\n",
            f"server-port={model.server_port}\n",
            f"gamemode={model.gamemode}\n",
            f"difficulty={model.difficulty}\n",
            f"pvp={'true' if model.pvp else 'false'}\n",
            f"max-players={model.max_players}\n",
            f"motd={model.motd}\n",
            f"online-mode={'true' if model.online_mode else 'false'}\n",
            f"enable-rcon={'true' if model.enable_rcon else 'false'}\n",
            f"view-distance={model.view_distance}\n",
            f"simulation-distance={model.simulation_distance}\n",
            f"allow-flight={'true' if model.allow_flight else 'false'}\n",
            f"spawn-protection={model.spawn_protection}\n",
            f"white-list={'true' if model.white_list else 'false'}\n",
            f"enforce-whitelist={'true' if model.enforce_whitelist else 'false'}\n",
            f"hardcore={'true' if model.hardcore else 'false'}\n",
            f"spawn-monsters={'true' if model.spawn_monsters else 'false'}\n",
            f"spawn-animals={'true' if model.spawn_animals else 'false'}\n",
            f"spawn-npcs={'true' if model.spawn_npcs else 'false'}\n",
            f"allow-nether={'true' if model.allow_nether else 'false'}\n",
            f"generate-structures={'true' if model.generate_structures else 'false'}\n",
            f"level-seed={model.level_seed}\n",
        ]
        for k, v in model.extra_properties.items():
            lines.append(f"{k}={v}\n")

        with open(props_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        return {"status": "success", "message": "server.properties가 성공적으로 저장되었습니다."}

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

        items.sort(key=lambda x: (not x.is_dir, x.name.lower()))
        return items

    def read_file_content(self, server_id: str, rel_path: str) -> FileContentRead:
        target_file = self._resolve_safe_path(server_id, rel_path)
        if not os.path.exists(target_file) or not os.path.isfile(target_file):
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

        size = os.path.getsize(target_file)
        if size > 5 * 1024 * 1024:
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
                zip_file.writestr("README.txt", f"World archive for {server_id} is being generated.")

        zip_buffer.seek(0)
        return zip_buffer

file_manager = ServerFileManager()
