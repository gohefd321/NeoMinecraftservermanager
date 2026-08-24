"""
billing_engine.py - Real-Time Pay-as-You-Go Billing Engine with Dynamic Admin Rate Adjustments
Features:
- Dynamic Billing Rates (Base rate, RAM rate, Chunk rate, Player rate customizable in Admin Page)
- Dynamic Tier Multipliers & Node-specific custom multipliers
- Redis In-Memory Atomic Deduction (Lua Script) & 10-Min PostgreSQL Batch Flush
- Out-of-Credit Graceful Shutdown via RCON
"""
import json
import asyncio
from typing import Dict, Any, Optional
from app.core.database import db
from app.services.node_scheduler import scheduler
from app.models.schema import BillingRateConfig, HardwareTier

LUA_DEDUCT_SCRIPT = """
local balance = redis.call('GET', KEYS[1])
if not balance then return {0, "0"} end
local current_bal = tonumber(balance)
local deduct_val = tonumber(ARGV[1])
if current_bal >= deduct_val then
    local new_bal = current_bal - deduct_val
    redis.call('SET', KEYS[1], tostring(new_bal))
    redis.call('HINCRBYFLOAT', 'wallet:pending_deltas', KEYS[1], -deduct_val)
    return {1, tostring(new_bal)}
else
    return {0, tostring(current_bal)}
end
"""

