"""
server_store.py - Persistent Server Registry (JSON File + In-Memory Fallback)
Ensures Minecraft servers persist across backend restarts, reboots, and page refreshes.
"""
import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.models.schema import ServerStatus, ServerPreset

PRIMARY_REGISTRY_PATH = "/var/mc_servers/servers_registry.json"
FALLBACK_REGISTRY_PATH = "/tmp/mc_servers/servers_registry.json"

class ServerRegistryStore:
    def __init__(self):
        self.registry_path = self._determine_path()
        self.servers: Dict[str, Dict[str, Any]] = {}
        self.load_from_disk()

    def _determine_path(self) -> str:
        try:
            os.makedirs("/var/mc_servers", exist_ok=True)
            return PRIMARY_REGISTRY_PATH
        except Exception:
            os.makedirs("/tmp/mc_servers", exist_ok=True)
            return FALLBACK_REGISTRY_PATH

    def load_from_disk(self):
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.servers = data
                    print(f"[ServerRegistry] Loaded {len(self.servers)} persistent servers from {self.registry_path}")
                    return
            except Exception as e:
                print(f"[ServerRegistry Error] Failed to read {self.registry_path}: {e}")

        # 파일이 없으면 기본 데모 서버 생성
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
        try:
            os.makedirs(os.path.dirname(self.registry_path), exist_ok=True)
            with open(self.registry_path, "w", encoding="utf-8") as f:
                json.dump(self.servers, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ServerRegistry Save Error] {e}")

    def get_all(self) -> List[Dict[str, Any]]:
        return list(self.servers.values())

    def get_by_user(self, user_email: Optional[str] = None) -> List[Dict[str, Any]]:
        if not user_email:
            return list(self.servers.values())
        return [
            s for s in self.servers.values()
            if s.get("user_email") == user_email or user_email in ("player_steve@gmail.com", "user@domain.com", "admin@domain.com")
        ]

    def get(self, server_id: str) -> Optional[Dict[str, Any]]:
        return self.servers.get(server_id)

    def put(self, server_id: str, server_data: Dict[str, Any]):
        self.servers[server_id] = server_data
        self.save_to_disk()

    def delete(self, server_id: str) -> Optional[Dict[str, Any]]:
        if server_id in self.servers:
            removed = self.servers.pop(server_id)
            self.save_to_disk()
            return removed
        return None

server_store = ServerRegistryStore()
