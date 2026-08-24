"""
server_store.py - High-Concurrency Multi-Worker Persistent Server Registry
Features:
- Multi-Worker (Uvicorn 4 workers) Hot Reload with File Modification Time Tracking (st_mtime)
- Atomic File Write (via tempfile + os.replace) preventing race conditions
- Case-insensitive User Email & Anonymous User Ownership Association
- Multi-path Fallbacks (/var/mc_servers, /etc/nextgen-mc, /tmp/mc_servers)
"""
import os
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.models.schema import ServerStatus, ServerPreset

REGISTRY_CANDIDATE_PATHS = [
    "/var/mc_servers/servers_registry.json",
    "/etc/nextgen-mc/servers_registry.json",
    "/tmp/mc_servers/servers_registry.json"
]

class ServerRegistryStore:
    def __init__(self):
        self.registry_path = self._determine_path()
        self.servers: Dict[str, Dict[str, Any]] = {}
        self.last_mtime: float = 0.0
        self._load_from_disk_force()

    def _determine_path(self) -> str:
        for p in REGISTRY_CANDIDATE_PATHS:
            parent = os.path.dirname(p)
            try:
                os.makedirs(parent, exist_ok=True)
                test_file = os.path.join(parent, ".perm_test")
                with open(test_file, "w") as f:
                    f.write("1")
                os.remove(test_file)
                return p
            except Exception:
                continue
        return "/tmp/mc_servers/servers_registry.json"

    def _sync_with_disk(self):
        """다중 워커 프로세스 환경에서 파일 변경 시 실시간 리로드"""
        if os.path.exists(self.registry_path):
            try:
                mtime = os.path.getmtime(self.registry_path)
                if mtime > self.last_mtime:
                    with open(self.registry_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self.servers = data
                        self.last_mtime = mtime
            except Exception as e:
                print(f"[ServerRegistry Sync Warning] {e}")

    def _load_from_disk_force(self):
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.servers = data
                    self.last_mtime = os.path.getmtime(self.registry_path)
                    print(f"[ServerRegistry] Loaded {len(self.servers)} persistent servers from {self.registry_path}")
                    return
            except Exception as e:
                print(f"[ServerRegistry Error] Failed to read {self.registry_path}: {e}")

        # 파일이 없을 시 기본 초기화
        if not self.servers:
            demo_id = "mc-demo-01"
            self.servers[demo_id] = {
                "id": demo_id,
                "name": "야생 생존 알파",
                "domain_slug": "alpha",
                "preset_type": ServerPreset.SURVIVAL_SMP.value,
                "node_id": "master-local",
                "node_ip": "127.0.0.1",
                "port": 25565,
                "rcon_port": 25575,
                "rcon_password": "SafeRconPassword123!",
                "server_type": "PAPER",
                "mc_version": "26.2",
                "allocated_ram_mb": 4096,
                "status": ServerStatus.RUNNING.value,
                "billing_multiplier": 1.0,
                "full_domain": "alpha.domain.com",
                "is_local_master": True,
                "user_email": "player_steve@gmail.com",
                "injected_plugins": ["EssentialsX (TPA, Home)", "Chunky", "Spark"],
                "created_at": datetime.utcnow().isoformat()
            }
            self.save_to_disk()

    def save_to_disk(self):
        """원자적(Atomic) 파일 쓰기로 파일 손상 및 멀티프로세스 충돌 방지"""
        parent = os.path.dirname(self.registry_path)
        os.makedirs(parent, exist_ok=True)
        tmp_path = f"{self.registry_path}.tmp.{os.getpid()}"

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.servers, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.registry_path)
            self.last_mtime = os.path.getmtime(self.registry_path)
        except Exception as e:
            print(f"[ServerRegistry Save Error] {e}")
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def get_all(self) -> List[Dict[str, Any]]:
        self._sync_with_disk()
        return list(self.servers.values())

    def get_by_user(self, user_email: Optional[str] = None) -> List[Dict[str, Any]]:
        self._sync_with_disk()
        if not user_email:
            return list(self.servers.values())

        clean_user = user_email.lower().strip()
        matched = []
        for s in self.servers.values():
            s_owner = str(s.get("user_email", "")).lower().strip()
            # 정확한 이메일 일치 또는 데모 유저 호환
            if s_owner == clean_user or clean_user in ("player_steve@gmail.com", "user@domain.com", "admin@domain.com"):
                matched.append(s)

        return matched

    def get(self, server_id: str) -> Optional[Dict[str, Any]]:
        self._sync_with_disk()
        return self.servers.get(server_id)

    def put(self, server_id: str, server_data: Dict[str, Any]):
        self._sync_with_disk()
        self.servers[server_id] = server_data
        self.save_to_disk()

    def delete(self, server_id: str) -> Optional[Dict[str, Any]]:
        self._sync_with_disk()
        if server_id in self.servers:
            removed = self.servers.pop(server_id)
            self.save_to_disk()
            return removed
        return None

    def transfer_ownership(self, old_user_email: str, new_user_email: str) -> int:
        """게스트 유저가 로그인했을 때 생성했던 서버의 소유권을 계정으로 이전"""
        self._sync_with_disk()
        clean_old = old_user_email.lower().strip()
        clean_new = new_user_email.lower().strip()
        transferred = 0

        for s in self.servers.values():
            if str(s.get("user_email", "")).lower().strip() == clean_old:
                s["user_email"] = clean_new
                transferred += 1

        if transferred > 0:
            self.save_to_disk()

        return transferred

server_store = ServerRegistryStore()
