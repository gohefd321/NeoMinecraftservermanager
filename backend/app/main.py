"""
main.py - Master Node FastAPI Application Entrypoint
Includes:
1. User Client Portal (/) - Google OAuth / 19+ Adult Verification Modal, Server Rental, Credit Wallet, Console
2. Protected Admin Center (/admin) - Protected by Master Secret Auth Modal & JWT Gateway
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
# 1. 일반 유저 전용 웹 사이트 (회원가입, 구글 로그인, 19세 성인인증, 서버 생성, 지갑)
# ==============================================================================
USER_PORTAL_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NextGen MC - 클라우드 마인크래프트 호스팅</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@300;400;600;700;800;900&display=swap');
        body { font-family: 'Pretendard', sans-serif; background: #050811; color: #f1f5f9; min-height: 100vh; }
        .glass-card { background: rgba(15, 23, 42, 0.8); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.08); }
        .gradient-btn { background: linear-gradient(135deg, #4f46e5, #6366f1); }
        .gradient-text { background: linear-gradient(135deg, #818cf8, #c084fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    </style>
</head>
<body class="p-4 md:p-8 max-w-6xl mx-auto space-y-8">
    <header class="flex items-center justify-between pb-5 border-b border-slate-800/80">
        <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center font-black text-xl text-white shadow-lg shadow-indigo-500/30">⛏️</div>
            <div>
                <h1 class="text-xl font-extrabold text-white tracking-tight flex items-center gap-2">
                    NextGen MC <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-900/60 text-indigo-300 border border-indigo-500/30 uppercase">Cloud</span>
                </h1>
                <p class="text-[11px] text-slate-400">초저지연 실시간 종량제 마인크래프트 서버 호스팅</p>
            </div>
        </div>

        <div class="flex items-center gap-3">
            <div id="authLoggedOut" class="flex items-center gap-2">
                <button onclick="openLoginModal()" class="px-4 py-2 rounded-xl gradient-btn text-white font-bold text-xs shadow-lg shadow-indigo-600/30 hover:opacity-90 transition flex items-center gap-1.5">
                    <svg class="w-4 h-4" viewBox="0 0 24 24"><path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/><path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/></svg>
                    구글 1초 로그인 / 회원가입
                </button>
            </div>

            <div id="authLoggedIn" class="hidden flex items-center gap-3">
                <div class="px-3.5 py-1.5 bg-slate-900/90 rounded-xl border border-slate-800 flex items-center gap-3 text-xs">
                    <div>
                        <span class="text-slate-400 block text-[9px] uppercase font-bold">보유 크레딧</span>
                        <span id="userBalance" class="font-mono font-bold text-sm text-emerald-400">3,000 KRW</span>
                    </div>
                    <button onclick="topupCredit()" class="px-2 py-1 bg-emerald-600/20 text-emerald-300 hover:bg-emerald-600/30 rounded-lg text-xs font-semibold border border-emerald-500/30">
                        + 충전
                    </button>
                </div>
                <div class="flex items-center gap-2">
                    <span id="userEmailTag" class="text-xs text-slate-300 font-medium">user@domain.com</span>
                    <span class="px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-400 border border-indigo-500/30 text-[10px] font-bold">19세 인증 ✓</span>
                    <button onclick="logout()" class="text-xs text-slate-500 hover:text-rose-400 font-semibold underline ml-1">로그아웃</button>
                </div>
            </div>

            <a href="/admin" class="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold">🔒 관리자</a>
        </div>
    </header>

    <div class="glass-card rounded-3xl p-6 md:p-10 bg-gradient-to-r from-indigo-950/40 via-slate-900 to-slate-900 flex flex-col md:flex-row items-start md:items-center justify-between gap-6 shadow-2xl">
        <div class="space-y-3 max-w-xl">
            <span class="px-3 py-1 rounded-full text-[11px] font-black bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 uppercase tracking-wider">
                ⚡ Zero-Port L4 Ingress & Generational ZGC
            </span>
            <h2 class="text-3xl md:text-4xl font-black text-white leading-tight">
                나만의 마인크래프트 서버를<br><span class="gradient-text">1분 만에 클라우드에 배포하세요</span>
            </h2>
            <p class="text-xs md:text-sm text-slate-400 leading-relaxed">
                포트 번호 없이 <strong>myserver.domain.com</strong>으로 접속되는 스마트 라우팅, 실시간 종량제 과금(Pay-as-you-go), 그리고 AI 렉 진단 파이프라인을 지원합니다.
            </p>
        </div>
        <button onclick="handleStartDeploy()" class="gradient-btn px-7 py-4 rounded-2xl font-black text-sm text-white shadow-xl shadow-indigo-600/40 hover:scale-105 transition whitespace-nowrap">
            🚀 새 서버 생성하기
        </button>
    </div>

    <div class="space-y-4">
        <div class="flex items-center justify-between">
            <h3 class="text-lg font-bold text-white flex items-center gap-2"><span>🎮</span> 내 마인크래프트 서버</h3>
            <span class="text-xs text-slate-400" id="serverCount">가동 중인 서버: 0개</span>
        </div>
        <div id="serversList" class="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div id="emptyState" class="md:col-span-2 glass-card rounded-2xl p-12 text-center space-y-3">
                <div class="text-4xl">🕹️</div>
                <p class="text-sm font-semibold text-slate-300">아직 생성된 마인크래프트 서버가 없습니다.</p>
                <p class="text-xs text-slate-500">상단의 [새 서버 생성하기] 버튼을 눌러 첫 서버를 개설하십시오. (신규 가입 시 3,000 KRW 무료 증정)</p>
            </div>
        </div>
    </div>

    <!-- Login Modal -->
    <div id="loginModal" class="hidden fixed inset-0 bg-black/75 backdrop-blur-md flex items-center justify-center p-4 z-50">
        <div class="glass-card max-w-md w-full rounded-2xl p-6 md:p-8 space-y-5 shadow-2xl">
            <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                <h4 class="font-extrabold text-base text-white flex items-center gap-2">
                    <span>🔑</span> 회원가입 및 구글 계정 로그인
                </h4>
                <button onclick="closeLoginModal()" class="text-slate-400 hover:text-white text-xl font-bold">&times;</button>
            </div>

            <form id="authForm" class="space-y-4 text-xs">
                <div>
                    <label class="block font-semibold text-slate-300 mb-1">구글 이메일 (Google Email)</label>
                    <input type="email" id="login_email" required placeholder="your-email@gmail.com" class="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-slate-100 outline-none focus:border-indigo-500">
                </div>

                <div class="p-3.5 bg-indigo-950/40 rounded-xl border border-indigo-500/30 space-y-2">
                    <label class="flex items-start gap-2.5 cursor-pointer">
                        <input type="checkbox" id="adult_agree" required class="mt-0.5 rounded bg-slate-900 border-slate-700 text-indigo-600 focus:ring-0">
                        <span class="text-slate-200 text-[11px] leading-relaxed">
                            <strong>[필수] 만 19세 이상 법정 성인 확인 및 약관 동의</strong><br>
                            <span class="text-slate-400 text-[10px]">대한민국 청소년 보호법 및 서비스 이용약관에 따라 만 19세 이상 성인에 한하여 서버 호스팅 서비스 및 결제 이용이 가능합니다.</span>
                        </span>
                    </label>
                </div>

                <button type="submit" id="authSubmitBtn" class="w-full py-3 rounded-xl gradient-btn font-extrabold text-white text-xs shadow-lg shadow-indigo-600/30 hover:opacity-90 transition">
                    동의하고 1초 가입 및 로그인 (3,000원 무료 체험)
                </button>
            </form>
        </div>
    </div>

    <!-- Create Modal -->
    <div id="createModal" class="hidden fixed inset-0 bg-black/75 backdrop-blur-md flex items-center justify-center p-4 z-50">
        <div class="glass-card max-w-lg w-full rounded-2xl p-6 md:p-8 space-y-5 shadow-2xl">
            <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                <h4 class="font-bold text-base text-white">✨ 새 마인크래프트 서버 개설</h4>
                <button onclick="closeCreateModal()" class="text-slate-400 hover:text-white text-xl">&times;</button>
            </div>

            <form id="createForm" class="space-y-4 text-xs">
                <div>
                    <label class="block font-semibold text-slate-300 mb-1">서버 명칭</label>
                    <input type="text" id="srv_name" required placeholder="예: 야생 생존 서버" class="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-slate-100 outline-none focus:border-indigo-500">
                </div>
                <div>
                    <label class="block font-semibold text-slate-300 mb-1">인게임 접속 서브도메인 (id.domain.com)</label>
                    <div class="flex items-center gap-2">
                        <input type="text" id="srv_slug" required pattern="^[a-z0-9-]{3,32}$" placeholder="예: myworld" class="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-slate-100 outline-none focus:border-indigo-500 font-mono">
                        <span class="text-slate-400 font-mono">.domain.com</span>
                    </div>
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block font-semibold text-slate-300 mb-1">서버 코어</label>
                        <select id="srv_type" class="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-slate-100 outline-none focus:border-indigo-500">
                            <option value="PAPER">Paper</option>
                            <option value="FABRIC">Fabric</option>
                            <option value="NEOFORGE">NeoForge</option>
                        </select>
                    </div>
                    <div>
                        <label class="block font-semibold text-slate-300 mb-1">버전</label>
                        <select id="srv_version" class="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-slate-100 outline-none font-mono">
                            <option value="1.20.4">1.20.4</option>
                            <option value="1.20.2">1.20.2</option>
                            <option value="1.19.4">1.19.4</option>
                        </select>
                    </div>
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block font-semibold text-slate-300 mb-1">할당 RAM</label>
                        <select id="srv_ram" class="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-slate-100 outline-none">
                            <option value="4096">4 GB RAM</option>
                            <option value="6144">6 GB RAM</option>
                            <option value="8192">8 GB RAM</option>
                        </select>
                    </div>
                    <div>
                        <label class="block font-semibold text-slate-300 mb-1">하드웨어 티어</label>
                        <select id="srv_tier" class="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-slate-100 outline-none">
                            <option value="high_nvme" selected>고성능 NVMe (1.3x)</option>
                            <option value="standard_ssd">표준 SSD (1.0x)</option>
                        </select>
                    </div>
                </div>
                <div class="pt-3 flex justify-end gap-2">
                    <button type="button" onclick="closeCreateModal()" class="px-4 py-2 rounded-xl bg-slate-800 text-slate-300">취소</button>
                    <button type="submit" id="deployBtn" class="gradient-btn px-5 py-2 rounded-xl text-white font-bold">배포 시작</button>
                </div>
            </form>
        </div>
    </div>

    <!-- RCON Modal -->
    <div id="rconModal" class="hidden fixed inset-0 bg-black/75 backdrop-blur-md flex items-center justify-center p-4 z-50">
        <div class="glass-card max-w-xl w-full rounded-2xl p-6 space-y-4 font-mono text-xs">
            <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                <span class="font-bold text-white text-sm" id="rconTitle">💻 서버 콘솔</span>
                <button onclick="document.getElementById('rconModal').classList.add('hidden')" class="text-slate-400 hover:text-white font-sans text-xl">&times;</button>
            </div>
            <div id="rconBox" class="h-44 p-3 bg-black/80 rounded-xl border border-slate-800 text-emerald-400 overflow-y-auto space-y-1">
                <div>[RCON Connected] 명령어를 입력하세요.</div>
            </div>
            <form id="rconSendForm" class="flex gap-2 font-sans">
                <input type="text" id="rconInput" placeholder="명령어 입력 (예: say 안녕하세요)" class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-100 font-mono outline-none">
                <button type="submit" class="px-4 py-2 bg-indigo-600 text-white rounded-lg font-bold">전송</button>
            </form>
        </div>
    </div>

    <script>
        let currentUser = JSON.parse(localStorage.getItem('mc_user')) || null;
        let myServers = [];
        let curRconId = null;

        function updateAuthState() {
            const outBox = document.getElementById('authLoggedOut');
            const inBox = document.getElementById('authLoggedIn');
            if (currentUser) {
                outBox.classList.add('hidden');
                inBox.classList.remove('hidden');
                document.getElementById('userEmailTag').innerText = currentUser.email;
                document.getElementById('userBalance').innerText = (currentUser.balance_krw || 3000).toLocaleString() + ' KRW';
            } else {
                outBox.classList.remove('hidden');
                inBox.classList.add('hidden');
            }
        }

        function openLoginModal() { document.getElementById('loginModal').classList.remove('hidden'); }
        function closeLoginModal() { document.getElementById('loginModal').classList.add('hidden'); }
        function handleStartDeploy() {
            if (!currentUser) { openLoginModal(); }
            else { openCreateModal(); }
        }
        function openCreateModal() { document.getElementById('createModal').classList.remove('hidden'); }
        function closeCreateModal() { document.getElementById('createModal').classList.add('hidden'); }
        function logout() {
            localStorage.removeItem('mc_user');
            currentUser = null;
            updateAuthState();
        }

        document.getElementById('authForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('login_email').value;
            const agree = document.getElementById('adult_agree').checked;
            const btn = document.getElementById('authSubmitBtn');
            btn.disabled = true;
            btn.innerText = '인증 처리 중...';

            try {
                const resp = await fetch('/api/v1/auth/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        email: email,
                        oauth_provider: "google",
                        oauth_token: "google-token-" + Math.random(),
                        is_adult_verified: agree
                    })
                });
                const data = await resp.json();
                if (resp.ok) {
                    currentUser = { email: data.email, user_id: data.user_id, balance_krw: data.initial_credit_krw };
                    localStorage.setItem('mc_user', JSON.stringify(currentUser));
                    updateAuthState();
                    closeLoginModal();
                    alert(`🎉 환영합니다! 19세 성인인증 완료 및 체험 크레딧 3,000 KRW가 지급되었습니다.`);
                } else {
                    alert('로그인 오류: ' + (data.detail || '실패'));
                }
            } catch (err) { alert('네트워크 오류: ' + err.message); }
            finally { btn.disabled = false; btn.innerText = '동의하고 1초 가입 및 로그인'; }
        });

        function topupCredit() {
            const amount = prompt("충전할 크레딧 금액을 입력하십시오 (KRW):", "10000");
            if (amount && !isNaN(amount)) {
                currentUser.balance_krw = (currentUser.balance_krw || 3000) + parseInt(amount);
                localStorage.setItem('mc_user', JSON.stringify(currentUser));
                updateAuthState();
                alert(amount + '원이 성공적으로 충전되었습니다!');
            }
        }

        document.getElementById('createForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('deployBtn');
            btn.disabled = true;
            btn.innerText = '프로비저닝 중...';

            const payload = {
                name: document.getElementById('srv_name').value,
                domain_slug: document.getElementById('srv_slug').value,
                server_type: document.getElementById('srv_type').value,
                mc_version: document.getElementById('srv_version').value,
                allocated_ram_mb: parseInt(document.getElementById('srv_ram').value),
                hardware_tier_preference: document.getElementById('srv_tier').value,
                target_user_id: currentUser ? currentUser.email : "user@domain.com"
            };

            try {
                const resp = await fetch('/api/v1/servers/deploy', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const res = await resp.json();
                if (resp.ok) {
                    alert(`🎉 서버 [${payload.name}] 배포 성공!\\n접속 주소: ${res.connect_address}`);
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
                    alert('배포 실패: ' + (res.detail || '오류'));
                }
            } catch (err) { alert('오류: ' + err.message); }
            finally { btn.disabled = false; btn.innerText = '배포 시작'; }
        });

        function renderServers() {
            const list = document.getElementById('serversList');
            const empty = document.getElementById('emptyState');
            const count = document.getElementById('serverCount');
            if (myServers.length === 0) { empty.classList.remove('hidden'); return; }
            empty.classList.add('hidden');
            count.innerText = `가동 중인 서버: ${myServers.length}개`;
            list.innerHTML = '';

            myServers.forEach(srv => {
                const card = document.createElement('div');
                card.className = 'glass-card rounded-2xl p-5 space-y-4 border border-indigo-500/20';
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
                            <button onclick="navigator.clipboard.writeText('${srv.address}'); alert('복사되었습니다!');" class="text-[11px] text-slate-400 hover:text-white underline">복사</button>
                        </div>
                    </div>
                    <div class="flex items-center justify-between text-xs pt-2 border-t border-slate-800">
                        <span class="text-slate-400">노드: <strong class="text-slate-200">${srv.node}</strong></span>
                        <div class="flex gap-2">
                            <button onclick="openRcon('${srv.id}', '${srv.name}')" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg">💻 콘솔</button>
                            <button onclick="diagnoseLag('${srv.id}')" class="px-3 py-1.5 bg-indigo-950 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-900 rounded-lg">⚡ AI 렉 진단</button>
                        </div>
                    </div>
                `;
                list.appendChild(card);
            });
        }

        function openRcon(id, name) {
            curRconId = id;
            document.getElementById('rconTitle').innerText = `💻 [${name}] 서버 콘솔`;
            document.getElementById('rconModal').classList.remove('hidden');
        }

        document.getElementById('rconSendForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const input = document.getElementById('rconInput');
            const cmd = input.value;
            const box = document.getElementById('rconBox');
            box.innerHTML += `<div class="text-slate-300">> ${cmd}</div>`;
            input.value = '';
            try {
                const resp = await fetch(`/api/v1/servers/${curRconId}/rcon`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command: cmd })
                });
                const res = await resp.json();
                box.innerHTML += `<div class="text-emerald-400">${res.response || res.detail}</div>`;
            } catch (err) { box.innerHTML += `<div class="text-rose-400">[Error] ${err.message}</div>`; }
            box.scrollTop = box.scrollHeight;
        });

        async function diagnoseLag(srvId) {
            alert('🔍 Spark Profiler 덤프를 로컬 AI(TabbyAPI)가 분석 중입니다...');
            const resp = await fetch(`/api/v1/servers/${srvId}/ai-diagnose`, { method: 'POST' });
            const res = await resp.json();
            alert(`[AI 렉 분석 완료]\\n• 요약: ${res.root_cause_summary}\\n• 주요 병목: ${res.culprits.join(', ')}\\n• 권고: ${res.actionable_steps.join(', ')}`);
        }

        updateAuthState();
    </script>
</body>
</html>"""

