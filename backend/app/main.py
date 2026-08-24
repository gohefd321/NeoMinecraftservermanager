"""
main.py - Master Node FastAPI Application Entrypoint
Includes:
1. User Client Dashboard (/) - Server Creation, Credit Topup, Modpacks, RCON Console
2. Admin Dashboard (/admin) - Live Nodes, Dynamic Billing Rates
3. Master-as-Worker Local Container Support
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

# ==============================================================================
# 1. 일반 유저 전용 웹 대시보드 UI (Server Rental, Credit, Console, Creation)
# ==============================================================================
USER_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NextGen MC - 클라우드 마인크래프트 서버 호스팅</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@300;400;600;700;800&display=swap');
        body { font-family: 'Pretendard', sans-serif; background: #070b14; color: #f1f5f9; min-height: 100vh; }
        .card { background: #0f172a; border: 1px solid rgba(255, 255, 255, 0.08); }
        .glass-btn { background: linear-gradient(135deg, #4f46e5, #6366f1); }
    </style>
</head>
<body class="p-4 md:p-8 max-w-6xl mx-auto space-y-8">
    <!-- Top Navbar -->
    <header class="flex items-center justify-between pb-6 border-b border-slate-800">
        <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center font-black text-xl text-white shadow-lg shadow-indigo-500/30">⛏️</div>
            <div>
                <h1 class="text-xl font-bold text-white tracking-tight">NextGen MC Hosting</h1>
                <p class="text-xs text-slate-400">실시간 종량제 클라우드 마인크래프트 서버</p>
            </div>
        </div>

        <div class="flex items-center gap-4">
            <!-- User Balance Box -->
            <div class="px-4 py-2 bg-slate-900 rounded-xl border border-slate-800 flex items-center gap-3 text-xs">
                <div>
                    <span class="text-slate-400 block text-[10px] uppercase font-bold">보유 크레딧</span>
                    <span id="userBalance" class="font-mono font-bold text-sm text-emerald-400">3,000 KRW</span>
                </div>
                <button onclick="topupCredit()" class="px-2.5 py-1 bg-emerald-600/20 text-emerald-300 hover:bg-emerald-600/30 rounded-lg text-xs font-semibold border border-emerald-500/30 transition">
                    + 충전
                </button>
            </div>

            <!-- Adult Verification Badge -->
            <span class="px-3 py-1.5 rounded-xl bg-indigo-950 text-indigo-300 border border-indigo-500/30 text-xs font-semibold flex items-center gap-1.5">
                <span class="w-2 h-2 rounded-full bg-indigo-400"></span> 19세 성인인증 완료
            </span>
        </div>
    </header>

    <!-- Hero / Create Server Action -->
    <div class="card rounded-2xl p-6 md:p-8 bg-gradient-to-r from-indigo-950/40 via-slate-900 to-slate-900 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div class="space-y-2 max-w-xl">
            <span class="px-3 py-1 rounded-full text-[11px] font-extrabold bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 uppercase">초고속 클라우드 배포</span>
            <h2 class="text-2xl font-black text-white">원클릭으로 마인크래프트 서버를 개설하세요</h2>
            <p class="text-xs text-slate-400 leading-relaxed">
                포트 번호 없이 <strong>id.domain.com</strong>으로 접속되는 L4 제로-포트 프록시, Java 21 Generational ZGC, 실시간 1분 종량제 과금이 자동 적용됩니다.
            </p>
        </div>
        <button onclick="openCreateModal()" class="glass-btn px-6 py-3.5 rounded-xl font-bold text-sm text-white shadow-xl shadow-indigo-600/40 hover:opacity-90 transition whitespace-nowrap">
            🚀 새 서버 생성하기
        </button>
    </div>

    <!-- My Minecraft Servers Section -->
    <div class="space-y-4">
        <div class="flex items-center justify-between">
            <h3 class="text-lg font-bold text-white flex items-center gap-2">
                <span>🎮</span> 내 마인크래프트 서버 목록
            </h3>
            <span class="text-xs text-slate-400" id="serverCount">가동 중인 서버: 0개</span>
        </div>

        <div id="serversList" class="grid grid-cols-1 md:grid-cols-2 gap-5">
            <!-- Empty State Placeholder -->
            <div id="emptyState" class="md:col-span-2 card rounded-2xl p-12 text-center space-y-3">
                <div class="text-4xl">🕹️</div>
                <p class="text-sm font-semibold text-slate-300">아직 생성된 마인크래프트 서버가 없습니다.</p>
                <p class="text-xs text-slate-500">상단의 [새 서버 생성하기] 버튼을 눌러 첫 서버를 개설하십시오.</p>
            </div>
        </div>
    </div>

    <!-- Create Server Modal -->
    <div id="createModal" class="hidden fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50">
        <div class="card max-w-lg w-full rounded-2xl p-6 space-y-5 shadow-2xl">
            <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                <h4 class="font-bold text-base text-white">✨ 새 마인크래프트 서버 개설</h4>
                <button onclick="closeCreateModal()" class="text-slate-400 hover:text-white text-lg font-bold">&times;</button>
            </div>

            <form id="createForm" class="space-y-4 text-xs">
                <div>
                    <label class="block font-semibold text-slate-300 mb-1">서버 이름</label>
                    <input type="text" id="srv_name" required placeholder="예: 야생 생존 서버" class="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-slate-100 outline-none focus:border-indigo-500">
                </div>

                <div>
                    <label class="block font-semibold text-slate-300 mb-1">접속용 서브도메인 (id.domain.com)</label>
                    <div class="flex items-center gap-2">
                        <input type="text" id="srv_slug" required pattern="^[a-z0-9-]{3,32}$" placeholder="예: myworld" class="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-slate-100 outline-none focus:border-indigo-500 font-mono">
                        <span class="text-slate-400 font-mono">.domain.com</span>
                    </div>
                </div>

                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block font-semibold text-slate-300 mb-1">서버 코어 (Server Type)</label>
                        <select id="srv_type" class="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-slate-100 outline-none focus:border-indigo-500">
                            <option value="PAPER">Paper (최적화 플러그인)</option>
                            <option value="FABRIC">Fabric (경량 모드팩)</option>
                            <option value="NEOFORGE">NeoForge (대형 모드팩)</option>
                            <option value="PURPUR">Purpur (하이퍼 커스텀)</option>
                        </select>
                    </div>
                    <div>
                        <label class="block font-semibold text-slate-300 mb-1">마인크래프트 버전</label>
                        <select id="srv_version" class="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-slate-100 outline-none focus:border-indigo-500 font-mono">
                            <option value="1.20.4">1.20.4 (최신 안정화)</option>
                            <option value="1.20.2">1.20.2</option>
                            <option value="1.19.4">1.19.4</option>
                            <option value="1.16.5">1.16.5</option>
                        </select>
                    </div>
                </div>

                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block font-semibold text-slate-300 mb-1">할당 RAM 메모리</label>
                        <select id="srv_ram" class="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-slate-100 outline-none focus:border-indigo-500">
                            <option value="4096">4 GB RAM (기본 권장)</option>
                            <option value="6144">6 GB RAM (중형 모드팩)</option>
                            <option value="8192">8 GB RAM (대형 서버)</option>
                        </select>
                    </div>
                    <div>
                        <label class="block font-semibold text-slate-300 mb-1">하드웨어 스펙 티어</label>
                        <select id="srv_tier" class="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-slate-100 outline-none focus:border-indigo-500">
                            <option value="standard_ssd">표준 SSD (1.0x 배율)</option>
                            <option value="high_nvme" selected>고성능 NVMe (1.3x 배율)</option>
                            <option value="extreme_dedicated">단독 코어 (1.8x 배율)</option>
                        </select>
                    </div>
                </div>

                <div class="p-3 bg-slate-900/60 rounded-xl border border-slate-800 space-y-2">
                    <label class="flex items-center gap-2 cursor-pointer">
                        <input type="checkbox" id="srv_crossplay" checked class="rounded bg-slate-800 border-slate-700 text-indigo-600 focus:ring-0">
                        <span class="text-slate-300 font-semibold">모바일/콘솔 크로스플레이 활성화 (Geyser/Floodgate)</span>
                    </label>
                    <label class="flex items-center gap-2 cursor-pointer">
                        <input type="checkbox" id="srv_zgc" checked class="rounded bg-slate-800 border-slate-700 text-indigo-600 focus:ring-0">
                        <span class="text-slate-300 font-semibold">Java 21 Generational ZGC & Aikar's 최적화 주입</span>
                    </label>
                </div>

                <div class="pt-3 flex justify-end gap-2">
                    <button type="button" onclick="closeCreateModal()" class="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold">취소</button>
                    <button type="submit" id="deployBtn" class="glass-btn px-5 py-2 rounded-xl text-white font-bold shadow-md shadow-indigo-600/30">배포 시작</button>
                </div>
            </form>
        </div>
    </div>

    <!-- RCON Console Modal -->
    <div id="rconModal" class="hidden fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50">
        <div class="card max-w-xl w-full rounded-2xl p-6 space-y-4 shadow-2xl font-mono text-xs">
            <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                <span class="font-bold text-white text-sm" id="rconServerTitle">💻 서버 콘솔 (RCON)</span>
                <button onclick="closeRconModal()" class="text-slate-400 hover:text-white font-sans text-lg font-bold">&times;</button>
            </div>
            <div id="rconOutput" class="h-48 p-3 bg-black/80 rounded-xl border border-slate-800 text-emerald-400 overflow-y-auto space-y-1">
                <div>[System] RCON Secure Terminal connected. Type commands below (e.g. /say, /op, /tp, /spark).</div>
            </div>
            <form id="rconForm" class="flex gap-2 font-sans">
                <input type="text" id="rconCmd" placeholder="명령어 입력 (예: say 안녕하세요!)" class="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-slate-100 text-xs outline-none focus:border-indigo-500 font-mono" required>
                <button type="submit" class="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-xl text-xs whitespace-nowrap">전송</button>
            </form>
        </div>
    </div>

    <script>
        let myServers = [];
        let currentRconServerId = null;

        function openCreateModal() { document.getElementById('createModal').classList.remove('hidden'); }
        function closeCreateModal() { document.getElementById('createModal').classList.add('hidden'); }
        function openRconModal(id, name) {
            currentRconServerId = id;
            document.getElementById('rconServerTitle').innerText = `💻 [${name}] 서버 콘솔`;
            document.getElementById('rconModal').classList.remove('hidden');
        }
        function closeRconModal() { document.getElementById('rconModal').classList.add('hidden'); }

        function topupCredit() {
            const amount = prompt("충전할 크레딧 금액을 입력하십시오 (KRW):", "10000");
            if (amount && !isNaN(amount)) {
                let cur = parseInt(document.getElementById('userBalance').innerText.replace(/[^0-9]/g, '')) || 0;
                cur += parseInt(amount);
                document.getElementById('userBalance').innerText = cur.toLocaleString() + ' KRW';
                alert(amount + '원이 성공적으로 충전되었습니다!');
            }
        }

        document.getElementById('createForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('deployBtn');
            btn.disabled = true;
            btn.innerText = '샌드박스 컨테이너 프로비저닝 중...';

            const payload = {
                name: document.getElementById('srv_name').value,
                domain_slug: document.getElementById('srv_slug').value,
                server_type: document.getElementById('srv_type').value,
                mc_version: document.getElementById('srv_version').value,
                allocated_ram_mb: parseInt(document.getElementById('srv_ram').value),
                hardware_tier_preference: document.getElementById('srv_tier').value,
                enable_crossplay: document.getElementById('srv_crossplay').checked,
                enable_zgc: document.getElementById('srv_zgc').checked
            };

            try {
                const resp = await fetch('/api/v1/servers/deploy', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const res = await resp.json();
                if (resp.ok) {
                    alert(`🎉 서버 [${payload.name}]가 성공적으로 배포되었습니다!\\n접속 주소: ${res.connect_address}`);
                    myServers.push({
                        id: res.server_id,
                        name: payload.name,
                        address: res.connect_address,
                        type: payload.server_type,
                        ram: payload.allocated_ram_mb,
                        node: res.assigned_node,
                        status: 'RUNNING'
                    });
                    renderServers();
                    closeCreateModal();
                } else {
                    alert('서버 생성 실패: ' + (res.detail || '오류 발생'));
                }
            } catch (err) {
                alert('네트워크 오류: ' + err.message);
            } finally {
                btn.disabled = false;
                btn.innerText = '배포 시작';
            }
        });

        function renderServers() {
            const list = document.getElementById('serversList');
            const empty = document.getElementById('emptyState');
            const count = document.getElementById('serverCount');

            if (myServers.length === 0) {
                empty.classList.remove('hidden');
                count.innerText = '가동 중인 서버: 0개';
                return;
            }

            empty.classList.add('hidden');
            count.innerText = `가동 중인 서버: ${myServers.length}개`;
            list.innerHTML = '';

            myServers.forEach(srv => {
                const card = document.createElement('div');
                card.className = 'card rounded-2xl p-5 space-y-4 border border-indigo-500/20';
                card.innerHTML = `
                    <div class="flex items-center justify-between">
                        <div>
                            <span class="font-bold text-base text-white">${srv.name}</span>
                            <span class="ml-2 text-[11px] font-mono px-2 py-0.5 bg-slate-800 text-slate-300 rounded">${srv.type} (${srv.ram / 1024}GB)</span>
                        </div>
                        <span class="px-2.5 py-1 text-xs font-mono font-bold text-emerald-400 bg-emerald-950/80 rounded-full border border-emerald-500/30 flex items-center gap-1.5">
                            <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span> ${srv.status}
                        </span>
                    </div>

                    <div class="p-3 bg-slate-950/80 rounded-xl border border-slate-800 space-y-1">
                        <span class="text-[10px] text-slate-500 font-bold uppercase block">인게임 멀티플레이 접속 주소 (포트 불필요)</span>
                        <div class="flex items-center justify-between">
                            <span class="font-mono text-xs text-indigo-300 font-bold">${srv.address}</span>
                            <button onclick="navigator.clipboard.writeText('${srv.address}'); alert('접속 주소가 복사되었습니다!');" class="text-[11px] text-slate-400 hover:text-white underline">복사</button>
                        </div>
                    </div>

                    <div class="flex items-center justify-between text-xs pt-2 border-t border-slate-800/80">
                        <span class="text-slate-400">호스팅 노드: <strong class="text-slate-200">${srv.node}</strong></span>
                        <div class="flex gap-2">
                            <button onclick="openRconModal('${srv.id}', '${srv.name}')" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold rounded-lg">💻 콘솔</button>
                            <button onclick="diagnoseLag('${srv.id}')" class="px-3 py-1.5 bg-indigo-950 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-900 rounded-lg">⚡ AI 렉 진단</button>
                        </div>
                    </div>
                `;
                list.appendChild(card);
            });
        }

        document.getElementById('rconForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const input = document.getElementById('rconCmd');
            const cmd = input.value;
            const output = document.getElementById('rconOutput');

            output.innerHTML += `<div class="text-slate-300">> ${cmd}</div>`;
            input.value = '';

            try {
                const resp = await fetch(`/api/v1/servers/${currentRconServerId}/rcon`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command: cmd })
                });
                const data = await resp.json();
                output.innerHTML += `<div class="text-emerald-400">${data.response || data.detail}</div>`;
            } catch (err) {
                output.innerHTML += `<div class="text-rose-400">[Error] ${err.message}</div>`;
            }
            output.scrollTop = output.scrollHeight;
        });

        async function diagnoseLag(srvId) {
            alert('🔍 Spark Profiler 데이터를 로컬 AI(TabbyAPI)가 분석 중입니다...');
            try {
                const resp = await fetch(`/api/v1/servers/${srvId}/ai-diagnose`, { method: 'POST' });
                const res = await resp.json();
                alert(`[AI 렉 분석 결과]\\n• 원인 요약: ${res.root_cause_summary}\\n• 주요 병목: ${res.culprits.join(', ')}\\n• 권고 조치: ${res.actionable_steps.join(', ')}`);
            } catch (err) {
                alert('AI 진단 호출 실패: ' + err.message);
            }
        }
    </script>
</body>
</html>"""

