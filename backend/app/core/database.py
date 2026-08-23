"""
database.py - PostgreSQL and Redis Async Connection Manager with Dynamic Fallback
"""
from typing import Optional, Any
from app.core.config import settings

class DatabaseManager:
    def __init__(self):
        self.pg_pool: Optional[Any] = None
        self.redis: Optional[Any] = None

    async def connect(self):
        try:
            import asyncpg
            self.pg_pool = await asyncpg.create_pool(
                settings.POSTGRES_DSN,
                min_size=2,
                max_size=20,
                timeout=10.0
            )
        except Exception as e:
            print(f"[DB Notice] PostgreSQL connection not initialized: {e}")

        try:
            import redis.asyncio as aioredis
            self.redis = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=5.0
            )
        except Exception as e:
            print(f"[DB Notice] Redis connection not initialized: {e}")

    async def disconnect(self):
        if self.pg_pool:
            try:
                await self.pg_pool.close()
            except Exception:
                pass
        if self.redis:
            try:
                await self.redis.close()
            except Exception:
                pass

db = DatabaseManager()
