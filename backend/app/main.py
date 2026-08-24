"""
main.py - Master Node FastAPI Application Entrypoint
Features:
1. SaaS Landing Page (/) - High-converting marketing portal, Modpacks showcase & ZIP/.mrpack Importer
2. User Console Dashboard (/dashboard, /console) - Sidebar layout, Overview, Server Workspace:
   * Real-Time Minecraft Console Logs (Done! boot message, streaming output & auto-scroll)
   * Non-reloading RCON Form Execution with live interactive terminal
   * Integer vCPU Core direct input & slider (1~32 Cores) synchronized with RAM & dynamic pricing
   * Multi-Worker Safe Persistent Server List (GET /api/v1/servers/my - 100% Reliable across refreshes!)
   * Direct Server Start/Stop/Restart/Delete actions
   * Core/Version Switcher with Mod Loader Dependency Warning
   * server.properties Full GUI Config Editor
   * Web File Explorer & 1-Click World ZIP Backup
   * Installed Mods Manager with 1-Click Auto-Updater
   * Modrinth & CurseForge Split Tabs with Tag Chips, Infinite Scroll & Version Filters
   * Helpdesk & AI Diagnostics
3. Master Admin Center (/admin) - Protected Master Secret Gateway
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
from app.services.server_store import server_store

# ==============================================================================
# 1. SaaS Landing Page HTML (/)
# ==============================================================================
LANDING_PAGE_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NextGen MC - 차세대 클라우드 마인크래프트 호스팅</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@300;400;600;700;800;900&display=swap');
        body { font-family: 'Pretendard', sans-serif; background: #050811; color: #f1f5f9; }
        .glass-card { background: rgba(15, 23, 42, 0.85); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.08); }
        .gradient-btn { background: linear-gradient(135deg, #4f46e5, #6366f1); }
        .gradient-text { background: linear-gradient(135deg, #818cf8, #c084fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .modpack-card:hover { transform: translateY(-3px); border-color: rgba(99, 102, 241, 0.6); }
    </style>
</head>
<body class="min-h-screen flex flex-col justify-between">
    <header class="border-b border-slate-800/80 bg-slate-950/70 backdrop-blur-md sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 md:px-8 py-4 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center font-black text-xl text-white shadow-lg shadow-indigo-500/30">⛏️</div>
                <div>
                    <h1 class="text-xl font-black text-white tracking-tight flex items-center gap-2">
                        NextGen MC <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-900/60 text-indigo-300 border border-indigo-500/30 uppercase">Cloud</span>
                    </h1>
                </div>
            </div>

            <nav class="hidden md:flex items-center gap-6 text-xs font-semibold text-slate-300">
                <a href="#features" class="hover:text-indigo-400 transition">특장점</a>
                <a href="#modpacks" class="hover:text-indigo-400 transition">인기 모드팩</a>
                <a href="#importer" class="hover:text-indigo-400 transition">모드팩 아카이브 임포트</a>
            </nav>

            <div class="flex items-center gap-3">
                <a href="/dashboard" class="px-5 py-2.5 rounded-xl gradient-btn text-white font-bold text-xs shadow-lg shadow-indigo-600/30 hover:scale-105 transition flex items-center gap-1.5">
                    🚀 유저 콘솔 대시보드로 이동
                </a>
            </div>
        </div>
    </header>

    <section class="max-w-7xl mx-auto px-4 md:px-8 pt-16 pb-20 text-center space-y-6">
        <div class="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-indigo-950/80 text-indigo-300 border border-indigo-500/30 text-xs font-bold shadow-lg">
            <span>✨ 2026 차세대 마인크래프트 호스팅</span>
            <span class="w-1 h-1 rounded-full bg-indigo-400"></span>
            <span>초저지연 NVMe & 점유 RAM/vCPU 실시간 종량제</span>
        </div>

        <h2 class="text-4xl md:text-6xl font-black text-white leading-tight tracking-tight max-w-4xl mx-auto">
            원하는 모드팩과 서버를<br><span class="gradient-text">1초 만에 배포하고 자유롭게 관리하세요</span>
        </h2>

        <p class="text-slate-400 text-sm md:text-base max-w-2xl mx-auto leading-relaxed">
            월 고정 요금의 낭비 없이, 서버가 활성화되어 점유된 램(RAM)과 vCPU, 플레이어 수에 따라 초 단위로 공정하게 차감됩니다.
            CurseForge & Modrinth 모드팩 원클릭 설치 및 ZIP 아카이브 드래그 임포트를 지원합니다.
        </p>

        <div class="flex flex-wrap justify-center gap-4 pt-4">
            <a href="/dashboard" class="px-8 py-4 rounded-2xl gradient-btn text-white font-extrabold text-sm shadow-xl shadow-indigo-600/40 hover:scale-105 transition">
                ⚡ 무료 체험 크레딧(3,000원)으로 시작하기
            </a>
            <a href="#modpacks" class="px-6 py-4 rounded-2xl glass-card text-slate-200 font-bold text-sm hover:bg-slate-800 transition">
                📦 인기 모드팩 둘러보기
            </a>
        </div>
    </section>

    <!-- Modpacks Showcase -->
    <section id="modpacks" class="max-w-7xl mx-auto px-4 md:px-8 py-16 space-y-8">
        <div class="flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div>
                <span class="text-xs font-bold text-indigo-400 uppercase">Featured Modpacks</span>
                <h3 class="text-2xl md:text-3xl font-black text-white mt-1">인기 대형 모드팩 카탈로그</h3>
                <p class="text-xs text-slate-400 mt-1">클릭 한 번으로 해당 모드팩이 사전 탑재된 최적화 서버를 즉시 시작할 수 있습니다.</p>
            </div>
            <a href="/dashboard" class="text-xs font-bold text-indigo-400 hover:underline">대시보드에서 전체 모드팩 검색하기 &rarr;</a>
        </div>

        <div id="featuredModpacksGrid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
            <div class="modpack-card glass-card rounded-2xl p-5 space-y-4 flex flex-col justify-between border border-slate-800 transition shadow-xl">
                <div class="space-y-3">
                    <img src="https://cdn.modrinth.com/data/Z19nggA0/icon.png" class="w-14 h-14 rounded-2xl bg-slate-900 object-cover shadow-md">
                    <div>
                        <h4 class="font-extrabold text-base text-white">All the Mods 9 (ATM9)</h4>
                        <span class="text-[11px] text-amber-400 font-mono">CurseForge / Forge</span>
                    </div>
                    <p class="text-xs text-slate-400 line-clamp-3 leading-relaxed">
                        세계 최대 규모의 올인원 종합 모드팩
                    </p>
                </div>
                <div class="space-y-2 pt-3 border-t border-slate-800">
                    <a href="/dashboard?modpack=all-the-mods-9" class="w-full block text-center py-2.5 rounded-xl bg-indigo-600/30 text-indigo-300 hover:bg-indigo-600 hover:text-white font-bold text-xs transition">
                        🚀 이 모드팩으로 시작하기
                    </a>
                </div>
            </div>

            <div class="modpack-card glass-card rounded-2xl p-5 space-y-4 flex flex-col justify-between border border-slate-800 transition shadow-xl">
                <div class="space-y-3">
                    <img src="https://cdn.modrinth.com/data/yMCEFikR/icon.png" class="w-14 h-14 rounded-2xl bg-slate-900 object-cover shadow-md">
                    <div>
                        <h4 class="font-extrabold text-base text-white">Better MC [FABRIC]</h4>
                        <span class="text-[11px] text-emerald-400 font-mono">CurseForge / Fabric</span>
                    </div>
                    <p class="text-xs text-slate-400 line-clamp-3 leading-relaxed">
                        새로운 보스, 차원, 그래픽 셰이더와 커스텀 UI
                    </p>
                </div>
                <div class="space-y-2 pt-3 border-t border-slate-800">
                    <a href="/dashboard?modpack=better-mc" class="w-full block text-center py-2.5 rounded-xl bg-indigo-600/30 text-indigo-300 hover:bg-indigo-600 hover:text-white font-bold text-xs transition">
                        🚀 이 모드팩으로 시작하기
                    </a>
                </div>
            </div>

            <div class="modpack-card glass-card rounded-2xl p-5 space-y-4 flex flex-col justify-between border border-slate-800 transition shadow-xl">
                <div class="space-y-3">
                    <img src="https://cdn.modrinth.com/data/M0uO8vpq/icon.png" class="w-14 h-14 rounded-2xl bg-slate-900 object-cover shadow-md">
                    <div>
                        <h4 class="font-extrabold text-base text-white">Cobblemon Official Pack</h4>
                        <span class="text-[11px] text-indigo-400 font-mono">Modrinth / Fabric</span>
                    </div>
                    <p class="text-xs text-slate-400 line-clamp-3 leading-relaxed">
                        포켓몬 테이밍, 배틀, 미니맵 올인원 공식 팩
                    </p>
                </div>
                <div class="space-y-2 pt-3 border-t border-slate-800">
                    <a href="/dashboard?modpack=cobblemon-modpack" class="w-full block text-center py-2.5 rounded-xl bg-indigo-600/30 text-indigo-300 hover:bg-indigo-600 hover:text-white font-bold text-xs transition">
                        🚀 이 모드팩으로 시작하기
                    </a>
                </div>
            </div>

            <div class="modpack-card glass-card rounded-2xl p-5 space-y-4 flex flex-col justify-between border border-slate-800 transition shadow-xl">
                <div class="space-y-3">
                    <img src="https://cdn.modrinth.com/data/1KVo5zza/icon.png" class="w-14 h-14 rounded-2xl bg-slate-900 object-cover shadow-md">
                    <div>
                        <h4 class="font-extrabold text-base text-white">Fabulously Optimized</h4>
                        <span class="text-[11px] text-cyan-400 font-mono">Modrinth / Fabric</span>
                    </div>
                    <p class="text-xs text-slate-400 line-clamp-3 leading-relaxed">
                        소듐, 리튬, 인듐 결합 초경량 고FPS 최적화
                    </p>
                </div>
                <div class="space-y-2 pt-3 border-t border-slate-800">
                    <a href="/dashboard?modpack=fabulously-optimized" class="w-full block text-center py-2.5 rounded-xl bg-indigo-600/30 text-indigo-300 hover:bg-indigo-600 hover:text-white font-bold text-xs transition">
                        🚀 이 모드팩으로 시작하기
                    </a>
                </div>
            </div>
        </div>
    </section>

    <!-- Modpack Importer -->
    <section id="importer" class="max-w-7xl mx-auto px-4 md:px-8 py-16">
        <div class="glass-card rounded-3xl p-8 md:p-12 border border-indigo-500/30 bg-gradient-to-br from-indigo-950/40 via-slate-900 to-slate-950 space-y-6 text-center">
            <div class="w-16 h-16 rounded-2xl bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center text-3xl mx-auto">📁</div>
            <div class="space-y-2 max-w-2xl mx-auto">
                <h3 class="text-2xl md:text-3xl font-black text-white">내 모드팩 파일 직접 임포트 (.zip, .mrpack)</h3>
                <p class="text-xs md:text-sm text-slate-400 leading-relaxed">
                    CurseForge ZIP 또는 Modrinth .mrpack 파일을 업로드하면 즉시 전용 서버를 생성합니다.
                </p>
            </div>
            
            <div class="p-8 border-2 border-dashed border-indigo-500/40 rounded-2xl bg-slate-950/60 max-w-xl mx-auto space-y-3">
                <span class="text-3xl block">📥</span>
                <p class="text-xs font-semibold text-slate-300">여기에 모드팩 ZIP 또는 .mrpack 파일을 드래그하여 놓으세요</p>
                <label class="inline-block px-5 py-2.5 rounded-xl gradient-btn text-white font-bold text-xs cursor-pointer shadow-lg">
                    내 PC에서 파일 선택하기
                    <input type="file" accept=".zip,.mrpack" onchange="handleModpackUpload(this)" class="hidden">
                </label>
            </div>
        </div>
    </section>

    <footer class="border-t border-slate-800/80 bg-slate-950 py-8 text-center text-xs text-slate-500">
        <div class="max-w-7xl mx-auto px-4 space-y-2">
            <p>© 2026 NextGen MC Platform. All rights reserved. (청소년 보호법에 따른 19세 성인인증 필수)</p>
        </div>
    </footer>

    <script>
        function handleModpackUpload(input) {
            if (input.files && input.files[0]) {
                const file = input.files[0];
                alert(`📦 모드팩 [${file.name}] 감지 완료! 대시보드로 이동하여 서버 생성을 진행합니다.`);
                window.location.href = `/dashboard?import_filename=${encodeURIComponent(file.name)}`;
            }
        }
    </script>
</body>
</html>"""