# ==============================================================================
# 2. 어드민 전용 제어 대시보드 UI (Admin Control Center)
# ==============================================================================
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
    <div class="flex flex-col md:flex-row items-start md:items-center justify-between pb-6 border-b border-slate-800 gap-4">
        <div>
            <h1 class="text-3xl font-extrabold tracking-tight text-white flex items-center gap-3">
                <span class="p-2 bg-indigo-600/20 text-indigo-400 rounded-xl border border-indigo-500/30">⚙️</span>
                어드민 클러스터 & 실시간 과금 제어 센터
            </h1>
            <p class="text-sm text-slate-400 mt-1">마스터/워커 노드 자원 모니터링 및 청크·플레이어 단위 실시간 종량제 요율 제어</p>
        </div>
        <div class="flex items-center gap-3">
            <a href="/" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-semibold">👉 유저 대시보드로 이동</a>
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

            <div class="md:col-span-3 pt-4 border-t border-slate-800 space-y-3">
                <h3 class="text-xs font-bold text-slate-300 uppercase">하드웨어 스펙 티어별 과금 배율</h3>
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

    <!-- 2. Live Cluster Nodes Overview -->
    <div class="card rounded-2xl p-6 shadow-xl space-y-6">
        <div class="flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
                <h2 class="text-lg font-bold text-white">🖥️ 클러스터 노드 현황 & 가용 자원 (Master-as-Worker 지원)</h2>
                <p class="text-xs text-slate-400">마스터 노드 및 워커 노드의 CPU, RAM, ZRAM, 컨테이너 가동 현황</p>
            </div>
            <button onclick="fetchNodes()" class="text-xs text-indigo-400 hover:text-indigo-300 font-semibold underline">노드 새로고침</button>
        </div>

        <div id="nodesGrid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5"></div>
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
            } catch (err) { console.error(err); }
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
            if (resp.ok) { alert('과금 요율 수정 완료!'); fetchNodes(); }
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
                            <div class="flex justify-between text-slate-400"><span>CPU:</span><span class="font-mono font-bold text-slate-200">${node.cpu_usage_pct.toFixed(1)}%</span></div>
                            <div class="flex justify-between text-slate-400"><span>RAM (${ramPct}%):</span><span class="font-mono font-bold text-slate-200">${node.ram_used_mb}MB / ${node.ram_total_mb}MB</span></div>
                            <div class="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden"><div class="bg-indigo-500 h-full" style="width: ${ramPct}%"></div></div>
                            <div class="flex justify-between text-slate-400"><span>Active Containers:</span><span class="font-mono font-bold text-indigo-400">${node.running_containers}</span></div>
                        </div>
                        <div class="pt-3 border-t border-slate-800 flex items-center justify-between">
                            <div class="text-[11px] text-slate-400">과금 배율: <strong class="text-amber-400 font-mono text-xs">${node.billing_multiplier}x</strong></div>
                            <button onclick="changeNodeMultiplier('${node.node_id}')" class="px-2.5 py-1 text-[11px] bg-slate-800 hover:bg-slate-700 rounded text-slate-200">배율 수정</button>
                        </div>
                    `;
                    container.appendChild(card);
                });
            } catch (err) { console.error(err); }
        }

        async function changeNodeMultiplier(nodeId) {
            const val = prompt(`[${nodeId}] 노드의 새로운 과금 배율을 입력하십시오:`, "1.0");
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
    print(f"🚀 [{settings.PROJECT_NAME} v{settings.VERSION}] Master Control Plane Starting...")
    await db.connect()
    await billing_engine.initialize()

    # Master 노드 자체를 로컬 워커로 자동 등록
    scheduler.register_master_as_local_worker()

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

# 1. 일반 유저 전용 대시보드 (서버 생성, 크레딧 충전, RCON 콘솔)
@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def user_dashboard():
    """일반 고객(유저)용 서버 생성 및 크레딧 관리 웹 대시보드"""
    return USER_DASHBOARD_HTML

# 2. 어드민 전용 제어 대시보드 (노드 모니터링, 실시간 과금 요율 변경)
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard():
    """총괄 관리자용 클러스터 노드 및 실시간 과금 요율 제어 센터"""
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
    uvicorn.run("app.main:app", host="0.0.0.0", port=8005, reload=True)
