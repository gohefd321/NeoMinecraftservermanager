"""
main.py - Master Node FastAPI Application Entrypoint
Supports: Master-as-Worker Local Containers, Dynamic Admin Billing, Local LLM Profiling
"""
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import db
from app.api.routes import api_router
from app.services.billing_engine import billing_engine
from app.services.node_scheduler import scheduler

ADMIN_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NextGen MC - 어드민 노드 & 동적 과금 관리</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@300;400;600;700;800&display=swap');
        body { font-family: 'Pretendard', sans-serif; background: #0b0f19; color: #f1f5f9; }
        .card { background: #131b2e; border: 1px solid rgba(255, 255, 255, 0.08); }
    </style>
</head>
<body class="p-6 md:p-10 max-w-7xl mx-auto space-y-8">
    <!-- Header -->
    <div class="flex flex-col md:flex-row items-start md:items-center justify-between pb-6 border-b border-slate-800 gap-4">
        <div>
            <h1 class="text-3xl font-extrabold tracking-tight text-white flex items-center gap-3">
                <span class="p-2 bg-indigo-600/20 text-indigo-400 rounded-xl border border-indigo-500/30">⚙️</span>
                어드민 클러스터 & 실시간 과금 제어 센터
            </h1>
            <p class="text-sm text-slate-400 mt-1">마스터/워커 노드 자원 모니터링 및 청크·플레이어 단위 실시간 종량제 요율 제어</p>
        </div>
        <div class="flex items-center gap-3">
            <span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-emerald-950/80 text-emerald-400 border border-emerald-500/30">
                <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                Master Control Plane Active
            </span>
        </div>
    </div>

    <!-- 1. Real-Time Dynamic Billing Rate Controller -->
    <div class="card rounded-2xl p-6 shadow-xl space-y-6">
        <div class="flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
                <h2 class="text-lg font-bold text-white">💰 실시간 종량제 과금 요율 동적 설정</h2>
                <p class="text-xs text-slate-400">수정 즉시 실시간 텔레메트리 연산에 반영됩니다.</p>
            </div>
            <button onclick="fetchCurrentRates()" class="text-xs text-indigo-400 hover:text-indigo-300 font-semibold underline">요율 새로고침</button>
        </div>

        <form id="billingForm" class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div class="space-y-2">
                <label class="block text-xs font-bold text-slate-300 uppercase">기본 유지비 (분당 KRW)</label>
                <div class="flex items-center gap-2">
                    <input type="number" step="0.01" id="base_container" name="base_container" class="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-sm focus:border-indigo-500 outline-none" required>
                    <span class="text-xs text-slate-400">원/분</span>
                </div>
                <p class="text-[11px] text-slate-500">컨테이너 가동 기본 단가 (기본값: 0.50원)</p>
            </div>

            <div class="space-y-2">
                <label class="block text-xs font-bold text-slate-300 uppercase">청크당 요율 (분당 KRW)</label>
                <div class="flex items-center gap-2">
                    <input type="number" step="0.0001" id="chunk_rate" name="chunk_rate" class="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-sm focus:border-indigo-500 outline-none" required>
                    <span class="text-xs text-slate-400">원/청크</span>
                </div>
                <p class="text-[11px] text-slate-500">로드된 1개 청크당 단가 (기본값: 0.0010원)</p>
            </div>

            <div class="space-y-2">
                <label class="block text-xs font-bold text-slate-300 uppercase">플레이어당 요율 (분당 KRW)</label>
                <div class="flex items-center gap-2">
                    <input type="number" step="0.01" id="player_rate" name="player_rate" class="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-sm focus:border-indigo-500 outline-none" required>
                    <span class="text-xs text-slate-400">원/인</span>
                </div>
                <p class="text-[11px] text-slate-500">동시접속자 1인당 단가 (기본값: 0.10원)</p>
            </div>

            <!-- Hardware Tier Multipliers -->
            <div class="md:col-span-3 pt-4 border-t border-slate-800 space-y-3">
                <h3 class="text-xs font-bold text-slate-300 uppercase">하드웨어 스펙 티어별 과금 배율 (Tier Multipliers)</h3>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div class="p-4 bg-slate-900/60 rounded-xl border border-slate-800 space-y-1.5">
                        <span class="text-xs font-bold text-slate-300">Standard SSD 노드</span>
                        <input type="number" step="0.1" id="tier_std" class="w-full px-3 py-1.5 bg-slate-950 border border-slate-700 rounded-lg text-sm outline-none">
                    </div>
                    <div class="p-4 bg-slate-900/60 rounded-xl border border-slate-800 space-y-1.5">
                        <span class="text-xs font-bold text-indigo-400">High Gen4 NVMe 노드</span>
                        <input type="number" step="0.1" id="tier_nvme" class="w-full px-3 py-1.5 bg-slate-950 border border-slate-700 rounded-lg text-sm outline-none">
                    </div>
                    <div class="p-4 bg-slate-900/60 rounded-xl border border-slate-800 space-y-1.5">
                        <span class="text-xs font-bold text-amber-400">Extreme Dedicated 노드</span>
                        <input type="number" step="0.1" id="tier_ext" class="w-full px-3 py-1.5 bg-slate-950 border border-slate-700 rounded-lg text-sm outline-none">
                    </div>
                </div>
            </div>

            <div class="md:col-span-3 flex justify-end">
                <button type="submit" class="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 font-bold text-sm rounded-xl transition shadow-lg shadow-indigo-600/30">
                    과금 요율 즉시 저장 및 실시간 적용
                </button>
            </div>
        </form>
    </div>

    <!-- 2. Live Cluster Nodes Overview (Master + Workers) -->
    <div class="card rounded-2xl p-6 shadow-xl space-y-6">
        <div class="flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
                <h2 class="text-lg font-bold text-white">🖥️ 클러스터 노드 현황 & 가용 자원 (Master-as-Worker 지원)</h2>
                <p class="text-xs text-slate-400">마스터 노드 및 워커 노드의 CPU, RAM, ZRAM, 컨테이너 가동 현황</p>
            </div>
            <button onclick="fetchNodes()" class="text-xs text-indigo-400 hover:text-indigo-300 font-semibold underline">노드 새로고침</button>
        </div>

        <div id="nodesGrid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            <!-- Dynamic Nodes Rendered Here -->
        </div>
    </div>

    <script>
        async function fetchCurrentRates() {
            try {
                const resp = await fetch('/api/v1/nodes/admin/billing/rates');
                const data = await resp.json();
                document.getElementById('base_container').value = data.base_container_per_min;
                document.getElementById('chunk_rate').value = data.per_chunk_rate;
                document.getElementById('player_rate').value = data.per_player_rate;
                document.getElementById('tier_std').value = data.tier_multipliers.standard_ssd || 1.0;
                document.getElementById('tier_nvme').value = data.tier_multipliers.high_nvme || 1.3;
                document.getElementById('tier_ext').value = data.tier_multipliers.extreme_dedicated || 1.8;
            } catch (err) {
                console.error(err);
            }
        }

        document.getElementById('billingForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const payload = {
                base_container_per_min: parseFloat(document.getElementById('base_container').value),
                per_chunk_rate: parseFloat(document.getElementById('chunk_rate').value),
                per_player_rate: parseFloat(document.getElementById('player_rate').value),
                tier_multipliers: {
                    standard_ssd: parseFloat(document.getElementById('tier_std').value),
                    high_nvme: parseFloat(document.getElementById('tier_nvme').value),
                    extreme_dedicated: parseFloat(document.getElementById('tier_ext').value)
                }
            };

            const resp = await fetch('/api/v1/nodes/admin/billing/rates', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (resp.ok) {
                alert('과금 요율이 성공적으로 수정되었으며 실시간 반영되었습니다!');
                fetchNodes();
            } else {
                alert('과금 요율 수정 실패');
            }
        });

        async function fetchNodes() {
            try {
                const resp = await fetch('/api/v1/nodes/admin/overview');
                const data = await resp.json();
                const container = document.getElementById('nodesGrid');
                container.innerHTML = '';

                data.nodes.forEach(node => {
                    const ramPct = Math.round((node.ram_used_mb / Math.max(node.ram_total_mb, 1)) * 100);
                    const isMaster = node.is_master_node;
                    const card = document.createElement('div');
                    card.className = 'p-5 bg-slate-900/80 rounded-xl border ' + (isMaster ? 'border-indigo-500/40 bg-indigo-950/20' : 'border-slate-800') + ' space-y-4';
                    card.innerHTML = `
                        <div class="flex items-center justify-between">
                            <div>
                                <span class="font-bold text-sm text-white">${node.node_name}</span>
                                ${isMaster ? '<span class="ml-2 px-2 py-0.5 text-[10px] font-extrabold bg-indigo-600 text-white rounded">MASTER+CONTAINER</span>' : '<span class="ml-2 px-2 py-0.5 text-[10px] bg-slate-800 text-slate-300 rounded">WORKER</span>'}
                            </div>
                            <span class="text-xs px-2 py-0.5 rounded font-mono font-bold ${node.status === 'ONLINE' ? 'text-emerald-400 bg-emerald-950' : 'text-rose-400 bg-rose-950'}">${node.status}</span>
                        </div>

                        <div class="space-y-2 text-xs">
                            <div class="flex justify-between text-slate-400">
                                <span>CPU Usage:</span>
                                <span class="font-mono font-bold text-slate-200">${node.cpu_usage_pct.toFixed(1)}%</span>
                            </div>
                            <div class="flex justify-between text-slate-400">
                                <span>RAM (${ramPct}%):</span>
                                <span class="font-mono font-bold text-slate-200">${node.ram_used_mb}MB / ${node.ram_total_mb}MB</span>
                            </div>
                            <div class="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                                <div class="bg-indigo-500 h-full" style="width: ${ramPct}%"></div>
                            </div>
                            <div class="flex justify-between text-slate-400">
                                <span>Active Containers:</span>
                                <span class="font-mono font-bold text-indigo-400">${node.running_containers}</span>
                            </div>
                        </div>

                        <div class="pt-3 border-t border-slate-800 flex items-center justify-between">
                            <div class="text-[11px] text-slate-400">
                                과금 배율: <strong class="text-amber-400 font-mono text-xs">${node.billing_multiplier}x</strong>
                            </div>
                            <button onclick="changeNodeMultiplier('${node.node_id}')" class="px-2.5 py-1 text-[11px] bg-slate-800 hover:bg-slate-700 rounded text-slate-200">배율 수정</button>
                        </div>
                    `;
                    container.appendChild(card);
                });
            } catch (err) {
                console.error(err);
            }
        }

        async function changeNodeMultiplier(nodeId) {
            const val = prompt(`[${nodeId}] 노드의 새로운 과금 배율을 입력하십시오 (예: 1.5):`, "1.0");
            if (val && !isNaN(val)) {
                await fetch('/api/v1/nodes/admin/nodes/set-multiplier', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ node_id: nodeId, custom_multiplier: parseFloat(val) })
                });
                fetchNodes();
            }
        }

        fetchCurrentRates();
        fetchNodes();
        setInterval(fetchNodes, 5000);
    </script>
</body>
</html>"""

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"🚀 [{settings.PROJECT_NAME} v{settings.VERSION}] Master Control Plane Starting...")
    await db.connect()
    await billing_engine.initialize()

    # Master 노드 자체를 로컬 워커로 자동 등록 (Master-as-Worker 지원)
    scheduler.register_master_as_local_worker()

    # 10분 주기 비동기 PostgreSQL 과금 동기화
    sync_task = asyncio.create_task(billing_engine.batch_sync_to_postgres())

    yield

    sync_task.cancel()
    await db.disconnect()
    print("🛑 Master Control Plane stopped gracefully.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Next-Gen Cloud-Native Minecraft Hosting Platform API with Tiered Memory & Real-Time Billing",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard():
    """어드민 전용 클러스터 노드 현황 & 실시간 과금 요율 제어 대시보드 UI"""
    return ADMIN_DASHBOARD_HTML

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "master_as_worker_active": "master-local" in scheduler.nodes
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