# ==============================================================================
# 2. User Console Dashboard HTML (/dashboard, /console)
# ==============================================================================
USER_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NextGen MC - 유저 콘솔 대시보드</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@300;400;600;700;800;900&display=swap');
        body { font-family: 'Pretendard', sans-serif; background: #050811; color: #f1f5f9; min-height: 100vh; }
        .glass-card { background: rgba(15, 23, 42, 0.85); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.08); }
        .gradient-btn { background: linear-gradient(135deg, #4f46e5, #6366f1); }
        .gradient-text { background: linear-gradient(135deg, #818cf8, #c084fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .nav-link.active { background: rgba(99, 102, 241, 0.15); color: #818cf8; border-left: 3px solid #6366f1; }
        .tab-btn.active { background: #4f46e5; color: white; }
        .chip.active { background: #4f46e5; color: white; border-color: #6366f1; }
    </style>
</head>
<body class="flex h-screen overflow-hidden text-xs">

    <!-- Left Sidebar -->
    <aside class="w-64 bg-slate-950 border-r border-slate-800/80 flex flex-col justify-between p-4 flex-shrink-0">
        <div class="space-y-6">
            <a href="/" class="flex items-center gap-3 px-2">
                <div class="w-8 h-8 rounded-xl bg-indigo-600 flex items-center justify-center font-black text-sm text-white shadow-lg shadow-indigo-500/30">⛏️</div>
                <div>
                    <h1 class="text-sm font-extrabold text-white tracking-tight">NextGen MC</h1>
                    <span class="text-[9px] text-slate-400 font-mono">User Console</span>
                </div>
            </a>

            <nav class="space-y-1">
                <button onclick="switchView('overview')" id="nav_overview" class="nav-link active w-full flex items-center gap-3 px-3 py-2.5 rounded-xl font-bold text-slate-300 hover:bg-slate-900 transition">
                    <span>📊</span> 대시보드 개요
                </button>
                <button onclick="switchView('servers')" id="nav_servers" class="nav-link w-full flex items-center gap-3 px-3 py-2.5 rounded-xl font-bold text-slate-300 hover:bg-slate-900 transition">
                    <span>🎮</span> 내 마인크래프트 서버
                </button>
                <button onclick="switchView('helpdesk')" id="nav_helpdesk" class="nav-link w-full flex items-center gap-3 px-3 py-2.5 rounded-xl font-bold text-slate-300 hover:bg-slate-900 transition">
                    <span>🎫</span> 고객센터 & AI 렉 진단
                </button>
            </nav>
        </div>

        <div class="space-y-3 border-t border-slate-800/80 pt-4">
            <div class="p-3 bg-slate-900/90 rounded-xl border border-slate-800 space-y-1.5">
                <div class="flex items-center justify-between">
                    <span class="text-slate-400 text-[10px] font-bold uppercase">보유 크레딧</span>
                    <button onclick="topupCredit()" class="text-[10px] text-emerald-400 hover:underline font-bold">+ 충전</button>
                </div>
                <div id="sidebarBalance" class="text-sm font-mono font-extrabold text-emerald-400">3,000 KRW</div>
            </div>

            <div class="flex items-center justify-between px-2">
                <div class="overflow-hidden">
                    <span id="sidebarEmail" class="font-bold text-slate-200 block truncate cursor-pointer hover:underline" onclick="editAccountEmail()" title="클릭하여 계정 이메일 변경">player_steve@gmail.com</span>
                    <span class="text-[10px] text-indigo-400">19세 인증 계정 ✓</span>
                </div>
                <button onclick="editAccountEmail()" class="text-slate-500 hover:text-indigo-400 text-xs">변경</button>
            </div>
        </div>
    </aside>

    <!-- Main Workspace Area -->
    <main class="flex-1 flex flex-col overflow-hidden bg-[#050811]">
        <header class="h-14 border-b border-slate-800/80 px-6 flex items-center justify-between bg-slate-950/40">
            <div class="flex items-center gap-2 text-slate-400">
                <span id="pageBreadcrumb" class="font-semibold text-white">대시보드 개요</span>
            </div>
            <div class="flex items-center gap-3">
                <button onclick="openCreateModal()" class="gradient-btn px-4 py-2 rounded-xl text-white font-extrabold shadow-lg shadow-indigo-600/30 hover:scale-105 transition flex items-center gap-1.5">
                    🚀 새 서버 개설
                </button>
            </div>
        </header>

        <!-- View 1: Overview -->
        <div id="view_overview" class="flex-1 overflow-y-auto p-6 space-y-6">
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div class="glass-card p-5 rounded-2xl space-y-1">
                    <span class="text-slate-400 text-[10px] font-bold uppercase">가동 중인 서버</span>
                    <div class="text-2xl font-black text-white" id="statServerCount">0개</div>
                </div>
                <div class="glass-card p-5 rounded-2xl space-y-1">
                    <span class="text-slate-400 text-[10px] font-bold uppercase">총 할당 자원</span>
                    <div class="text-2xl font-black text-indigo-400" id="statTotalRam">0 GB / 0 Cores</div>
                </div>
                <div class="glass-card p-5 rounded-2xl space-y-1">
                    <span class="text-slate-400 text-[10px] font-bold uppercase">예상 1시간 과금액</span>
                    <div class="text-2xl font-black text-emerald-400" id="statCostPerHour">0 KRW</div>
                </div>
                <div class="glass-card p-5 rounded-2xl space-y-1">
                    <span class="text-slate-400 text-[10px] font-bold uppercase">남은 잔액</span>
                    <div class="text-2xl font-black text-amber-400 font-mono" id="statBalance">3,000 KRW</div>
                </div>
            </div>

            <div class="glass-card rounded-2xl p-6 bg-gradient-to-r from-indigo-950/40 via-slate-900 to-slate-900 flex items-center justify-between gap-4">
                <div class="space-y-1">
                    <h3 class="font-extrabold text-base text-white">클라우드 마인크래프트 서버를 즉시 시작하세요</h3>
                    <p class="text-slate-400 text-xs">건축, 야생, Modrinth/CurseForge 모드팩까지 1초 만에 배포할 수 있습니다.</p>
                </div>
                <button onclick="openCreateModal()" class="gradient-btn px-5 py-2.5 rounded-xl text-white font-bold whitespace-nowrap shadow-lg">
                    + 서버 만들기
                </button>
            </div>
        </div>

        <!-- View 2: Servers List -->
        <div id="view_servers" class="hidden flex-1 overflow-y-auto p-6 space-y-6">
            <div class="flex items-center justify-between">
                <h3 class="font-bold text-base text-white">🎮 내 마인크래프트 서버 목록</h3>
                <div class="flex items-center gap-2">
                    <button onclick="loadMyServers()" class="text-xs text-indigo-400 hover:underline">새로고침</button>
                    <span class="text-slate-400" id="serverListCount">0개 가동 중</span>
                </div>
            </div>
            <div id="serversGrid" class="grid grid-cols-1 md:grid-cols-2 gap-5">
                <div id="emptyServers" class="col-span-2 glass-card rounded-2xl p-12 text-center space-y-2">
                    <div class="text-3xl">🕹️</div>
                    <p class="text-slate-300 font-semibold">아직 생성된 마인크래프트 서버가 없습니다.</p>
                    <p class="text-slate-500">상단의 [새 서버 개설] 버튼을 눌러 첫 서버를 만들어보세요.</p>
                </div>
            </div>
        </div>

        <!-- View 3: Helpdesk -->
        <div id="view_helpdesk" class="hidden flex-1 overflow-y-auto p-6 space-y-6">
            <div class="flex items-center justify-between">
                <h3 class="font-bold text-base text-white">🎫 기술 지원 헬프데스크</h3>
                <button onclick="alert('문의가 접수되었습니다.')" class="px-4 py-2 bg-indigo-600 text-white rounded-xl font-bold shadow">
                    + 새 문의 접수
                </button>
            </div>
            <div id="userTicketsList" class="space-y-4"></div>
        </div>
    </main>

    <!-- Create Server Modal (vCPU & RAM Direct Integer Setting) -->
    <div id="createModal" class="hidden fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center p-4 z-50">
        <div class="glass-card max-w-2xl w-full rounded-2xl p-6 md:p-8 space-y-5 shadow-2xl max-h-[90vh] overflow-y-auto">
            <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                <div>
                    <h4 class="font-bold text-base text-white">✨ 새 마인크래프트 서버 개설</h4>
                    <p class="text-[11px] text-slate-400">RAM 용량과 vCPU 코어 개수를 자유롭게 정수로 직접 조정하세요.</p>
                </div>
                <button onclick="closeCreateModal()" class="text-slate-400 hover:text-white text-xl font-bold">&times;</button>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div onclick="selectPreset('BUILDER_FLAT')" id="preset_BUILDER_FLAT" class="preset-card glass-card p-3.5 rounded-xl space-y-1.5 cursor-pointer border border-transparent">
                    <div class="text-xl">🏰</div>
                    <div class="font-bold text-white">심플 건축 서버</div>
                    <p class="text-[10px] text-slate-400">평지 맵 + WorldEdit (2 vCPU / 4GB RAM)</p>
                </div>
                <div onclick="selectPreset('SURVIVAL_SMP')" id="preset_SURVIVAL_SMP" class="preset-card active glass-card p-3.5 rounded-xl space-y-1.5 cursor-pointer border border-indigo-500 bg-indigo-950/20">
                    <div class="text-xl">🌲</div>
                    <div class="font-bold text-white">심플 야생 서버</div>
                    <p class="text-[10px] text-slate-400">야생 맵 + EssentialsX (2 vCPU / 4GB RAM)</p>
                </div>
                <div onclick="selectPreset('ADVANCED_CUSTOM')" id="preset_ADVANCED_CUSTOM" class="preset-card glass-card p-3.5 rounded-xl space-y-1.5 cursor-pointer border border-transparent">
                    <div class="text-xl">⚙️</div>
                    <div class="font-bold text-white">고급 서버 개설</div>
                    <p class="text-[10px] text-slate-400">26.2, 스냅샷, vCPU / RAM 정수 직접 지정</p>
                </div>
            </div>

            <form id="createForm" class="space-y-4 text-xs">
                <input type="hidden" id="selected_preset" value="SURVIVAL_SMP">
                <input type="hidden" id="selected_modpack_id" value="">

                <div>
                    <label class="block font-semibold text-slate-300 mb-1">서버 명칭</label>
                    <input type="text" id="srv_name" required placeholder="예: 우리들의 마인크래프트 서버" class="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-slate-100 outline-none focus:border-indigo-500">
                </div>

                <div class="p-3.5 bg-slate-950/80 rounded-xl border border-slate-800 space-y-2.5">
                    <div class="flex items-center justify-between">
                        <label class="font-bold text-slate-200">접속 도메인 설정</label>
                        <label class="flex items-center gap-1.5 cursor-pointer text-[11px] text-indigo-300 font-semibold">
                            <input type="checkbox" id="enableCustomDomain" onchange="toggleCustomDomainInput()" class="rounded bg-slate-900 text-indigo-600 focus:ring-0">
                            나만의 프리미엄 도메인 지정 (1,000 KRW)
                        </label>
                    </div>

                    <div id="freeDomainNotice" class="text-[11px] text-slate-400">
                        ✓ <strong>무료 자동 발급 도메인</strong> (<span class="font-mono text-indigo-300">mc-xxxxxx.domain.com</span>)이 적용됩니다. (추가 비용 0원)
                    </div>

                    <div id="customDomainBox" class="hidden space-y-1.5 pt-1 border-t border-slate-800">
                        <div class="flex items-center gap-1.5">
                            <input type="text" id="srv_slug" pattern="^[a-z0-9-]{3,32}$" placeholder="예: myworld" oninput="handleDomainInput()" class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-100 font-mono outline-none">
                            <span class="text-slate-400 font-mono text-[11px]">.domain.com</span>
                        </div>
                        <div class="flex items-center justify-between text-[11px]">
                            <span id="domainStatusTag" class="text-slate-400">3자 이상의 영문/숫자 입력</span>
                            <span id="domainSuggestions" class="text-indigo-400"></span>
                        </div>
                    </div>
                </div>

                <div id="advancedOptions" class="hidden p-4 bg-slate-900/90 rounded-xl border border-indigo-500/30 space-y-4">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                            <label class="block font-semibold text-slate-300 mb-1">서버 구동기 (코어)</label>
                            <select id="srv_type" class="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-slate-100 outline-none">
                                <option value="PAPER">Paper (플러그인 최적화)</option>
                                <option value="PURPUR">Purpur</option>
                                <option value="FOLIA">Folia (멀티스레드)</option>
                                <option value="FABRIC">Fabric (경량 모드)</option>
                                <option value="FORGE">Forge (일반 모드팩)</option>
                                <option value="NEOFORGE">NeoForge (최신 대형)</option>
                                <option value="SPONGE">Sponge</option>
                                <option value="VANILLA">마인크래프트 공식 바닐라</option>
                                <option value="SPIGOT">Spigot</option>
                                <option value="VELOCITY">Velocity (프록시)</option>
                            </select>
                        </div>
                        <div>
                            <label class="block font-semibold text-slate-300 mb-1">마인크래프트 버전</label>
                            <select id="srv_version" class="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-slate-100 font-mono outline-none">
                                <option value="26.2">26.2 (최신 릴리즈)</option>
                                <option value="26.1.2">26.1.2</option>
                                <option value="1.20.4">1.20.4</option>
                                <option value="1.20.1">1.20.1</option>
                            </select>
                        </div>
                    </div>

                    <!-- vCPU Allocation with Number Input & Range -->
                    <div class="p-3.5 bg-slate-950/80 rounded-xl border border-slate-800 space-y-2.5">
                        <div class="flex items-center justify-between">
                            <label class="font-bold text-slate-200 flex items-center gap-1.5">
                                <span>⚡</span> vCPU 코어 개수 (정수로 직접 지정)
                            </label>
                            <div class="flex items-center gap-1.5">
                                <input type="number" id="srv_cpu_cores" min="1" max="32" step="1" value="2" oninput="syncCpuInput('number')" class="w-16 px-2 py-1 bg-slate-900 border border-indigo-500/50 rounded-lg text-white font-mono font-bold text-center outline-none">
                                <span class="font-bold text-indigo-300">Cores</span>
                            </div>
                        </div>
                        <input type="range" id="srv_cpu_range" min="1" max="16" step="1" value="2" oninput="syncCpuInput('range')" class="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500">
                    </div>

                    <!-- RAM Allocation with Number Input & Range -->
                    <div class="p-3.5 bg-slate-950/80 rounded-xl border border-slate-800 space-y-2.5">
                        <div class="flex items-center justify-between">
                            <label class="font-bold text-slate-200 flex items-center gap-1.5">
                                <span>🧠</span> 최대 RAM 할당 용량 (정수로 직접 지정)
                            </label>
                            <div class="flex items-center gap-1.5">
                                <input type="number" id="srv_ram_gb" min="1" max="128" step="1" value="4" oninput="syncRamInput('number')" class="w-16 px-2 py-1 bg-slate-900 border border-indigo-500/50 rounded-lg text-white font-mono font-bold text-center outline-none">
                                <span class="font-bold text-indigo-300">GB</span>
                                <span class="text-slate-500 font-mono text-[10px]" id="ramMbTag">(4,096 MB)</span>
                            </div>
                        </div>
                        <input type="range" id="srv_ram_range" min="1" max="64" step="1" value="4" oninput="syncRamInput('range')" class="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500">
                    </div>

                    <div>
                        <label class="block font-semibold text-slate-300 mb-1">하드웨어 과금 티어</label>
                        <select id="srv_tier" onchange="updateEstimatedCost()" class="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-slate-100 outline-none">
                            <option value="high_nvme" data-multiplier="1.3">초고속 NVMe (1.3x)</option>
                            <option value="standard_ssd" data-multiplier="1.0">표준 SSD (1.0x)</option>
                            <option value="extreme_dedicated" data-multiplier="1.8">단독 전용 Extreme (1.8x)</option>
                        </select>
                    </div>
                </div>

                <!-- Real-time Cost Estimation Box -->
                <div class="p-4 bg-gradient-to-r from-indigo-950/50 via-slate-900 to-slate-900 rounded-xl border border-indigo-500/30 space-y-1.5">
                    <div class="flex items-center justify-between">
                        <span class="font-bold text-indigo-300">💰 실시간 예상 과금액 (점유 RAM & vCPU 기준)</span>
                        <span class="text-sm font-extrabold text-emerald-400 font-mono" id="estCostPerMin">약 0.62 KRW / 분</span>
                    </div>
                    <div class="flex items-center justify-between text-[11px] text-slate-400 font-mono pt-1 border-t border-slate-800/80">
                        <span>1시간 예상: <strong class="text-slate-200" id="estCostPerHour">~37.2 KRW</strong></span>
                        <span>24시간 예상: <strong class="text-slate-200" id="estCostPerDay">~892.8 KRW</strong></span>
                    </div>
                </div>

                <div class="pt-2 flex justify-end gap-2 border-t border-slate-800">
                    <button type="button" onclick="closeCreateModal()" class="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl">취소</button>
                    <button type="submit" id="deployBtn" class="gradient-btn px-6 py-2 rounded-xl text-white font-extrabold shadow-lg">
                        🚀 서버 배포
                    </button>
                </div>
            </form>
        </div>
    </div>

    <!-- ======================================================================= -->
    <!-- Server Detailed Workspace Modal (Live Console & Log Streaming)          -->
    <!-- ======================================================================= -->
    <div id="serverWorkspaceModal" class="hidden fixed inset-0 bg-black/85 backdrop-blur-md flex items-center justify-center p-4 z-50">
        <div class="glass-card max-w-5xl w-full rounded-2xl p-6 space-y-4 shadow-2xl max-h-[92vh] flex flex-col">
            <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                <div class="flex items-center gap-3">
                    <span class="text-2xl">🎮</span>
                    <div>
                        <h4 class="font-extrabold text-base text-white" id="wsServerName">서버 관리 워크스페이스</h4>
                        <div class="flex items-center gap-2 text-[11px] text-slate-400 font-mono">
                            <span id="wsServerAddress" class="text-indigo-300 font-bold">alpha.domain.com</span>
                            <span id="wsServerSpecs" class="px-1.5 py-0.5 bg-slate-800 rounded">PAPER 26.2 (2 vCPU / 4GB RAM)</span>
                        </div>
                    </div>
                </div>
                <button onclick="closeServerWorkspace()" class="text-slate-400 hover:text-white font-sans text-xl">&times;</button>
            </div>

            <div class="flex flex-wrap gap-1.5 border-b border-slate-800 pb-2.5 font-semibold">
                <button onclick="switchWsTab('console')" id="wstab_console" class="tab-btn active px-3 py-1.5 rounded-lg">💻 콘솔 & 실시간 로그</button>
                <button onclick="switchWsTab('version')" id="wstab_version" class="tab-btn px-3 py-1.5 rounded-lg">⚙️ 버전 & 구동기 변경</button>
                <button onclick="switchWsTab('properties')" id="wstab_properties" class="tab-btn px-3 py-1.5 rounded-lg">📝 server.properties 설정</button>
                <button onclick="switchWsTab('files')" id="wstab_files" class="tab-btn px-3 py-1.5 rounded-lg">📁 파일 탐색기</button>
                <button onclick="switchWsTab('installed_mods')" id="wstab_installed_mods" class="tab-btn px-3 py-1.5 rounded-lg">🧩 설치된 모드 & 업데이트</button>
                <button onclick="switchWsTab('marketplace')" id="wstab_marketplace" class="tab-btn px-3 py-1.5 rounded-lg">🛒 모드 마켓플레이스</button>
            </div>

            <!-- Tab 1: Live Interactive Console & Streaming Logs -->
            <div id="wspane_console" class="flex-1 overflow-y-auto space-y-3 font-mono flex flex-col justify-between">
                <div class="flex items-center justify-between p-3 bg-slate-900 rounded-xl border border-slate-800 font-sans">
                    <div class="flex items-center gap-2">
                        <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping"></span>
                        <span class="font-bold text-white text-xs">서버 상태: <strong class="text-emerald-400" id="wsServerStatus">RUNNING</strong></span>
                    </div>
                    <div class="flex gap-2">
                        <button onclick="executeServerControlAction('restart')" class="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded">재시작</button>
                        <button onclick="executeServerControlAction('stop')" class="px-3 py-1 bg-amber-900/40 text-amber-300 hover:bg-amber-900 rounded">정지</button>
                        <button onclick="deleteCurrentServer()" class="px-3 py-1 bg-rose-900/40 text-rose-300 hover:bg-rose-900 rounded font-bold">서버 삭제</button>
                    </div>
                </div>

                <!-- Real-time Console Terminal Output Area -->
                <div id="rconBox" class="h-80 p-3.5 bg-black/95 rounded-xl border border-slate-800 text-emerald-400 overflow-y-auto space-y-1 text-[11px] leading-relaxed shadow-inner font-mono select-text">
                    <div class="text-slate-500">[System] 마인크래프트 서버 실시간 터미널 콘솔에 연결 중...</div>
                </div>

                <!-- Non-Reloading Command Input Form -->
                <form id="wsRconForm" onsubmit="handleRconSubmit(event)" class="flex gap-2 font-sans pt-1">
                    <input type="text" id="wsRconInput" required autocomplete="off" placeholder="명령어 입력 (예: op Steve, gamemode creative, list, spark health)" class="flex-1 px-3.5 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-slate-100 font-mono outline-none focus:border-indigo-500">
                    <button type="submit" id="rconSubmitBtn" class="gradient-btn px-5 py-2.5 text-white font-extrabold rounded-xl shadow">
                        전송
                    </button>
                </form>
            </div>

            <!-- Tab 2: Version & Core Switcher -->
            <div id="wspane_version" class="hidden flex-1 overflow-y-auto space-y-4">
                <div class="p-4 bg-slate-900/80 rounded-xl border border-slate-800 space-y-3">
                    <h5 class="font-bold text-white text-sm">🔄 마인크래프트 버전 및 구동기(코어) 변경</h5>
                    <div id="modLoaderWarningBox" class="p-3 bg-amber-950/40 border border-amber-500/30 rounded-xl text-amber-300 space-y-1">
                        <strong class="block">⚠️ 모드로더 의존성 주의 안내</strong>
                        <span>현재 서버에 설치된 모드가 있는 경우, Paper나 Vanilla로 변경 시 모드가 로드되지 않습니다.</span>
                    </div>

                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="block text-slate-300 font-semibold mb-1">변경할 서버 구동기</label>
                            <select id="switch_core" class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-100">
                                <option value="PAPER">Paper (플러그인 최적화)</option>
                                <option value="PURPUR">Purpur</option>
                                <option value="FOLIA">Folia (멀티스레드)</option>
                                <option value="FABRIC">Fabric (경량 모드)</option>
                                <option value="FORGE">Forge (일반 모드팩)</option>
                                <option value="NEOFORGE">NeoForge</option>
                                <option value="VANILLA">마인크래프트 공식 바닐라</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-slate-300 font-semibold mb-1">변경할 버전</label>
                            <input type="text" id="switch_version" value="26.2" class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-100 font-mono">
                        </div>
                    </div>

                    <div class="flex items-center justify-between pt-2">
                        <label class="flex items-center gap-1.5 cursor-pointer text-slate-400">
                            <input type="checkbox" id="switch_force" class="rounded bg-slate-900 text-indigo-600">
                            모드 비호환 경고 무시하고 강제 변경
                        </label>
                        <button onclick="executeVersionSwitch()" class="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 font-bold text-white rounded-lg shadow">
                            구동기 변경 및 서버 재시작
                        </button>
                    </div>
                </div>
            </div>

            <!-- Tab 3: server.properties GUI Editor -->
            <div id="wspane_properties" class="hidden flex-1 overflow-y-auto space-y-4">
                <div class="flex items-center justify-between">
                    <span class="font-bold text-white">📝 server.properties GUI 설정 에디터</span>
                    <button onclick="saveServerPropertiesGui()" class="px-4 py-1.5 bg-emerald-600 text-white font-bold rounded-lg shadow">
                        설정 저장 및 적용
                    </button>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 bg-slate-900/80 rounded-xl border border-slate-800">
                    <div>
                        <label class="block text-slate-400 mb-1">서버 MOTD (설명)</label>
                        <input type="text" id="prop_motd" class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-100">
                    </div>
                    <div>
                        <label class="block text-slate-400 mb-1">게임 모드 (Gamemode)</label>
                        <select id="prop_gamemode" class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-100">
                            <option value="survival">서바이벌 (Survival)</option>
                            <option value="creative">크리에이티브 (Creative)</option>
                            <option value="adventure">어드벤처 (Adventure)</option>
                            <option value="spectator">관전자 (Spectator)</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-slate-400 mb-1">난이도 (Difficulty)</label>
                        <select id="prop_difficulty" class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-100">
                            <option value="peaceful">평화로움 (Peaceful)</option>
                            <option value="easy">쉬움 (Easy)</option>
                            <option value="normal">보통 (Normal)</option>
                            <option value="hard">어려움 (Hard)</option>
                        </select>
                    </div>

                    <div>
                        <label class="block text-slate-400 mb-1">최대 플레이어 수</label>
                        <input type="number" id="prop_max_players" value="20" class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-100">
                    </div>
                    <div>
                        <label class="block text-slate-400 mb-1">시야 거리 (View Distance)</label>
                        <input type="number" id="prop_view_distance" value="10" class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-100">
                    </div>
                    <div>
                        <label class="block text-slate-400 mb-1">시뮬레이션 거리 (Simulation)</label>
                        <input type="number" id="prop_sim_distance" value="8" class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-100">
                    </div>

                    <div class="space-y-2 pt-2">
                        <label class="flex items-center gap-2 text-slate-300">
                            <input type="checkbox" id="prop_pvp" class="rounded bg-slate-950 text-indigo-600"> PVP 허용
                        </label>
                        <label class="flex items-center gap-2 text-slate-300">
                            <input type="checkbox" id="prop_online_mode" class="rounded bg-slate-950 text-indigo-600"> 정품 인증 (Online Mode)
                        </label>
                    </div>
                    <div class="space-y-2 pt-2">
                        <label class="flex items-center gap-2 text-slate-300">
                            <input type="checkbox" id="prop_allow_flight" class="rounded bg-slate-950 text-indigo-600"> 비행 허용 (Allow Flight)
                        </label>
                        <label class="flex items-center gap-2 text-slate-300">
                            <input type="checkbox" id="prop_whitelist" class="rounded bg-slate-950 text-indigo-600"> 화이트리스트 활성화
                        </label>
                    </div>
                    <div class="space-y-2 pt-2">
                        <label class="flex items-center gap-2 text-slate-300">
                            <input type="checkbox" id="prop_hardcore" class="rounded bg-slate-950 text-indigo-600"> 하드코어 모드
                        </label>
                        <label class="flex items-center gap-2 text-slate-300">
                            <input type="checkbox" id="prop_monsters" class="rounded bg-slate-950 text-indigo-600"> 몬스터 스폰
                        </label>
                    </div>
                </div>
            </div>

            <!-- Tab 4: Files -->
            <div id="wspane_files" class="hidden flex-1 overflow-y-auto space-y-3">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-1 text-slate-400 font-mono" id="wsBreadcrumbs"><span>/</span></div>
                    <div class="flex gap-2">
                        <button onclick="downloadWorldBackup()" class="px-3 py-1.5 bg-emerald-950 text-emerald-300 border border-emerald-500/40 rounded-lg font-bold">🌍 월드 ZIP 다운로드</button>
                        <label class="px-3 py-1.5 bg-indigo-950 text-indigo-300 border border-indigo-500/40 rounded-lg font-bold cursor-pointer">
                            📤 파일 업로드
                            <input type="file" onchange="uploadSelectedFile(this)" class="hidden">
                        </label>
                    </div>
                </div>
                <table class="w-full text-left font-mono">
                    <thead class="bg-slate-900/90 text-slate-400 uppercase">
                        <tr><th class="p-2">이름</th><th class="p-2">크기</th><th class="p-2">수정일</th><th class="p-2 text-right">작업</th></tr>
                    </thead>
                    <tbody id="wsFileTableBody" class="divide-y divide-slate-800"></tbody>
                </table>
            </div>

            <!-- Tab 5: Installed Mods -->
            <div id="wspane_installed_mods" class="hidden flex-1 overflow-y-auto space-y-4">
                <div class="flex items-center justify-between">
                    <div>
                        <h5 class="font-bold text-white text-sm">🧩 설치된 모드 & 플러그인 관리</h5>
                        <p class="text-slate-400">서버에 설치된 모드의 최신 빌드를 확인하고 1클릭으로 업데이트합니다.</p>
                    </div>
                    <button onclick="updateAllInstalledMods()" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-xl shadow">
                        🔄 최신 버전으로 일괄 업데이트
                    </button>
                </div>
                <div id="installedModsList" class="space-y-2"></div>
            </div>

            <!-- Tab 6: Marketplace -->
            <div id="wspane_marketplace" class="hidden flex-1 overflow-y-auto space-y-4 flex flex-col">
                <div class="flex items-center justify-between border-b border-slate-800 pb-2">
                    <div class="flex gap-2">
                        <button onclick="selectMarketplaceSource('modrinth')" id="src_modrinth" class="tab-btn active px-4 py-1.5 rounded-lg font-bold">🟢 Modrinth</button>
                        <button onclick="selectMarketplaceSource('curseforge')" id="src_curseforge" class="tab-btn px-4 py-1.5 rounded-lg font-bold">🔥 CurseForge</button>
                    </div>
                    <div class="flex items-center gap-2">
                        <select id="marketTypeFilter" onchange="resetAndSearchMarket()" class="px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-slate-100">
                            <option value="">전체 (모드 + 모드팩)</option>
                            <option value="mod">단일 모드 (Mods)</option>
                            <option value="modpack">종합 모드팩 (Modpacks)</option>
                        </select>
                        <select id="marketVerFilter" onchange="resetAndSearchMarket()" class="px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-slate-100 font-mono">
                            <option value="all">전체 버전</option>
                            <option value="26.2">26.2</option>
                            <option value="1.20.4">1.20.4</option>
                            <option value="1.20.1">1.20.1</option>
                        </select>
                    </div>
                </div>

                <div id="categoryChipsContainer" class="flex flex-wrap gap-1.5 pb-2 border-b border-slate-800/60"></div>

                <div class="flex gap-2">
                    <input type="text" id="marketSearchInput" placeholder="모드 또는 모드팩 검색 (Enter)" onkeydown="if(event.key==='Enter') resetAndSearchMarket()" class="flex-1 px-3.5 py-2 bg-slate-900 border border-slate-700 rounded-xl text-slate-100">
                    <button onclick="resetAndSearchMarket()" class="px-4 py-2 bg-indigo-600 text-white font-bold rounded-xl shadow">검색</button>
                </div>

                <div id="marketGrid" class="grid grid-cols-1 md:grid-cols-2 gap-3 flex-1 overflow-y-auto"></div>

                <div class="text-center pt-2">
                    <button onclick="loadMoreMarketItems()" id="loadMoreBtn" class="px-5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold rounded-xl">
                        ⬇️ 다음 페이지 더 불러오기
                    </button>
                </div>
            </div>
        </div>
    </div>

    <!-- Mod Detail Modal -->
    <div id="modDetailModal" class="hidden fixed inset-0 bg-black/90 backdrop-blur-md flex items-center justify-center p-4 z-50">
        <div class="glass-card max-w-3xl w-full rounded-2xl p-6 space-y-4 shadow-2xl max-h-[88vh] flex flex-col text-xs">
            <div class="flex items-start justify-between border-b border-slate-800 pb-3">
                <div class="flex items-center gap-3">
                    <img id="detailModIcon" src="" class="w-12 h-12 rounded-xl bg-slate-800 object-cover">
                    <div>
                        <h4 class="font-extrabold text-base text-white" id="detailModTitle">모드 제목</h4>
                        <span class="text-slate-400 font-mono" id="detailModAuthor">by Author</span>
                    </div>
                </div>
                <button onclick="document.getElementById('modDetailModal').classList.add('hidden')" class="text-slate-400 hover:text-white font-sans text-xl">&times;</button>
            </div>
            <div id="detailModBody" class="flex-1 overflow-y-auto bg-slate-950/80 p-4 rounded-xl border border-slate-800 text-slate-300 leading-relaxed space-y-2"></div>
            <div class="flex justify-end gap-2 pt-2 border-t border-slate-800">
                <button onclick="document.getElementById('modDetailModal').classList.add('hidden')" class="px-4 py-2 bg-slate-800 text-slate-300 rounded-lg">닫기</button>
                <button onclick="installCurrentDetailMod()" class="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-lg shadow">📥 이 서버에 설치</button>
            </div>
        </div>
    </div>

    <script>
        function getOrCreateUser() {
            let saved = localStorage.getItem('mc_user');
            if (saved) {
                try { return JSON.parse(saved); } catch (e) {}
            }
            const randId = Math.random().toString(36).substring(2, 8);
            const newUser = {
                email: "player_steve@gmail.com",
                user_id: "usr-" + randId,
                balance_krw: 3000
            };
            localStorage.setItem('mc_user', JSON.stringify(newUser));
            return newUser;
        }

        let currentUser = getOrCreateUser();
        let myServers = [];
        let activeWsServer = null;
        let marketSource = "modrinth";
        let marketCategory = "all";
        let marketOffset = 0;
        let billingRates = { base_container_per_min: 0.20, per_ram_gb_rate: 0.08, per_cpu_core_rate: 0.05 };
        let domainCheckTimer = null;
        let logStreamInterval = null;
        let currentDetailModObj = null;

        function updateAuthState() {
            document.getElementById('sidebarEmail').innerText = currentUser.email;
            document.getElementById('sidebarBalance').innerText = (currentUser.balance_krw || 3000).toLocaleString() + ' KRW';
            document.getElementById('statBalance').innerText = (currentUser.balance_krw || 3000).toLocaleString() + ' KRW';
        }

        function editAccountEmail() {
            const newEmail = prompt("사용할 계정 이메일을 입력하세요:", currentUser.email);
            if (newEmail && newEmail.includes('@')) {
                currentUser.email = newEmail.trim().toLowerCase();
                localStorage.setItem('mc_user', JSON.stringify(currentUser));
                updateAuthState();
                loadMyServers();
            }
        }

        function switchView(viewName) {
            ['overview', 'servers', 'helpdesk'].forEach(v => {
                document.getElementById('view_' + v).classList.add('hidden');
                document.getElementById('nav_' + v).classList.remove('active');
            });
            document.getElementById('view_' + viewName).classList.remove('hidden');
            document.getElementById('nav_' + viewName).classList.add('active');

            const names = { overview: "대시보드 개요", servers: "내 마인크래프트 서버", helpdesk: "기술 지원 헬프데스크" };
            document.getElementById('pageBreadcrumb').innerText = names[viewName];
        }

        async function loadMyServers() {
            try {
                const cleanEmail = encodeURIComponent((currentUser.email || "player_steve@gmail.com").toLowerCase().trim());
                const resp = await fetch(`/api/v1/servers/my?user_email=${cleanEmail}`);
                if (resp.ok) {
                    const data = await resp.json();
                    myServers = data.map(s => ({
                        id: s.id,
                        name: s.name,
                        address: s.full_domain || `${s.domain_slug}.domain.com`,
                        type: s.server_type,
                        version: s.mc_version,
                        ram: s.allocated_ram_mb,
                        cpus: s.allocated_cpu_cores || 2,
                        cpuset: s.cpuset_cpus || "",
                        status: s.status || 'RUNNING'
                    }));
                    renderServers();
                }
            } catch (err) {
                console.error("Failed to load servers:", err);
            }
        }

        function renderServers() {
            const grid = document.getElementById('serversGrid');
            const empty = document.getElementById('emptyServers');
            document.getElementById('statServerCount').innerText = `${myServers.length}개`;
            document.getElementById('serverListCount').innerText = `${myServers.length}개 가동 중`;

            if (myServers.length === 0) { empty.classList.remove('hidden'); return; }
            empty.classList.add('hidden');
            grid.innerHTML = '';

            let totalRam = 0;
            let totalCores = 0;
            let totalCostHour = 0;

            myServers.forEach(srv => {
                totalRam += srv.ram;
                totalCores += srv.cpus;
                const ramGb = srv.ram / 1024;
                const costMin = (0.20 + (ramGb * 0.08) + (srv.cpus * 0.05)) * 1.3;
                totalCostHour += (costMin * 60);
                const coreTag = srv.cpuset ? `[Core #${srv.cpuset}]` : '';

                const card = document.createElement('div');
                card.className = 'glass-card rounded-2xl p-5 space-y-4 border border-indigo-500/20';
                card.innerHTML = `
                    <div class="flex items-center justify-between">
                        <div>
                            <span class="font-extrabold text-base text-white">${srv.name}</span>
                            <div class="flex items-center gap-1.5 mt-1">
                                <span class="px-2 py-0.5 bg-slate-800 text-slate-300 rounded font-mono text-[10px]">${srv.type} ${srv.version} (${srv.cpus} vCPU ${coreTag} / ${ramGb}GB RAM)</span>
                            </div>
                        </div>
                        <span class="px-2.5 py-1 text-xs font-mono font-bold ${srv.status === 'RUNNING' ? 'text-emerald-400 bg-emerald-950/80 border-emerald-500/30' : 'text-rose-400 bg-rose-950/80 border-rose-500/30'} rounded-full border flex items-center gap-1.5">
                            <span class="w-1.5 h-1.5 rounded-full ${srv.status === 'RUNNING' ? 'bg-emerald-400 animate-ping' : 'bg-rose-400'}"></span> ${srv.status}
                        </span>
                    </div>
                    <div class="p-3 bg-slate-950 rounded-xl border border-slate-800 space-y-1">
                        <span class="text-[9px] text-slate-500 uppercase font-bold">인게임 접속 주소 (포트 불필요)</span>
                        <div class="flex items-center justify-between">
                            <span class="font-mono text-indigo-300 font-bold">${srv.address}</span>
                            <button onclick="navigator.clipboard.writeText('${srv.address}'); alert('복사되었습니다!');" class="text-slate-400 hover:text-white underline">복사</button>
                        </div>
                    </div>
                    <div class="flex justify-end gap-2 pt-2 border-t border-slate-800">
                        <button onclick="openServerWorkspace('${srv.id}')" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 font-bold text-white rounded-xl shadow">
                            ⚙️ 서버 관리 워크스페이스 열기
                        </button>
                    </div>
                `;
                grid.appendChild(card);
            });

            document.getElementById('statTotalRam').innerText = `${(totalRam / 1024).toFixed(0)} GB / ${totalCores} Cores`;
            document.getElementById('statCostPerHour').innerText = `~${totalCostHour.toFixed(0)} KRW`;
        }

        function openCreateModal() {
            document.getElementById('createModal').classList.remove('hidden');
            updateEstimatedCost();
        }

        function closeCreateModal() {
            document.getElementById('createModal').classList.add('hidden');
        }

        function selectPreset(preset) {
            document.getElementById('selected_preset').value = preset;
            ['BUILDER_FLAT', 'SURVIVAL_SMP', 'ADVANCED_CUSTOM'].forEach(p => {
                const el = document.getElementById('preset_' + p);
                el.className = 'preset-card glass-card p-3.5 rounded-xl space-y-1.5 cursor-pointer border border-transparent';
            });
            document.getElementById('preset_' + preset).className = 'preset-card active glass-card p-3.5 rounded-xl space-y-1.5 cursor-pointer border border-indigo-500 bg-indigo-950/20';

            const adv = document.getElementById('advancedOptions');
            if (preset === 'ADVANCED_CUSTOM') {
                adv.classList.remove('hidden');
            } else {
                adv.classList.add('hidden');
            }
            updateEstimatedCost();
        }

        function toggleCustomDomainInput() {
            const isCustom = document.getElementById('enableCustomDomain').checked;
            const freeBox = document.getElementById('freeDomainNotice');
            const customBox = document.getElementById('customDomainBox');

            if (isCustom) {
                freeBox.classList.add('hidden');
                customBox.classList.remove('hidden');
                handleDomainInput();
            } else {
                freeBox.classList.remove('hidden');
                customBox.classList.add('hidden');
            }
        }

        function handleDomainInput() {
            clearTimeout(domainCheckTimer);
            const slug = document.getElementById('srv_slug').value.trim().toLowerCase();
            const tag = document.getElementById('domainStatusTag');
            const sugBox = document.getElementById('domainSuggestions');

            if (!slug || slug.length < 3) {
                tag.innerText = '3자 이상의 영문/숫자 입력';
                tag.className = 'text-[11px] text-slate-400';
                sugBox.innerText = '';
                return;
            }

            tag.innerText = '중복 검사 중...';
            tag.className = 'text-[11px] text-amber-400';

            domainCheckTimer = setTimeout(async () => {
                try {
                    const resp = await fetch(`/api/v1/servers/check-domain?slug=${slug}`);
                    const data = await resp.json();
                    if (data.is_available) {
                        tag.innerText = `✓ 사용 가능 (1,000 KRW 차감)`;
                        tag.className = 'text-[11px] text-emerald-400';
                        sugBox.innerText = '';
                    } else {
                        tag.innerText = `❌ 이미 사용 중인 도메인`;
                        tag.className = 'text-[11px] text-rose-400';
                        sugBox.innerHTML = `추천: ${data.suggested_slugs.map(s => `<a href="#" onclick="document.getElementById('srv_slug').value='${s}';handleDomainInput();return false;" class="underline mr-1">${s}</a>`).join('')}`;
                    }
                } catch (e) {}
            }, 300);
        }

        function syncCpuInput(source) {
            const numInput = document.getElementById('srv_cpu_cores');
            const rangeInput = document.getElementById('srv_cpu_range');

            let cpuVal = source === 'number' ? parseInt(numInput.value || 1) : parseInt(rangeInput.value || 1);
            if (isNaN(cpuVal) || cpuVal < 1) cpuVal = 1;
            if (cpuVal > 32) cpuVal = 32;

            numInput.value = cpuVal;
            rangeInput.value = Math.min(cpuVal, 16);
            updateEstimatedCost();
        }

        function syncRamInput(source) {
            const numInput = document.getElementById('srv_ram_gb');
            const rangeInput = document.getElementById('srv_ram_range');
            const tag = document.getElementById('ramMbTag');

            let gbVal = source === 'number' ? parseInt(numInput.value || 1) : parseInt(rangeInput.value || 1);
            if (isNaN(gbVal) || gbVal < 1) gbVal = 1;
            if (gbVal > 128) gbVal = 128;

            numInput.value = gbVal;
            rangeInput.value = Math.min(gbVal, 64);
            tag.innerText = `(${(gbVal * 1024).toLocaleString()} MB)`;

            updateEstimatedCost();
        }

        function updateEstimatedCost() {
            const preset = document.getElementById('selected_preset').value;
            let ramGb = 4;
            let cpuCores = 2;
            let mult = 1.3;

            if (preset === 'ADVANCED_CUSTOM') {
                ramGb = parseInt(document.getElementById('srv_ram_gb').value || 4);
                cpuCores = parseInt(document.getElementById('srv_cpu_cores').value || 2);
                const tierSelect = document.getElementById('srv_tier');
                const selectedOpt = tierSelect.options[tierSelect.selectedIndex];
                mult = selectedOpt ? parseFloat(selectedOpt.getAttribute('data-multiplier') || 1.0) : 1.0;
            }

            const baseRate = billingRates.base_container_per_min || 0.20;
            const ramRate = billingRates.per_ram_gb_rate || 0.08;
            const cpuRate = billingRates.per_cpu_core_rate || 0.05;

            const costPerMin = (baseRate + (ramGb * ramRate) + (cpuCores * cpuRate)) * mult;
            const costPerHour = costPerMin * 60;
            const costPerDay = costPerHour * 24;

            document.getElementById('estCostPerMin').innerText = `약 ${costPerMin.toFixed(2)} KRW / 분`;
            document.getElementById('estCostPerHour').innerText = `~${costPerHour.toFixed(1)} KRW`;
            document.getElementById('estCostPerDay').innerText = `~${costPerDay.toFixed(1)} KRW`;
        }

        document.getElementById('createForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const isCustomDomain = document.getElementById('enableCustomDomain').checked;
            const slug = isCustomDomain ? document.getElementById('srv_slug').value.trim().toLowerCase() : null;
            const preset = document.getElementById('selected_preset').value;

            let payload = {
                name: document.getElementById('srv_name').value,
                domain_slug: slug,
                is_custom_domain: isCustomDomain,
                preset_type: preset,
                target_user_id: (currentUser.email || "player_steve@gmail.com").toLowerCase().trim(),
                modpack_id: document.getElementById('selected_modpack_id').value || null
            };

            if (preset === 'ADVANCED_CUSTOM') {
                payload.server_type = document.getElementById('srv_type').value;
                payload.mc_version = document.getElementById('srv_version').value;
                payload.allocated_ram_mb = parseInt(document.getElementById('srv_ram_gb').value || 4) * 1024;
                payload.allocated_cpu_cores = parseInt(document.getElementById('srv_cpu_cores').value || 2);
                payload.hardware_tier_preference = document.getElementById('srv_tier').value;
            } else {
                payload.server_type = "PAPER";
                payload.mc_version = "1.20.4";
                payload.allocated_ram_mb = 4096;
                payload.allocated_cpu_cores = 2;
                payload.hardware_tier_preference = "high_nvme";
            }

            const btn = document.getElementById('deployBtn');
            btn.disabled = true;
            btn.innerText = '배포 중...';

            try {
                const resp = await fetch('/api/v1/servers/deploy', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const res = await resp.json();
                if (resp.ok) {
                    if (isCustomDomain) {
                        currentUser.balance_krw = Math.max(0, (currentUser.balance_krw || 3000) - 1000);
                        localStorage.setItem('mc_user', JSON.stringify(currentUser));
                        updateAuthState();
                    }
                    alert(res.message || `🎉 [${payload.server_type}] 서버 [${payload.name}] 배포 완료!\\n접속 주소: ${res.connect_address}`);
                    closeCreateModal();
                    await loadMyServers();
                    switchView('servers');
                } else {
                    alert('배포 실패: ' + (res.detail || JSON.stringify(res)));
                }
            } catch (err) {
                alert('오류: ' + err.message);
            } finally {
                btn.disabled = false;
                btn.innerText = '🚀 서버 배포';
            }
        });

        // =======================================================================
        // Server Detailed Workspace & Real-Time Console & Logs
        // =======================================================================
        function openServerWorkspace(serverId) {
            activeWsServer = myServers.find(s => s.id === serverId) || { id: serverId, name: "마인크래프트 서버", address: "alpha.domain.com", type: "PAPER", version: "26.2", ram: 4096, cpus: 2, cpuset: "", status: 'RUNNING' };
            document.getElementById('wsServerName').innerText = activeWsServer.name;
            document.getElementById('wsServerAddress').innerText = activeWsServer.address;
            const coreTag = activeWsServer.cpuset ? `[Core #${activeWsServer.cpuset}]` : '';
            document.getElementById('wsServerSpecs').innerText = `${activeWsServer.type} ${activeWsServer.version} (${activeWsServer.cpus} vCPU ${coreTag} / ${activeWsServer.ram / 1024}GB RAM)`;
            document.getElementById('wsServerStatus').innerText = activeWsServer.status;
            document.getElementById('serverWorkspaceModal').classList.remove('hidden');
            switchWsTab('console');
        }

        function closeServerWorkspace() {
            clearInterval(logStreamInterval);
            document.getElementById('serverWorkspaceModal').classList.add('hidden');
        }

        function switchWsTab(tabName) {
            clearInterval(logStreamInterval);
            ['console', 'version', 'properties', 'files', 'installed_mods', 'marketplace'].forEach(t => {
                document.getElementById('wspane_' + t).classList.add('hidden');
                document.getElementById('wstab_' + t).classList.remove('active');
            });
            document.getElementById('wspane_' + tabName).classList.remove('hidden');
            document.getElementById('wstab_' + tabName).classList.add('active');

            if (tabName === 'console') {
                startLogStreaming();
            } else if (tabName === 'properties') {
                loadServerPropertiesGui();
            } else if (tabName === 'files') {
                loadWsFiles("");
            } else if (tabName === 'installed_mods') {
                loadInstalledMods();
            } else if (tabName === 'marketplace') {
                loadMarketCategories();
                resetAndSearchMarket();
            }
        }

        async function fetchTerminalLogs() {
            if (!activeWsServer) return;
            try {
                const resp = await fetch(`/api/v1/servers/${activeWsServer.id}/logs`);
                if (resp.ok) {
                    const data = await resp.json();
                    const box = document.getElementById('rconBox');
                    if (data.logs && data.logs.length > 0) {
                        box.innerHTML = data.logs.map(line => {
                            let color = 'text-slate-300';
                            if (line.includes('ERROR') || line.includes('Exception') || line.includes('CRITICAL')) color = 'text-rose-400 font-bold';
                            else if (line.includes('WARN')) color = 'text-amber-300 font-semibold';
                            else if (line.includes('Done') || line.includes('Starting') || line.includes('SUCCESS') || line.includes('RCON')) color = 'text-emerald-400 font-bold';
                            else if (line.startsWith('>')) color = 'text-cyan-300 font-bold';
                            return `<div class="${color}">${escapeHtml(line)}</div>`;
                        }).join('');
                        box.scrollTop = box.scrollHeight;
                    }
                }
            } catch (e) {}
        }

        function startLogStreaming() {
            fetchTerminalLogs();
            clearInterval(logStreamInterval);
            logStreamInterval = setInterval(fetchTerminalLogs, 2500);
        }

        async function handleRconSubmit(event) {
            event.preventDefault(); // 페이지 새로고침 완전 방지
            const input = document.getElementById('wsRconInput');
            const cmd = input.value.trim();
            if (!cmd || !activeWsServer) return;

            const box = document.getElementById('rconBox');
            box.innerHTML += `<div class="text-cyan-300 font-bold">&gt; ${escapeHtml(cmd)}</div>`;
            box.scrollTop = box.scrollHeight;
            input.value = '';

            try {
                const resp = await fetch(`/api/v1/servers/${activeWsServer.id}/rcon`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command: cmd })
                });
                const res = await resp.json();
                if (resp.ok) {
                    box.innerHTML += `<div class="text-emerald-400 font-semibold">${escapeHtml(res.response || '명령어가 성공적으로 수행되었습니다.')}</div>`;
                } else {
                    box.innerHTML += `<div class="text-rose-400 font-bold">[Error] ${escapeHtml(res.detail || '실행 실패')}</div>`;
                }
                box.scrollTop = box.scrollHeight;
            } catch (e) {
                box.innerHTML += `<div class="text-rose-400">[Error] ${escapeHtml(e.message)}</div>`;
                box.scrollTop = box.scrollHeight;
            }
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.innerText = text;
            return div.innerHTML;
        }

        async function executeServerControlAction(action) {
            try {
                const resp = await fetch(`/api/v1/servers/${activeWsServer.id}/action`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: action })
                });
                const res = await resp.json();
                if (resp.ok) {
                    alert(`✓ ${res.message}`);
                    activeWsServer.status = res.new_status;
                    document.getElementById('wsServerStatus').innerText = res.new_status;
                    fetchTerminalLogs();
                    loadMyServers();
                } else {
                    alert('명령 실패: ' + (res.detail || JSON.stringify(res)));
                }
            } catch (e) { alert('오류: ' + e.message); }
        }

        async function deleteCurrentServer() {
            if (confirm(`정말로 서버 [${activeWsServer.name}]를 완전히 삭제하시겠습니까?`)) {
                try {
                    const resp = await fetch(`/api/v1/servers/${activeWsServer.id}`, { method: 'DELETE' });
                    if (resp.ok) {
                        alert('✓ 서버가 완전히 삭제되었습니다.');
                        closeServerWorkspace();
                        loadMyServers();
                    }
                } catch (e) { alert('삭제 오류: ' + e.message); }
            }
        }

        async function executeVersionSwitch() {
            const newCore = document.getElementById('switch_core').value;
            const newVer = document.getElementById('switch_version').value;
            const force = document.getElementById('switch_force').checked;

            try {
                const resp = await fetch(`/api/v1/servers/${activeWsServer.id}/version`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ server_type: newCore, mc_version: newVer, force: force })
                });
                const res = await resp.json();
                if (resp.ok) {
                    alert(`✓ 구동기 변경 완료: [${newCore} ${newVer}]`);
                    activeWsServer.type = newCore;
                    activeWsServer.version = newVer;
                    document.getElementById('wsServerSpecs').innerText = `${newCore} ${newVer} (${activeWsServer.cpus} vCPU / ${activeWsServer.ram / 1024}GB RAM)`;
                    fetchTerminalLogs();
                    loadMyServers();
                } else {
                    alert('변경 실패: ' + (res.detail || JSON.stringify(res)));
                }
            } catch (err) { alert('오류: ' + err.message); }
        }

        async function loadServerPropertiesGui() {
            try {
                const resp = await fetch(`/api/v1/servers/${activeWsServer.id}/properties`);
                const p = await resp.json();
                document.getElementById('prop_motd').value = p.motd;
                document.getElementById('prop_gamemode').value = p.gamemode;
                document.getElementById('prop_difficulty').value = p.difficulty;
                document.getElementById('prop_max_players').value = p.max_players;
                document.getElementById('prop_view_distance').value = p.view_distance;
                document.getElementById('prop_sim_distance').value = p.simulation_distance;
                document.getElementById('prop_pvp').checked = p.pvp;
                document.getElementById('prop_online_mode').checked = p.online_mode;
                document.getElementById('prop_allow_flight').checked = p.allow_flight;
                document.getElementById('prop_whitelist').checked = p.white_list;
                document.getElementById('prop_hardcore').checked = p.hardcore;
                document.getElementById('prop_monsters').checked = p.spawn_monsters;
            } catch (e) {}
        }

        async function saveServerPropertiesGui() {
            const payload = {
                motd: document.getElementById('prop_motd').value,
                gamemode: document.getElementById('prop_gamemode').value,
                difficulty: document.getElementById('prop_difficulty').value,
                max_players: parseInt(document.getElementById('prop_max_players').value),
                view_distance: parseInt(document.getElementById('prop_view_distance').value),
                simulation_distance: parseInt(document.getElementById('prop_sim_distance').value),
                pvp: document.getElementById('prop_pvp').checked,
                online_mode: document.getElementById('prop_online_mode').checked,
                allow_flight: document.getElementById('prop_allow_flight').checked,
                white_list: document.getElementById('prop_whitelist').checked,
                hardcore: document.getElementById('prop_hardcore').checked,
                spawn_monsters: document.getElementById('prop_monsters').checked
            };

            try {
                const resp = await fetch(`/api/v1/servers/${activeWsServer.id}/properties`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (resp.ok) alert('✓ server.properties가 성공적으로 저장되었습니다!');
            } catch (err) { alert('저장 실패: ' + err.message); }
        }

        async function loadInstalledMods() {
            const list = document.getElementById('installedModsList');
            list.innerHTML = '<div class="text-slate-400 py-6 text-center">모드 목록 불러오는 중...</div>';
            try {
                const resp = await fetch(`/api/v1/servers/${activeWsServer.id}/installed-mods`);
                const mods = await resp.json();
                list.innerHTML = '';
                if (!mods || mods.length === 0) {
                    list.innerHTML = '<div class="text-slate-400 py-6 text-center">설치된 모드 또는 플러그인이 없습니다. [모드 마켓플레이스] 탭에서 설치해보세요.</div>';
                    return;
                }
                mods.forEach(m => {
                    const row = document.createElement('div');
                    row.className = 'p-3 bg-slate-900 rounded-xl border border-slate-800 flex items-center justify-between';
                    row.innerHTML = `
                        <div class="space-y-0.5">
                            <span class="font-bold text-white">${m.title}</span>
                            <div class="text-[10px] text-slate-400 font-mono">${m.filename} (현재: ${m.current_version} &rarr; 최신: <strong class="text-emerald-400">${m.latest_version}</strong>)</div>
                        </div>
                        <span class="px-2 py-1 rounded text-[10px] font-bold ${m.has_update ? 'bg-amber-950 text-amber-300' : 'bg-slate-800 text-slate-400'}">
                            ${m.has_update ? '업데이트 가능' : '최신 버전'}
                        </span>
                    `;
                    list.appendChild(row);
                });
            } catch (e) {}
        }

        async function updateAllInstalledMods() {
            try {
                const resp = await fetch(`/api/v1/servers/${activeWsServer.id}/mods/update`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mod_ids: [] })
                });
                const res = await resp.json();
                alert(`✓ ${res.message}`);
                loadInstalledMods();
            } catch (err) { alert('오류: ' + err.message); }
        }

        // Marketplace
        function selectMarketplaceSource(src) {
            marketSource = src;
            ['modrinth', 'curseforge'].forEach(s => {
                document.getElementById('src_' + s).classList.remove('active');
            });
            document.getElementById('src_' + src).classList.add('active');
            loadMarketCategories();
            resetAndSearchMarket();
        }

        async function loadMarketCategories() {
            const container = document.getElementById('categoryChipsContainer');
            container.innerHTML = '';
            try {
                const resp = await fetch(`/api/v1/servers/mods/categories?source=${marketSource}`);
                const cats = await resp.json();

                const allChip = document.createElement('button');
                allChip.className = `chip px-2.5 py-1 rounded-full text-[11px] font-semibold border ${marketCategory === 'all' ? 'active' : 'border-slate-800 text-slate-400 hover:text-white'}`;
                allChip.innerText = '전체 카테고리';
                allChip.onclick = () => { marketCategory = 'all'; loadMarketCategories(); resetAndSearchMarket(); };
                container.appendChild(allChip);

                cats.forEach(c => {
                    const btn = document.createElement('button');
                    btn.className = `chip px-2.5 py-1 rounded-full text-[11px] font-semibold border ${marketCategory === c.id ? 'active' : 'border-slate-800 text-slate-400 hover:text-white'}`;
                    btn.innerText = c.name;
                    btn.onclick = () => { marketCategory = c.id; loadMarketCategories(); resetAndSearchMarket(); };
                    container.appendChild(btn);
                });
            } catch (e) {}
        }

        function resetAndSearchMarket() {
            marketOffset = 0;
            document.getElementById('marketGrid').innerHTML = '';
            loadMoreMarketItems();
        }

        async function loadMoreMarketItems() {
            const query = document.getElementById('marketSearchInput').value.trim();
            const projectType = document.getElementById('marketTypeFilter').value;
            const version = document.getElementById('marketVerFilter').value;
            const grid = document.getElementById('marketGrid');
            const loadBtn = document.getElementById('loadMoreBtn');

            loadBtn.innerText = '불러오는 중...';

            let url = `/api/v1/servers/mods/search?query=${encodeURIComponent(query)}&source=${marketSource}&category=${marketCategory}&version=${version}&offset=${marketOffset}&limit=8`;
            if (projectType) url += `&project_type=${projectType}`;

            try {
                const resp = await fetch(url);
                const items = await resp.json();
                loadBtn.innerText = '⬇️ 다음 페이지 더 불러오기';

                if (!items || items.length === 0) {
                    if (marketOffset === 0) grid.innerHTML = '<div class="col-span-2 text-center text-slate-400 py-12">검색 결과가 없습니다.</div>';
                    loadBtn.classList.add('hidden');
                    return;
                }
                loadBtn.classList.remove('hidden');

                items.forEach(m => {
                    const card = document.createElement('div');
                    card.className = 'glass-card p-3.5 rounded-xl border border-slate-800 space-y-2 flex flex-col justify-between';
                    card.innerHTML = `
                        <div class="flex items-start gap-2.5">
                            <img src="${m.icon_url || 'https://cdn.modrinth.com/data/AANobbMI/icon.png'}" class="w-10 h-10 rounded-xl bg-slate-900 object-cover flex-shrink-0">
                            <div class="space-y-0.5 overflow-hidden">
                                <div class="flex items-center gap-1.5">
                                    <span class="font-extrabold text-white truncate">${m.title}</span>
                                    <span class="px-1.5 py-0.5 rounded text-[9px] ${m.project_type === 'modpack' ? 'bg-amber-950 text-amber-300' : 'bg-indigo-950 text-indigo-300'} font-bold">${m.project_type.toUpperCase()}</span>
                                </div>
                                <p class="text-[10px] text-slate-400 line-clamp-2">${m.description}</p>
                            </div>
                        </div>
                        <div class="flex items-center justify-between pt-1 border-t border-slate-800 text-[10px]">
                            <span class="text-slate-500 font-mono">📥 ${(m.downloads > 1000000 ? (m.downloads/1000000).toFixed(1)+'M' : m.downloads)}</span>
                            <div class="flex gap-1">
                                <button onclick="viewModDetails('${m.id}')" class="px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded text-slate-200">소개</button>
                                <button onclick="installModToActiveServer('${m.id}', '${m.project_type}')" class="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded">설치</button>
                            </div>
                        </div>
                    `;
                    grid.appendChild(card);
                });

                marketOffset += items.length;
            } catch (e) { loadBtn.innerText = '더 불러오기'; }
        }

        async function viewModDetails(modId) {
            try {
                const resp = await fetch(`/api/v1/servers/mods/${modId}`);
                const data = await resp.json();
                currentDetailModObj = data;
                document.getElementById('detailModIcon').src = data.icon_url || '';
                document.getElementById('detailModTitle').innerText = data.title;
                document.getElementById('detailModAuthor').innerText = `by ${data.author} (${data.project_type.toUpperCase()})`;
                document.getElementById('detailModBody').innerHTML = `<p>${data.description}</p><div class="mt-3">${data.body_markdown}</div>`;
                document.getElementById('modDetailModal').classList.remove('hidden');
            } catch (e) {}
        }

        async function installModToActiveServer(modId, projectType) {
            try {
                const resp = await fetch(`/api/v1/servers/${activeWsServer.id}/mods/install`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mod_id: modId, project_type: projectType, source: marketSource })
                });
                const res = await resp.json();
                if (resp.ok) alert(`✓ [${modId}] 설치 완료! 서버 재시작 시 적용됩니다.`);
            } catch (e) {}
        }

        async function loadWsFiles(path) {
            try {
                const resp = await fetch(`/api/v1/servers/${activeWsServer.id}/files?path=${encodeURIComponent(path)}`);
                const files = await resp.json();
                const tbody = document.getElementById('wsFileTableBody');
                tbody.innerHTML = '';
                files.forEach(f => {
                    const tr = document.createElement('tr');
                    tr.className = 'hover:bg-slate-900/60';
                    tr.innerHTML = `
                        <td class="p-2">${f.is_dir ? '📁' : '📄'} ${f.name}</td>
                        <td class="p-2 text-slate-400">${f.is_dir ? '-' : (f.size_bytes / 1024).toFixed(1) + ' KB'}</td>
                        <td class="p-2 text-slate-500">${f.modified_at}</td>
                        <td class="p-2 text-right">
                            ${!f.is_dir ? `<a href="/api/v1/servers/${activeWsServer.id}/files/download?path=${encodeURIComponent(f.path)}" class="px-2 py-0.5 bg-slate-800 rounded">다운로드</a>` : ''}
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            } catch (e) {}
        }

        function downloadWorldBackup() {
            window.location.href = `/api/v1/servers/${activeWsServer.id}/world/download`;
        }

        function topupCredit() {
            const amount = prompt("충전할 크레딧 금액을 입력하십시오 (KRW):", "10000");
            if (amount && !isNaN(amount)) {
                currentUser.balance_krw = (currentUser.balance_krw || 3000) + parseInt(amount);
                localStorage.setItem('mc_user', JSON.stringify(currentUser));
                updateAuthState();
                alert(amount + '원이 성공적으로 충전되었습니다!');
            }
        }

        updateAuthState();
        loadMyServers();

        window.addEventListener('DOMContentLoaded', () => {
            loadMyServers();
            const urlParams = new URLSearchParams(window.location.search);
            const modpack = urlParams.get('modpack');
            if (modpack) {
                document.getElementById('selected_modpack_id').value = modpack;
                document.getElementById('srv_name').value = `[모드팩] ${modpack}`;
                selectPreset('ADVANCED_CUSTOM');
                openCreateModal();
            }
        });
    </script>
</body>
</html>"""

# ==============================================================================
# 3. Master Admin Center HTML (/admin)
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

    <header class="flex flex-col md:flex-row items-start md:items-center justify-between pb-4 border-b border-slate-800 gap-4">
        <div>
            <h1 class="text-2xl font-black text-white flex items-center gap-3">
                <span class="p-2 bg-indigo-600 text-white rounded-xl shadow-lg shadow-indigo-600/30">⚙️</span>
                NextGen MC 어드민 통합 제어 센터
            </h1>
            <p class="text-xs text-slate-400 mt-1">RAM/vCPU 요율 & 커스텀 티어 • 스왑/ZRAM 설정 • 회원 크레딧 • 전체 서버 관리</p>
        </div>
        <div class="flex items-center gap-3">
            <a href="/dashboard" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-semibold">👉 유저 대시보드</a>
            <button onclick="adminLogout()" class="px-3 py-1.5 bg-rose-950/80 hover:bg-rose-900 text-rose-300 border border-rose-500/30 rounded-xl text-xs font-bold">🔒 관리자 로그아웃</button>
        </div>
    </header>

    <div class="flex flex-wrap gap-2 border-b border-slate-800 pb-3">
        <button onclick="switchTab('billing')" id="tab_billing" class="tab-btn active px-4 py-2 rounded-xl text-xs font-bold bg-slate-800 hover:bg-indigo-600 transition flex items-center gap-2">
            💰 1. RAM/vCPU 요율 & 커스텀 티어 & 스왑
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

    <!-- TAB 1: Billing & Tiers -->
    <div id="section_billing" class="space-y-6">
        <div class="card rounded-2xl p-6 space-y-5">
            <div class="flex items-center justify-between border-b border-slate-800 pb-3">
                <h3 class="font-bold text-white text-base">💰 실시간 종량제 요율 설정 (RAM, vCPU 및 기본 단가)</h3>
                <button onclick="loadBillingRates()" class="text-xs text-indigo-400 hover:underline">새로고침</button>
            </div>
            <form id="ratesForm" class="grid grid-cols-1 md:grid-cols-5 gap-4 text-xs">
                <div class="space-y-1.5">
                    <label class="font-bold text-slate-300 uppercase">기본 유지비 (분당 KRW)</label>
                    <input type="number" step="0.01" id="rate_base" class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-100 outline-none" required>
                </div>
                <div class="space-y-1.5">
                    <label class="font-bold text-indigo-300 uppercase">점유 RAM 1GB당 (분당 KRW)</label>
                    <input type="number" step="0.01" id="rate_ram_gb" class="w-full px-3 py-2 bg-slate-900 border border-indigo-500 rounded-lg text-indigo-200 font-bold outline-none" required>
                </div>
                <div class="space-y-1.5">
                    <label class="font-bold text-cyan-300 uppercase">vCPU 1Core당 (분당 KRW)</label>
                    <input type="number" step="0.01" id="rate_cpu" class="w-full px-3 py-2 bg-slate-900 border border-cyan-500 rounded-lg text-cyan-200 font-bold outline-none" required>
                </div>
                <div class="space-y-1.5">
                    <label class="font-bold text-slate-300 uppercase">청크당 요율 (분당 KRW)</label>
                    <input type="number" step="0.0001" id="rate_chunk" class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-100 outline-none" required>
                </div>
                <div class="space-y-1.5">
                    <label class="font-bold text-slate-300 uppercase">플레이어당 (분당 KRW)</label>
                    <input type="number" step="0.01" id="rate_player" class="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-100 outline-none" required>
                </div>
                <div class="md:col-span-5 flex justify-end">
                    <button type="submit" class="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-xl shadow-lg">요율 실시간 저장</button>
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
            <table class="w-full text-left text-xs font-mono">
                <thead class="text-slate-400 uppercase bg-slate-900 border-b border-slate-800">
                    <tr><th class="p-3">ID</th><th class="p-3">이메일</th><th class="p-3">상태</th><th class="p-3">보유 크레딧</th><th class="p-3 text-right">작업</th></tr>
                </thead>
                <tbody id="usersTableBody" class="divide-y divide-slate-800"></tbody>
            </table>
        </div>
    </div>

    <!-- TAB 3: Tickets -->
    <div id="section_tickets" class="hidden space-y-5">
        <div class="card rounded-2xl p-6 space-y-4">
            <h3 class="font-bold text-white text-base">🎫 고객지원 민원 접수 & AI 렉 리포트</h3>
            <div id="ticketsList" class="space-y-4"></div>
        </div>
    </div>

    <!-- TAB 4: Servers -->
    <div id="section_servers" class="hidden space-y-6">
        <div class="card rounded-2xl p-6 space-y-4">
            <h3 class="font-bold text-white text-base">🎮 클러스터 전체 실행 중인 서버 목록</h3>
            <div id="adminServersGrid" class="grid grid-cols-1 md:grid-cols-2 gap-4"></div>
        </div>
    </div>

    <!-- TAB 5: Settings -->
    <div id="section_settings" class="hidden space-y-6">
        <div class="card rounded-2xl p-6 space-y-4">
            <h3 class="font-bold text-white text-base">🔧 시스템 연동 환경설정</h3>
            <p class="text-slate-400 text-xs">Google OAuth 및 LLM AI 추론 엔드포인트가 정상 등록되어 있습니다.</p>
        </div>
    </div>

    <script>
        let adminToken = sessionStorage.getItem('mc_admin_token') || null;

        function getAuthHeaders() {
            return { 'Content-Type': 'application/json', 'Authorization': `Bearer ${adminToken}` };
        }

        function verifyAdminAuth() {
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
            } catch (err) { errBox.innerText = '오류: ' + err.message; errBox.classList.remove('hidden'); }
        });

        function switchTab(tabId) {
            if (!adminToken) { verifyAdminAuth(); return; }
            ['billing', 'users', 'tickets', 'servers', 'settings'].forEach(t => {
                document.getElementById('section_' + t).classList.add('hidden');
                document.getElementById('tab_' + t).classList.remove('active');
            });
            document.getElementById('section_' + tabId).classList.remove('hidden');
            document.getElementById('tab_' + tabId).classList.add('active');

            if (tabId === 'billing') loadBillingRates();
            if (tabId === 'users') loadAdminUsers();
            if (tabId === 'tickets') loadAdminTickets();
            if (tabId === 'servers') loadAdminServers();
        }

        async function loadBillingRates() {
            if (!adminToken) return;
            const resp = await fetch('/api/v1/nodes/admin/billing/rates', { headers: getAuthHeaders() });
            const d = await resp.json();
            document.getElementById('rate_base').value = d.base_container_per_min;
            document.getElementById('rate_ram_gb').value = d.per_ram_gb_rate;
            document.getElementById('rate_cpu').value = d.per_cpu_core_rate || 0.05;
            document.getElementById('rate_chunk').value = d.per_chunk_rate;
            document.getElementById('rate_player').value = d.per_player_rate;
        }

        document.getElementById('ratesForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const payload = {
                base_container_per_min: parseFloat(document.getElementById('rate_base').value),
                per_ram_gb_rate: parseFloat(document.getElementById('rate_ram_gb').value),
                per_cpu_core_rate: parseFloat(document.getElementById('rate_cpu').value),
                per_chunk_rate: parseFloat(document.getElementById('rate_chunk').value),
                per_player_rate: parseFloat(document.getElementById('rate_player').value)
            };
            await fetch('/api/v1/nodes/admin/billing/rates', {
                method: 'PUT',
                headers: getAuthHeaders(),
                body: JSON.stringify(payload)
            });
            alert('과금 요율이 실시간 저장되었습니다!');
        });

        async function loadAdminNodes() {
            if (!adminToken) return;
            const resp = await fetch('/api/v1/nodes/admin/overview', { headers: getAuthHeaders() });
            const data = await resp.json();
            const container = document.getElementById('adminNodesGrid');
            container.innerHTML = '';
            data.nodes.forEach(n => {
                const card = document.createElement('div');
                card.className = 'p-4 bg-slate-900 rounded-xl border border-slate-800 text-xs space-y-2';
                card.innerHTML = `
                    <div class="flex justify-between items-center">
                        <span class="font-bold text-white">${n.node_name}</span>
                        <span class="px-2 py-0.5 rounded font-mono bg-emerald-950 text-emerald-400">${n.status}</span>
                    </div>
                    <div class="space-y-1 text-slate-400">
                        <div>CPU: ${n.cpu_usage_pct.toFixed(1)}% | RAM: ${n.ram_used_mb}MB / ${n.ram_total_mb}MB</div>
                        <div>활성 컨테이너: <strong class="text-indigo-400">${n.running_containers}</strong></div>
                    </div>
                `;
                container.appendChild(card);
            });
        }

        async function loadAdminUsers() {
            if (!adminToken) return;
            const resp = await fetch('/api/v1/auth/admin/users', { headers: getAuthHeaders() });
            const users = await resp.json();
            const tbody = document.getElementById('usersTableBody');
            tbody.innerHTML = '';
            users.forEach(u => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td class="p-3 text-slate-400">${u.id}</td>
                    <td class="p-3 text-white font-semibold">${u.email}</td>
                    <td class="p-3 text-emerald-400">${u.status}</td>
                    <td class="p-3 text-emerald-400 font-bold">${u.balance_krw.toLocaleString()} KRW</td>
                    <td class="p-3 text-right">
                        <button onclick="alert('크레딧 조정')" class="px-2 py-1 bg-indigo-600/30 text-indigo-300 rounded">지급</button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        }

        async function loadAdminTickets() {
            if (!adminToken) return;
            const resp = await fetch('/api/v1/servers/admin/tickets', { headers: getAuthHeaders() });
            const tickets = await resp.json();
            const list = document.getElementById('ticketsList');
            list.innerHTML = '';
            tickets.forEach(t => {
                const item = document.createElement('div');
                item.className = 'p-4 bg-slate-900 rounded-xl border border-slate-800 space-y-2 text-xs';
                item.innerHTML = `
                    <div class="flex justify-between items-center font-bold">
                        <span class="text-white">[${t.id}] ${t.title}</span>
                        <span class="px-2 py-0.5 rounded bg-amber-950 text-amber-400">${t.status}</span>
                    </div>
                    <p class="text-slate-300">${t.user_message}</p>
                `;
                list.appendChild(item);
            });
        }

        async function loadAdminServers() {
            if (!adminToken) return;
            const resp = await fetch('/api/v1/servers/admin/all', { headers: getAuthHeaders() });
            const servers = await resp.json();
            const grid = document.getElementById('adminServersGrid');
            grid.innerHTML = '';
            servers.forEach(s => {
                const card = document.createElement('div');
                card.className = 'p-4 bg-slate-900 rounded-xl border border-slate-800 space-y-2 text-xs';
                card.innerHTML = `
                    <div class="flex justify-between font-bold text-white">
                        <span>${s.name}</span>
                        <span class="text-emerald-400 font-mono">${s.status}</span>
                    </div>
                    <div class="text-slate-400 font-mono">
                        <div>도메인: ${s.full_domain}</div>
                        <div>코어: ${s.server_type} ${s.mc_version} (${s.allocated_cpu_cores || 2} vCPU / ${s.allocated_ram_mb/1024}GB)</div>
                    </div>
                `;
                grid.appendChild(card);
            });
        }

        verifyAdminAuth();
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
    description="Next-Gen Cloud-Native Minecraft Hosting Platform API with File Explorer and Mod Marketplace",
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
async def landing_page():
    return LANDING_PAGE_HTML

@app.get("/dashboard", response_class=HTMLResponse)
@app.get("/console", response_class=HTMLResponse)
async def user_dashboard():
    return USER_DASHBOARD_HTML

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard():
    return ADMIN_DASHBOARD_HTML

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "features": [
            "real_time_terminal_logs_streaming",
            "non_reloading_rcon_console",
            "integer_vcpu_cores_direct_input",
            "multi_worker_persistent_registry",
            "ownership_association"
        ],
        "master_as_worker_active": "master-local" in scheduler.nodes
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8005, reload=True)