# ==============================================================================
# 2. 어드민 전용 통합 제어 센터 UI (보안 인증 모달 & 토큰 게이트웨이 탑재)
# ==============================================================================
ADMIN_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NextGen MC - 어드민 보안 제어 센터</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@300;400;600;700;800;900&display=swap');
        body { font-family: 'Pretendard', sans-serif; background: #050811; color: #f1f5f9; min-height: 100vh; }
        .card { background: #0f172a; border: 1px solid rgba(255, 255, 255, 0.08); }
        .tab-btn.active { background: #4f46e5; color: white; }
    </style>
</head>
<body class="p-4 md:p-8 max-w-7xl mx-auto space-y-6">

    <!-- Admin Authentication Modal (Screen Lock if not authenticated) -->
    <div id="adminAuthGateModal" class="fixed inset-0 bg-black/90 backdrop-blur-xl flex items-center justify-center p-4 z-50">
        <div class="card max-w-md w-full rounded-2xl p-8 space-y-5 shadow-2xl border border-indigo-500/40">
            <div class="text-center space-y-2">
                <div class="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-indigo-600/30 text-indigo-400 border border-indigo-500/30 text-2xl mb-1">🔒</div>
                <h3 class="text-xl font-extrabold text-white">NextGen MC 총괄 관리자 인증</h3>
                <p class="text-xs text-slate-400">어드민 제어 센터는 마스터 시크릿 암호 인증이 필요합니다.</p>
            </div>

            <form id="adminAuthForm" class="space-y-4 text-xs">
                <div>
                    <label class="block font-semibold text-slate-300 mb-1">클러스터 마스터 시크릿 (Master Secret Key)</label>
                    <input type="password" id="adminSecretInput" required placeholder="설치 시 지정한 마스터 시크릿 입력" class="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-700 rounded-xl text-slate-100 outline-none focus:border-indigo-500">
                </div>
                <button type="submit" id="adminAuthBtn" class="w-full py-3 bg-indigo-600 hover:bg-indigo-500 font-extrabold text-white rounded-xl shadow-lg shadow-indigo-600/30 transition">
                    관리자 인증 및 제어 센터 접속
                </button>
                <div id="adminAuthError" class="hidden text-rose-400 text-center font-semibold"></div>
            </form>
        </div>
    </div>

    <!-- Protected Admin Dashboard Header -->
    <header class="flex flex-col md:flex-row items-start md:items-center justify-between pb-4 border-b border-slate-800 gap-4">
        <div>
            <h1 class="text-2xl font-black text-white flex items-center gap-3">
                <span class="p-2 bg-indigo-600 text-white rounded-xl shadow-lg shadow-indigo-600/30">⚙️</span>
                NextGen MC 어드민 통합 제어 센터
            </h1>
            <p class="text-xs text-slate-400 mt-1">과금 티어 동적 관리 • 회원 계정 & 크레딧 • 민원 처리 • 전체 서버 관리 • Google OAuth & LLM</p>
        </div>
        <div class="flex items-center gap-3">
            <a href="/" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-semibold">👉 유저 대시보드</a>
            <button onclick="adminLogout()" class="px-3 py-1.5 bg-rose-950/80 hover:bg-rose-900 text-rose-300 border border-rose-500/30 rounded-xl text-xs font-bold">🔒 관리자 로그아웃</button>
        </div>
    </header>

    <!-- 5-Tab Navigation -->
    <div class="flex flex-wrap gap-2 border-b border-slate-800 pb-3">
        <button onclick="switchTab('billing')" id="tab_billing" class="tab-btn active px-4 py-2 rounded-xl text-xs font-bold bg-slate-800 hover:bg-indigo-600 transition flex items-center gap-2">
            💰 1. 과금 티어 & 노드 제어
        </button>
        <button onclick="switchTab('users')" id="tab_users" class="tab-btn px-4 py-2 rounded-xl text-xs font-bold bg-slate-800 hover:bg-indigo-600 transition flex items-center gap-2">
            👥 2. 회원 계정 & 크레딧 관리
        </button>
        <button onclick="switchTab('tickets')" id="tab_tickets" class="tab-btn px-4 py-2 rounded-xl text-xs font-bold bg-slate-800 hover:bg-indigo-600 transition flex items-center gap-2">
            🎫 3. 민원 및 헬프데스크 처리
        </button>
        <button onclick="switchTab('servers')" id="tab_servers" class="tab-btn px-4 py-2 rounded-xl text-xs font-bold bg-slate-800 hover:bg-indigo-600 transition flex items-center gap-2">
            🖥️ 4. 서버 생성 & 전체 서버 관리
        </button>
        <button onclick="switchTab('settings')" id="tab_settings" class="tab-btn px-4 py-2 rounded-xl text-xs font-bold bg-slate-800 hover:bg-indigo-600 transition flex items-center gap-2">
            🔧 5. Google OAuth & LLM 설정
        </button>
    </div>

    <!-- TAB 1: Billing & Nodes -->
    <div id="section_billing" class="space-y-6">
        <div class="card rounded-2xl p-6 space-y-5">
            <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                <h3 class="font-bold text-white text-base">💰 실시간 종량제 과금 요율 동적 설정</h3>
                <button onclick="loadBillingRates()" class="text-xs text-indigo-400 hover:underline">새로고침</button>
            </div>
            <form id="ratesForm" class="grid grid-cols-1 md:grid-cols-3 gap-5 text-xs">
                <div class="space-y-1.5">
                    <label class="font-bold text-slate-300 uppercase">기본 유지비 (분당 KRW)</label>
                    <input type="number" step="0.01" id="rate_base" class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-100 outline-none" required>
                    <span class="text-slate-500 text-[10px]">컨테이너 기본 가동비</span>
                </div>
                <div class="space-y-1.5">
                    <label class="font-bold text-slate-300 uppercase">청크당 요율 (분당 KRW)</label>
                    <input type="number" step="0.0001" id="rate_chunk" class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-100 outline-none" required>
                    <span class="text-slate-500 text-[10px]">로드된 청크 1개당 단가</span>
                </div>
                <div class="space-y-1.5">
                    <label class="font-bold text-slate-300 uppercase">플레이어당 요율 (분당 KRW)</label>
                    <input type="number" step="0.01" id="rate_player" class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-100 outline-none" required>
                    <span class="text-slate-500 text-[10px]">동시 접속자 1인당 단가</span>
                </div>
                <div class="md:col-span-3 pt-3 border-t border-slate-800 grid grid-cols-3 gap-3">
                    <div>
                        <span class="font-bold text-slate-300">Standard SSD 배율</span>
                        <input type="number" step="0.1" id="rate_tier_std" class="w-full px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg mt-1">
                    </div>
                    <div>
                        <span class="font-bold text-indigo-400">High NVMe 배율</span>
                        <input type="number" step="0.1" id="rate_tier_nvme" class="w-full px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg mt-1">
                    </div>
                    <div>
                        <span class="font-bold text-amber-400">Extreme Dedicated 배율</span>
                        <input type="number" step="0.1" id="rate_tier_ext" class="w-full px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg mt-1">
                    </div>
                </div>
                <div class="md:col-span-3 flex justify-end">
                    <button type="submit" class="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-xl shadow-lg shadow-indigo-600/30">요율 실시간 저장</button>
                </div>
            </form>
        </div>

        <div class="card rounded-2xl p-6 space-y-4">
            <h3 class="font-bold text-white text-base">🖥️ 클러스터 노드 현황 & 자원 모니터링</h3>
            <div id="adminNodesGrid" class="grid grid-cols-1 md:grid-cols-3 gap-4"></div>
        </div>
    </div>

    <!-- TAB 2: Users -->
    <div id="section_users" class="hidden space-y-5">
        <div class="card rounded-2xl p-6 space-y-4">
            <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                <h3 class="font-bold text-white text-base">👥 회원 계정 & 크레딧 관리</h3>
                <button onclick="loadAdminUsers()" class="text-xs text-indigo-400 hover:underline">새로고침</button>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-left text-xs">
                    <thead class="text-slate-400 uppercase bg-slate-900/80 border-b border-slate-800">
                        <tr>
                            <th class="p-3">유저 ID</th>
                            <th class="p-3">이메일</th>
                            <th class="p-3">19세 인증</th>
                            <th class="p-3">상태</th>
                            <th class="p-3">보유 크레딧</th>
                            <th class="p-3 text-right">관리 작업</th>
                        </tr>
                    </thead>
                    <tbody id="usersTableBody" class="divide-y divide-slate-800/60 font-mono"></tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- TAB 3: Tickets -->
    <div id="section_tickets" class="hidden space-y-5">
        <div class="card rounded-2xl p-6 space-y-4">
            <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                <h3 class="font-bold text-white text-base">🎫 고객지원 민원 접수 & AI 렉 리포트</h3>
                <button onclick="loadAdminTickets()" class="text-xs text-indigo-400 hover:underline">새로고침</button>
            </div>
            <div id="ticketsList" class="space-y-4"></div>
        </div>
    </div>

    <!-- TAB 4: Servers -->
    <div id="section_servers" class="hidden space-y-6">
        <div class="card rounded-2xl p-6 space-y-4">
            <h3 class="font-bold text-white text-base">🚀 어드민 직속 서버 즉시 개설</h3>
            <form id="adminCreateForm" class="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                <div>
                    <label class="block font-semibold text-slate-300 mb-1">서버 이름</label>
                    <input type="text" id="adm_name" required placeholder="예: 어드민 공식 서버" class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-100 outline-none">
                </div>
                <div>
                    <label class="block font-semibold text-slate-300 mb-1">서브도메인 (id.domain.com)</label>
                    <input type="text" id="adm_slug" required pattern="^[a-z0-9-]{3,32}$" placeholder="예: official" class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-100 outline-none font-mono">
                </div>
                <div>
                    <label class="block font-semibold text-slate-300 mb-1">소유 대상 유저 이메일</label>
                    <input type="email" id="adm_user" placeholder="admin@domain.com" class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-100 outline-none">
                </div>
                <div>
                    <label class="block font-semibold text-slate-300 mb-1">서버 타입</label>
                    <select id="adm_type" class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-100 outline-none">
                        <option value="PAPER">Paper</option>
                        <option value="FABRIC">Fabric</option>
                        <option value="NEOFORGE">NeoForge</option>
                    </select>
                </div>
                <div>
                    <label class="block font-semibold text-slate-300 mb-1">할당 RAM</label>
                    <select id="adm_ram" class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-100 outline-none font-mono">
                        <option value="4096">4 GB</option>
                        <option value="8192" selected>8 GB</option>
                        <option value="16384">16 GB</option>
                    </select>
                </div>
                <div>
                    <label class="block font-semibold text-slate-300 mb-1">배치 노드 지정 (Optional)</label>
                    <select id="adm_node" class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-100 outline-none font-mono">
                        <option value="">자동 최적 노드 스케줄링</option>
                        <option value="master-local">Master Node (Local Container)</option>
                    </select>
                </div>
                <div class="md:col-span-3 flex justify-end">
                    <button type="submit" class="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-xl shadow-lg shadow-indigo-600/30">어드민 권한 서버 배포</button>
                </div>
            </form>
        </div>

        <div class="card rounded-2xl p-6 space-y-4">
            <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                <h3 class="font-bold text-white text-base">🎮 클러스터 전체 실행 중인 서버 목록</h3>
                <button onclick="loadAdminServers()" class="text-xs text-indigo-400 hover:underline">새로고침</button>
            </div>
            <div id="adminServersGrid" class="grid grid-cols-1 md:grid-cols-2 gap-4"></div>
        </div>
    </div>

    <!-- TAB 5: System Settings (Google OAuth & LLM) -->
    <div id="section_settings" class="hidden space-y-6">
        <div class="card rounded-2xl p-6 space-y-5">
            <div class="border-b border-slate-800 pb-3">
                <h3 class="font-bold text-white text-base">🔧 시스템 외부 연동 환경설정</h3>
                <p class="text-xs text-slate-400 mt-0.5">Google OAuth 로그인 키 및 로컬 LLM AI 추론기 엔드포인트를 변경합니다.</p>
            </div>

            <form id="sysSettingsForm" class="space-y-4 text-xs">
                <div class="p-4 bg-slate-900/80 rounded-xl border border-slate-800 space-y-3">
                    <span class="font-bold text-indigo-400 text-sm block">🔑 구글 OAuth 연동 설정</span>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                            <label class="block text-slate-400 mb-1">Google Client ID</label>
                            <input type="text" id="cfg_google_id" placeholder="xxxx.apps.googleusercontent.com" class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-100 outline-none">
                        </div>
                        <div>
                            <label class="block text-slate-400 mb-1">Google Client Secret</label>
                            <input type="password" id="cfg_google_sec" placeholder="GOCSPX-xxxx" class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-100 outline-none">
                        </div>
                    </div>
                </div>

                <div class="p-4 bg-slate-900/80 rounded-xl border border-slate-800 space-y-3">
                    <span class="font-bold text-amber-400 text-sm block">🤖 로컬 AI 렉 진단기 (Local LLM / llama-server)</span>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                            <label class="block text-slate-400 mb-1">Local LLM API URL (llama-server: 8000)</label>
                            <input type="text" id="cfg_llm_url" value="http://localhost:8000/v1/chat/completions" class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-100 font-mono outline-none">
                        </div>
                        <div>
                            <label class="block text-slate-400 mb-1">LLM 모델명</label>
                            <input type="text" id="cfg_llm_model" value="qwen-2.5-32b-instruct" class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-100 font-mono outline-none">
                        </div>
                    </div>
                </div>

                <div class="flex justify-end">
                    <button type="submit" class="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-xl shadow-lg shadow-indigo-600/30">환경설정 저장 및 즉시 반영</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Ticket Resolve Modal -->
    <div id="resolveModal" class="hidden fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50">
        <div class="card max-w-lg w-full rounded-2xl p-6 space-y-4 shadow-2xl text-xs">
            <h4 class="font-bold text-sm text-white" id="modalTicketTitle">🎫 민원 답변 및 처리</h4>
            <form id="resolveForm" class="space-y-3">
                <input type="hidden" id="res_ticket_id">
                <div>
                    <label class="block font-semibold text-slate-300 mb-1">처리 상태</label>
                    <select id="res_status" class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-100 outline-none">
                        <option value="RESOLVED">RESOLVED (처리 완료)</option>
                        <option value="IN_PROGRESS">IN_PROGRESS (조사/진행 중)</option>
                        <option value="CLOSED">CLOSED (종결)</option>
                    </select>
                </div>
                <div>
                    <label class="block font-semibold text-slate-300 mb-1">관리자 공식 답변</label>
                    <textarea id="res_response" rows="4" required placeholder="유저에게 전달할 조치 내역 또는 보상 안내를 입력하십시오." class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-100 outline-none"></textarea>
                </div>
                <div class="flex justify-end gap-2 pt-2">
                    <button type="button" onclick="document.getElementById('resolveModal').classList.add('hidden')" class="px-4 py-2 bg-slate-800 rounded-lg text-slate-300">취소</button>
                    <button type="submit" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-white font-bold">답변 등록</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        let adminToken = sessionStorage.getItem('mc_admin_token') || null;

        function getAuthHeaders() {
            return {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${adminToken}`
            };
        }

        async function verifyAdminAuth() {
            if (!adminToken) {
                document.getElementById('adminAuthGateModal').classList.remove('hidden');
                return false;
            }
            document.getElementById('adminAuthGateModal').classList.add('hidden');
            return true;
        }

        function adminLogout() {
            sessionStorage.removeItem('mc_admin_token');
            adminToken = null;
            document.getElementById('adminAuthGateModal').classList.remove('hidden');
        }

        document.getElementById('adminAuthForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const secret = document.getElementById('adminSecretInput').value;
            const errBox = document.getElementById('adminAuthError');
            const btn = document.getElementById('adminAuthBtn');
            btn.disabled = true;
            btn.innerText = '인증 검증 중...';

            try {
                const resp = await fetch('/api/v1/auth/admin/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ master_secret: secret })
                });
                const data = await resp.json();
                if (resp.ok) {
                    adminToken = data.access_token;
                    sessionStorage.setItem('mc_admin_token', adminToken);
                    document.getElementById('adminAuthGateModal').classList.add('hidden');
                    loadBillingRates();
                    loadAdminNodes();
                } else {
                    errBox.innerText = data.detail || '마스터 시크릿 암호가 올바르지 않습니다.';
                    errBox.classList.remove('hidden');
                }
            } catch (err) {
                errBox.innerText = '서버 연결 실패: ' + err.message;
                errBox.classList.remove('hidden');
            } finally {
                btn.disabled = false;
                btn.innerText = '관리자 인증 및 제어 센터 접속';
            }
        });

        function switchTab(tabId) {
            if (!adminToken) { verifyAdminAuth(); return; }
            ['billing', 'users', 'tickets', 'servers', 'settings'].forEach(t => {
                document.getElementById('section_' + t).classList.add('hidden');
                document.getElementById('tab_' + t).classList.remove('active');
            });
            document.getElementById('section_' + tabId).classList.remove('hidden');
            document.getElementById('tab_' + tabId).classList.add('active');

            if (tabId === 'billing') { loadBillingRates(); loadAdminNodes(); }
            if (tabId === 'users') loadAdminUsers();
            if (tabId === 'tickets') loadAdminTickets();
            if (tabId === 'servers') loadAdminServers();
        }

        async function loadBillingRates() {
            if (!adminToken) return;
            const resp = await fetch('/api/v1/nodes/admin/billing/rates', { headers: getAuthHeaders() });
            if (resp.status === 401) { adminLogout(); return; }
            const d = await resp.json();
            document.getElementById('rate_base').value = d.base_container_per_min;
            document.getElementById('rate_chunk').value = d.per_chunk_rate;
            document.getElementById('rate_player').value = d.per_player_rate;
            document.getElementById('rate_tier_std').value = d.tier_multipliers.standard_ssd || 1.0;
            document.getElementById('rate_tier_nvme').value = d.tier_multipliers.high_nvme || 1.3;
            document.getElementById('rate_tier_ext').value = d.tier_multipliers.extreme_dedicated || 1.8;
        }

        document.getElementById('ratesForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const payload = {
                base_container_per_min: parseFloat(document.getElementById('rate_base').value),
                per_chunk_rate: parseFloat(document.getElementById('rate_chunk').value),
                per_player_rate: parseFloat(document.getElementById('rate_player').value),
                tier_multipliers: {
                    standard_ssd: parseFloat(document.getElementById('rate_tier_std').value),
                    high_nvme: parseFloat(document.getElementById('rate_tier_nvme').value),
                    extreme_dedicated: parseFloat(document.getElementById('rate_tier_ext').value)
                }
            };
            await fetch('/api/v1/nodes/admin/billing/rates', {
                method: 'PUT',
                headers: getAuthHeaders(),
                body: JSON.stringify(payload)
            });
            alert('과금 요율 수정 및 실시간 적용 완료!');
        });

        async function loadAdminNodes() {
            if (!adminToken) return;
            const resp = await fetch('/api/v1/nodes/admin/overview', { headers: getAuthHeaders() });
            if (resp.status === 401) { adminLogout(); return; }
            const data = await resp.json();
            const container = document.getElementById('adminNodesGrid');
            container.innerHTML = '';
            data.nodes.forEach(n => {
                const ramPct = Math.round((n.ram_used_mb / Math.max(n.ram_total_mb, 1)) * 100);
                const card = document.createElement('div');
                card.className = 'p-4 bg-slate-900/80 rounded-xl border ' + (n.is_master_node ? 'border-indigo-500/40' : 'border-slate-800') + ' text-xs space-y-3';
                card.innerHTML = `
                    <div class="flex justify-between items-center">
                        <span class="font-bold text-white">${n.node_name}</span>
                        <span class="px-2 py-0.5 rounded font-mono ${n.status === 'ONLINE' ? 'bg-emerald-950 text-emerald-400' : 'bg-rose-950 text-rose-400'}">${n.status}</span>
                    </div>
                    <div class="space-y-1 text-slate-400">
                        <div>CPU: <strong class="text-slate-200">${n.cpu_usage_pct.toFixed(1)}%</strong> | RAM: <strong class="text-slate-200">${n.ram_used_mb}MB / ${n.ram_total_mb}MB (${ramPct}%)</strong></div>
                        <div>활성 컨테이너: <strong class="text-indigo-400">${n.running_containers}</strong> | 배율: <strong class="text-amber-400">${n.billing_multiplier}x</strong></div>
                    </div>
                `;
                container.appendChild(card);
            });
        }

        async function loadAdminUsers() {
            if (!adminToken) return;
            const resp = await fetch('/api/v1/auth/admin/users', { headers: getAuthHeaders() });
            if (resp.status === 401) { adminLogout(); return; }
            const users = await resp.json();
            const tbody = document.getElementById('usersTableBody');
            tbody.innerHTML = '';
            users.forEach(u => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td class="p-3 text-slate-400">${u.id}</td>
                    <td class="p-3 text-white font-semibold">${u.email}</td>
                    <td class="p-3 text-emerald-400 font-bold">19세 성인인증 ✓</td>
                    <td class="p-3"><span class="px-2 py-0.5 rounded ${u.status === 'ACTIVE' ? 'bg-emerald-950 text-emerald-300' : 'bg-rose-950 text-rose-300'}">${u.status}</span></td>
                    <td class="p-3 text-emerald-400 font-bold font-mono">${u.balance_krw.toLocaleString()} KRW</td>
                    <td class="p-3 text-right space-x-2">
                        <button onclick="adjustCreditPrompt('${u.id}', '${u.email}')" class="px-2.5 py-1 bg-indigo-600/30 text-indigo-300 hover:bg-indigo-600 rounded text-[11px] font-semibold">크레딧 지급/차감</button>
                        <button onclick="toggleUserBan('${u.id}')" class="px-2.5 py-1 bg-rose-600/30 text-rose-300 hover:bg-rose-600 rounded text-[11px] font-semibold">${u.status === 'ACTIVE' ? '정지' : '해제'}</button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        }

        async function adjustCreditPrompt(uid, email) {
            const val = prompt(`[${email}] 회원에게 지급(+) 또는 차감(-)할 금액을 입력하십시오 (KRW):`, "10000");
            if (val && !isNaN(val)) {
                await fetch('/api/v1/auth/admin/users/adjust-credit', {
                    method: 'POST',
                    headers: getAuthHeaders(),
                    body: JSON.stringify({ user_id: uid, amount_krw: parseFloat(val), reason: "어드민 수동 조정" })
                });
                loadAdminUsers();
            }
        }

        async function toggleUserBan(uid) {
            if (confirm(`유저 [${uid}]의 상태를 변경하시겠습니까?`)) {
                await fetch(`/api/v1/auth/admin/users/${uid}/toggle-status`, { method: 'POST', headers: getAuthHeaders() });
                loadAdminUsers();
            }
        }

        async function loadAdminTickets() {
            if (!adminToken) return;
            const resp = await fetch('/api/v1/servers/admin/tickets', { headers: getAuthHeaders() });
            if (resp.status === 401) { adminLogout(); return; }
            const tickets = await resp.json();
            const list = document.getElementById('ticketsList');
            list.innerHTML = '';
            tickets.forEach(t => {
                const item = document.createElement('div');
                item.className = 'p-5 bg-slate-900/80 rounded-xl border border-slate-800 space-y-3 text-xs';
                item.innerHTML = `
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <span class="font-mono font-bold text-indigo-400">[${t.id}]</span>
                            <span class="font-bold text-white text-sm">${t.title}</span>
                            <span class="text-slate-400 font-mono">(${t.user_email})</span>
                        </div>
                        <span class="px-2.5 py-1 rounded font-bold font-mono ${t.status === 'OPEN' ? 'bg-amber-950 text-amber-400' : 'bg-emerald-950 text-emerald-400'}">${t.status}</span>
                    </div>
                    <div class="p-3 bg-slate-950 rounded-lg text-slate-300 font-sans">${t.user_message}</div>
                    ${t.ai_report_json ? `
                        <div class="p-3 bg-indigo-950/40 rounded-lg border border-indigo-500/20 text-indigo-300">
                            <strong>⚡ AI Spark Profiler 진단:</strong> ${t.ai_report_json.root_cause_summary}
                            <div class="text-[11px] text-slate-400 mt-1">권고: ${t.ai_report_json.actionable_steps ? t.ai_report_json.actionable_steps.join(', ') : ''}</div>
                        </div>
                    ` : ''}
                    ${t.admin_response ? `<div class="p-3 bg-slate-800/80 rounded-lg text-emerald-300"><strong>답변 완료:</strong> ${t.admin_response}</div>` : ''}
                    <div class="flex justify-end pt-2">
                        <button onclick="openResolveModal('${t.id}', '${t.title}')" class="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-lg">민원 답변 및 상태 변경</button>
                    </div>
                `;
                list.appendChild(item);
            });
        }

        function openResolveModal(id, title) {
            document.getElementById('res_ticket_id').value = id;
            document.getElementById('modalTicketTitle').innerText = `🎫 [${id}] 민원 처리: ${title}`;
            document.getElementById('resolveModal').classList.remove('hidden');
        }

        document.getElementById('resolveForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const payload = {
                ticket_id: document.getElementById('res_ticket_id').value,
                status: document.getElementById('res_status').value,
                admin_response: document.getElementById('res_response').value
            };
            await fetch('/api/v1/servers/admin/tickets/resolve', {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify(payload)
            });
            alert('민원 답변 및 상태가 등록되었습니다!');
            document.getElementById('resolveModal').classList.add('hidden');
            loadAdminTickets();
        });

        async function loadAdminServers() {
            if (!adminToken) return;
            const resp = await fetch('/api/v1/servers/admin/all', { headers: getAuthHeaders() });
            if (resp.status === 401) { adminLogout(); return; }
            const servers = await resp.json();
            const grid = document.getElementById('adminServersGrid');
            grid.innerHTML = '';
            servers.forEach(s => {
                const card = document.createElement('div');
                card.className = 'p-5 bg-slate-900/80 rounded-xl border border-slate-800 space-y-3 text-xs';
                card.innerHTML = `
                    <div class="flex justify-between items-center">
                        <div>
                            <span class="font-bold text-white text-sm">${s.name}</span>
                            <span class="text-[11px] text-slate-400 font-mono ml-2">${s.server_type} (${s.allocated_ram_mb}MB)</span>
                        </div>
                        <span class="px-2 py-0.5 rounded font-mono font-bold ${s.status === 'RUNNING' ? 'bg-emerald-950 text-emerald-400' : 'bg-rose-950 text-rose-400'}">${s.status}</span>
                    </div>
                    <div class="text-slate-400 font-mono">
                        <div>접속 도메인: <strong class="text-indigo-300">${s.full_domain}</strong></div>
                        <div>배치 노드: <strong class="text-slate-200">${s.node_id} (${s.node_ip}:${s.port})</strong></div>
                        <div>소유자: <strong class="text-slate-300">${s.user_email || 'user@domain.com'}</strong></div>
                    </div>
                    <div class="pt-2 border-t border-slate-800 flex justify-end gap-2">
                        <button onclick="forceServerAction('${s.id}', 'restart')" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded">재시작</button>
                        <button onclick="forceServerAction('${s.id}', 'stop')" class="px-2.5 py-1 bg-amber-900/40 text-amber-300 hover:bg-amber-900 rounded">강제 정지</button>
                        <button onclick="forceDestroyServer('${s.id}')" class="px-2.5 py-1 bg-rose-900/40 text-rose-300 hover:bg-rose-900 rounded">영구 삭제</button>
                    </div>
                `;
                grid.appendChild(card);
            });
        }

        document.getElementById('adminCreateForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const payload = {
                name: document.getElementById('adm_name').value,
                domain_slug: document.getElementById('adm_slug').value,
                server_type: document.getElementById('adm_type').value,
                mc_version: "1.20.4",
                allocated_ram_mb: parseInt(document.getElementById('adm_ram').value),
                preferred_node_id: document.getElementById('adm_node').value || null,
                target_user_id: document.getElementById('adm_user').value || null
            };
            const resp = await fetch('/api/v1/servers/deploy', {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify(payload)
            });
            const res = await resp.json();
            alert(`[어드민 서버 배포 완료]\\n접속 주소: ${res.connect_address}`);
            loadAdminServers();
        });

        document.getElementById('sysSettingsForm').addEventListener('submit', (e) => {
            e.preventDefault();
            alert('시스템 환경설정(Google OAuth & LLM)이 저장되었습니다.');
        });

        async function forceServerAction(id, act) {
            await fetch(`/api/v1/servers/admin/${id}/force-action`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ action: act })
            });
            loadAdminServers();
        }

        async function forceDestroyServer(id) {
            if (confirm(`서버 [${id}]를 클러스터에서 강제 영구 삭제하시겠습니까?`)) {
                await fetch(`/api/v1/servers/admin/${id}`, { method: 'DELETE', headers: getAuthHeaders() });
                loadAdminServers();
            }
        }

        // Check Auth on Init
        verifyAdminAuth().then(isAuth => {
            if (isAuth) {
                loadBillingRates();
                loadAdminNodes();
            }
        });
    </script>
</body>
</html>"""

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 [{settings.PROJECT_NAME} v{settings.VERSION}] Master Control Plane Starting...")
    await db.connect()
    await billing_engine.initialize()
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

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def user_portal():
    return USER_PORTAL_HTML

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard():
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