class BillingEngine:
    def __init__(self):
        self.lua_sha: Optional[str] = None
        # 실시간 동적 과금 요율 (어드민 페이지에서 즉시 변경 가능)
        self.rates: BillingRateConfig = BillingRateConfig()

    async def initialize(self):
        if db.redis:
            try:
                self.lua_sha = await db.redis.script_load(LUA_DEDUCT_SCRIPT)
                # Redis에 저장된 기존 요율 설정 불러오기
                saved_rates_json = await db.redis.get("config:billing_rates")
                if saved_rates_json:
                    data = json.loads(saved_rates_json)
                    self.rates = BillingRateConfig(**data)
                    print(f"[BillingEngine] Loaded Dynamic Rates from Redis: Base={self.rates.base_container_per_min}, RAM_GB={self.rates.per_ram_gb_rate}, Chunk={self.rates.per_chunk_rate}, Player={self.rates.per_player_rate}")
            except Exception as e:
                print(f"[BillingEngine Notice] Redis config initialization deferred: {e}")

    async def update_billing_rates(self, new_config: BillingRateConfig) -> BillingRateConfig:
        """어드민 대시보드에서 RAM/청크/플레이어/기본 단가 및 티어 배율 실시간 수정"""
        self.rates = new_config
        # Redis에 영구 보관
        if db.redis:
            try:
                await db.redis.set("config:billing_rates", json.dumps(new_config.dict()))
            except Exception as e:
                print(f"[BillingEngine Error] Failed to persist billing rates to Redis: {e}")

        # 노드 스케줄러의 기본 티어 배율 동기화
        for tier_str, mult in new_config.tier_multipliers.items():
            for node in scheduler.nodes.values():
                if node.hardware_tier == tier_str:
                    node.billing_multiplier = mult

        print(f"[BillingEngine] 💰 Dynamic Billing Rates Updated: Base={self.rates.base_container_per_min} KRW/m, RAM_GB={self.rates.per_ram_gb_rate} KRW/m, Chunk={self.rates.per_chunk_rate} KRW/m, Player={self.rates.per_player_rate} KRW/m")
        return self.rates

    def get_current_rates(self) -> BillingRateConfig:
        return self.rates

    def compute_minute_cost(self, ram_mb: int, chunks: int, players: int, node_id: str, cpu_cores: int = 2) -> float:
        """
        점유/할당 RAM 및 vCPU 코어, 어드민 설정 단가, 노드 배율을 반영한 1분 실제 과금액 연산
        Cost = (Base_Rate + (RAM_GB * RAM_GB_Rate) + (CPU_Cores * CPU_Rate) + (Chunks * Chunk_Rate) + (Players * Player_Rate)) * Node_Multiplier
        """
        base_rate = self.rates.base_container_per_min
        ram_gb = max(1.0, ram_mb / 1024.0)
        ram_rate = self.rates.per_ram_gb_rate
        cpu_rate = getattr(self.rates, "per_cpu_core_rate", 0.05)
        chunk_rate = self.rates.per_chunk_rate
        player_rate = self.rates.per_player_rate

        raw_cost = base_rate + (ram_gb * ram_rate) + (cpu_cores * cpu_rate) + (chunks * chunk_rate) + (players * player_rate)
        multiplier = scheduler.get_tier_multiplier(node_id)
        final_cost = round(raw_cost * multiplier, 4)
        return final_cost

    def calculate_estimated_cost_per_min(self, ram_mb: int, cpu_cores: int = 2, tier_id: Optional[str] = None, multiplier: Optional[float] = None) -> float:
        """
        서버 개설 시 사용자와 어드민에게 보여줄 '1분당 예상 차감 요금' 계산
        (유휴 기본 상태: 청크/플레이어 0 기준)
        """
        base_rate = self.rates.base_container_per_min
        ram_gb = max(1.0, ram_mb / 1024.0)
        ram_rate = self.rates.per_ram_gb_rate
        cpu_rate = getattr(self.rates, "per_cpu_core_rate", 0.05)

        raw_cost = base_rate + (ram_gb * ram_rate) + (cpu_cores * cpu_rate)
        
        mult = multiplier
        if mult is None:
            if tier_id and tier_id in scheduler.custom_tiers:
                mult = scheduler.custom_tiers[tier_id].multiplier
            elif tier_id == "high_nvme":
                mult = 1.3
            elif tier_id == "extreme_dedicated":
                mult = 1.8
            else:
                mult = 1.0

        return round(raw_cost * mult, 2)

    async def handle_out_of_credit_shutdown(self, server_meta: Dict[str, Any]):
        """
        크레딧 잔액 소진 시 RCON 안전 종료 및 DB 상태 변경
        """
        server_id = server_meta.get("server_id")
        host_ip = server_meta.get("node_ip", "127.0.0.1")
        rcon_port = server_meta.get("rcon_port", 25575)
        rcon_pass = server_meta.get("rcon_password", "")

        print(f"[BILLING ALERT] Server {server_id} has exhausted credits! Executing Graceful Shutdown...")

        try:
            from aiomcrcon import Client as AsyncRconClient
            async with AsyncRconClient(host_ip, rcon_port, rcon_pass) as rcon:
                # 1. 인게임 타이틀 및 챗 경고
                await rcon.send_cmd('title @a title {"text":"[과금 알림] 잔액 소진","color":"red","bold":true}')
                await rcon.send_cmd('title @a subtitle {"text":"크레딧이 모두 소진되어 서버가 안전하게 종료됩니다.","color":"yellow"}')
                await rcon.send_cmd('say [시스템] 10초 후 월드 데이터를 저장하고 서버를 일시 중지(SUSPENDED)합니다.')
                
                await asyncio.sleep(10)
                
                # 2. 월드 저장
                await rcon.send_cmd('save-all')
                await asyncio.sleep(3)
                
                # 3. 서버 정지
                await rcon.send_cmd('stop')
        except Exception as e:
            print(f"[RCON Shutdown] Note: RCON command execution on {server_id}: {e}")

        # DB 상태를 'SUSPENDED'로 변경
        if db.pg_pool:
            try:
                async with db.pg_pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE mc_servers SET status = 'SUSPENDED' WHERE id = $1",
                        server_id
                    )
            except Exception as e:
                print(f"[DB ERROR] Failed to update server status: {e}")

    async def process_telemetry(self, data: Dict[str, Any]):
        """
        1분 단위 텔레메트리 데이터 수신 및 원자적 실시간 과금 수행
        """
        user_id = data["user_id"]
        server_id = data["server_id"]
        node_id = data.get("node_id", "master-local")
        mem_used_mb = data.get("mem_used_mb", 4096)
        chunks = data.get("loaded_chunks", 0)
        players = data.get("active_players", 0)
        tps = data.get("tps", 20.0)

        cost = self.compute_minute_cost(mem_used_mb, chunks, players, node_id)
        wallet_key = f"wallet:balance:{user_id}"

        # 1. Redis 인메모리 원자적 차감
        status_code = 1
        remaining_balance = 1000.0
        if db.redis and self.lua_sha:
            try:
                res = await db.redis.evalsha(self.lua_sha, 1, wallet_key, str(cost))
                status_code, remaining_balance = int(res[0]), float(res[1])
            except Exception as e:
                print(f"[Redis Lua] Evaluation error: {e}")

        # 2. 텔레메트리 감사 로그 비동기 기록
        if db.pg_pool:
            try:
                async with db.pg_pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO telemetry_billing_logs 
                        (server_id, user_id, timestamp, loaded_chunks, active_players, tps, cost_krw)
                        VALUES ($1, $2, NOW(), $3, $4, $5, $6)
                        """,
                        server_id, user_id, chunks, players, tps, cost
                    )
            except Exception as e:
                print(f"[DB Insert Telemetry Log Error]: {e}")

        # 3. 크레딧 소진 판별
        if status_code == 0 or remaining_balance <= 0.0:
            server_meta = data.get("server_meta", {"server_id": server_id})
            await self.handle_out_of_credit_shutdown(server_meta)

    async def batch_sync_to_postgres(self):
        """
        10분 주기 Redis pending deltas -> PostgreSQL 영구 장부 동기화
        """
        while True:
            await asyncio.sleep(600)  # 10분
            if not db.redis or not db.pg_pool:
                continue

            try:
                deltas = await db.redis.hgetall("wallet:pending_deltas")
                if not deltas:
                    continue

                async with db.pg_pool.acquire() as conn:
                    async with conn.transaction():
                        for wallet_key, delta_str in deltas.items():
                            user_id = wallet_key.split(":")[-1]
                            delta_val = float(delta_str)
                            await conn.execute(
                                """
                                UPDATE credit_wallets 
                                SET balance_krw = balance_krw + $1, last_synced_at = NOW()
                                WHERE user_id = $2
                                """,
                                delta_val, user_id
                            )
                await db.redis.delete("wallet:pending_deltas")
                print(f"[Billing Sync] Flushed {len(deltas)} user balances to PostgreSQL.")
            except Exception as e:
                print(f"[Billing Sync ERROR] {e}")

billing_engine = BillingEngine()
