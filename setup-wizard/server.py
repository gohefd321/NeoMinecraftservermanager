#!/usr/bin/env python3
"""
server.py - NextGen MC Platform Web Setup Wizard Server
Features:
- Includes Google OAuth API Credentials & Local LLM Endpoint Configuration
- Embedded Responsive HTML (Zero missing static file 404 errors)
- Automatic Port Conflict Resolution (Auto fallback: 8080 -> 8081 -> 8082...)
"""
import os
import sys
import json
import time
import re
import socket
import subprocess
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NextGen MC Platform - Node Initialization Wizard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@300;400;600;700;800&display=swap');
        body { font-family: 'Pretendard', sans-serif; background: radial-gradient(circle at top, #1e1b4b, #0f172a, #020617); min-height: 100vh; }
        .glass { background: rgba(15, 23, 42, 0.85); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.12); }
    </style>
</head>
<body class="text-slate-100 flex items-center justify-center p-4 py-8">
    <div class="glass max-w-2xl w-full rounded-2xl p-8 shadow-2xl space-y-6">
        <div class="text-center space-y-2">
            <div class="inline-flex items-center justify-center w-14 h-14 rounded-xl bg-indigo-600/30 border border-indigo-500/30 text-indigo-400 mb-2">
                <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path>
                </svg>
            </div>
            <h1 class="text-2xl font-bold tracking-tight text-white">NextGen MC Hosting Setup Wizard</h1>
            <p class="text-xs text-slate-400">클러스터 노드 역할, Google OAuth 로그인 및 로컬 AI(LLM) 환경을 구성하십시오.</p>
        </div>

        <form id="setupForm" class="space-y-5">
            <!-- Node Role Selection -->
            <div>
                <label class="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2">노드 역할 (Node Role)</label>
                <div class="grid grid-cols-2 gap-3">
                    <label class="cursor-pointer border border-indigo-500 bg-indigo-950/40 rounded-xl p-4 flex flex-col items-center justify-center space-y-2 transition-all duration-200" id="masterCard">
                        <input type="radio" name="node_role" value="master" class="hidden" checked onchange="handleRoleChange('master')">
                        <span class="font-bold text-sm text-indigo-300">Master Node (대장)</span>
                        <span class="text-[11px] text-slate-400 text-center">API 서버(:8005), 유저/어드민 웹, 과금 엔진, 로컬 컨테이너</span>
                    </label>
                    <label class="cursor-pointer border border-slate-700 bg-slate-800/60 rounded-xl p-4 flex flex-col items-center justify-center space-y-2 transition-all duration-200" id="workerCard">
                        <input type="radio" name="node_role" value="worker" class="hidden" onchange="handleRoleChange('worker')">
                        <span class="font-bold text-sm text-slate-300">Worker Node (작업)</span>
                        <span class="text-[11px] text-slate-400 text-center">도커 격리 컨테이너 구동, ZRAM 다층 메모리</span>
                    </label>
                </div>
            </div>

            <!-- Common Fields -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                    <label class="block text-xs font-medium text-slate-300 mb-1">노드 명칭 (Node Name)</label>
                    <input type="text" id="node_name" name="node_name" required placeholder="예: seoul-master-01" class="w-full px-3.5 py-2 rounded-lg bg-slate-900/80 border border-slate-700 text-xs focus:outline-none focus:border-indigo-500">
                </div>
                <div>
                    <label class="block text-xs font-medium text-slate-300 mb-1">노드 고유 식별자 (Node UUID)</label>
                    <input type="text" id="node_id" name="node_id" readonly class="w-full px-3.5 py-2 rounded-lg bg-slate-950/80 border border-slate-800 text-xs font-mono text-slate-400 focus:outline-none">
                </div>
            </div>

            <!-- Master-Specific Fields -->
            <div id="masterFields" class="space-y-4 border-t border-slate-800 pt-4">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs font-medium text-slate-300 mb-1">관리자 이메일 (SuperAdmin)</label>
                        <input type="email" id="admin_email" name="admin_email" required value="admin@domain.com" class="w-full px-3.5 py-2 rounded-lg bg-slate-900/80 border border-slate-700 text-xs focus:outline-none focus:border-indigo-500">
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-slate-300 mb-1">클러스터 마스터 시크릿 키</label>
                        <input type="password" id="master_secret" name="master_secret" required value="cluster-secret-key-12345" class="w-full px-3.5 py-2 rounded-lg bg-slate-900/80 border border-slate-700 text-xs focus:outline-none focus:border-indigo-500">
                    </div>
                </div>

                <!-- Google OAuth Configuration -->
                <div class="p-3.5 bg-slate-900/60 rounded-xl border border-slate-800 space-y-2.5">
                    <div class="flex items-center gap-2">
                        <span class="text-xs font-bold text-indigo-400">🔑 구글 계정 간편 로그인 연동 (Google OAuth API)</span>
                    </div>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-2.5 text-xs">
                        <div>
                            <label class="block text-[11px] text-slate-400 mb-1">Google Client ID</label>
                            <input type="text" id="google_client_id" name="google_client_id" placeholder="xxxx.apps.googleusercontent.com" class="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-xs outline-none focus:border-indigo-500">
                        </div>
                        <div>
                            <label class="block text-[11px] text-slate-400 mb-1">Google Client Secret</label>
                            <input type="password" id="google_client_secret" name="google_client_secret" placeholder="GOCSPX-xxxx" class="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-xs outline-none focus:border-indigo-500">
                        </div>
                    </div>
                </div>

                <!-- Local LLM AI Profiler Configuration -->
                <div class="p-3.5 bg-slate-900/60 rounded-xl border border-slate-800 space-y-2.5">
                    <div class="flex items-center gap-2">
                        <span class="text-xs font-bold text-amber-400">🤖 로컬 AI 렉 진단기 연동 (llama.cpp / TabbyAPI)</span>
                    </div>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-2.5 text-xs">
                        <div>
                            <label class="block text-[11px] text-slate-400 mb-1">Local LLM API URL</label>
                            <input type="text" id="local_llm_url" name="local_llm_url" value="http://localhost:8000/v1/chat/completions" class="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-xs font-mono outline-none focus:border-indigo-500">
                        </div>
                        <div>
                            <label class="block text-[11px] text-slate-400 mb-1">LLM 모델명</label>
                            <input type="text" id="local_llm_model" name="local_llm_model" value="qwen-2.5-32b-instruct" class="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-xs font-mono outline-none focus:border-indigo-500">
                        </div>
                    </div>
                </div>
            </div>

            <!-- Worker-Specific Fields (Hidden by default) -->
            <div id="workerFields" class="space-y-3 hidden border-t border-slate-800 pt-3">
                <div>
                    <label class="block text-xs font-medium text-slate-300 mb-1">Master 노드 API 주소</label>
                    <input type="text" id="master_endpoint" name="master_endpoint" placeholder="http://192.168.1.100:8005" class="w-full px-3.5 py-2 rounded-lg bg-slate-900/80 border border-slate-700 text-xs focus:outline-none focus:border-indigo-500">
                </div>
                <div>
                    <label class="block text-xs font-medium text-slate-300 mb-1">클러스터 보안 인증 토큰 (Cluster Secret)</label>
                    <input type="password" id="cluster_token" name="cluster_token" placeholder="클러스터 공통 시크릿 키 입력" class="w-full px-3.5 py-2 rounded-lg bg-slate-900/80 border border-slate-700 text-xs focus:outline-none focus:border-indigo-500">
                </div>
                <div>
                    <label class="block text-xs font-medium text-slate-300 mb-1">하드웨어 스펙 티어</label>
                    <select id="hardware_tier" name="hardware_tier" class="w-full px-3.5 py-2 rounded-lg bg-slate-900/80 border border-slate-700 text-xs focus:outline-none focus:border-indigo-500">
                        <option value="standard_ssd">표준 SSD 노드 (1.0x 배율)</option>
                        <option value="high_nvme">고성능 Gen4 NVMe 노드 (1.3x 배율)</option>
                        <option value="extreme_dedicated">최고성능 단독 코어 노드 (1.8x 배율)</option>
                    </select>
                </div>
            </div>

            <button type="submit" id="submitBtn" class="w-full py-3 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 font-semibold text-sm shadow-lg shadow-indigo-600/30 transition duration-150 ease-in-out">
                설정 완료 및 백그라운드 서비스 시작
            </button>
        </form>

        <div id="statusBox" class="hidden p-4 rounded-xl text-center text-xs space-y-2"></div>
    </div>

    <script>
        function uuidv4() {
            return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
                (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
            );
        }
        document.getElementById('node_id').value = 'node-' + uuidv4().substring(0, 13);
        document.getElementById('node_name').value = 'master-node-' + Math.floor(1000 + Math.random() * 9000);

        function handleRoleChange(role) {
            const masterFields = document.getElementById('masterFields');
            const workerFields = document.getElementById('workerFields');
            const masterCard = document.getElementById('masterCard');
            const workerCard = document.getElementById('workerCard');

            if (role === 'master') {
                masterFields.classList.remove('hidden');
                workerFields.classList.add('hidden');
                masterCard.className = 'cursor-pointer border border-indigo-500 bg-indigo-950/40 rounded-xl p-4 flex flex-col items-center justify-center space-y-2 transition-all duration-200';
                workerCard.className = 'cursor-pointer border border-slate-700 bg-slate-800/60 rounded-xl p-4 flex flex-col items-center justify-center space-y-2 transition-all duration-200';
            } else {
                masterFields.classList.add('hidden');
                workerFields.classList.remove('hidden');
                workerCard.className = 'cursor-pointer border border-indigo-500 bg-indigo-950/40 rounded-xl p-4 flex flex-col items-center justify-center space-y-2 transition-all duration-200';
                masterCard.className = 'cursor-pointer border border-slate-700 bg-slate-800/60 rounded-xl p-4 flex flex-col items-center justify-center space-y-2 transition-all duration-200';
            }
        }

        document.getElementById('setupForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('submitBtn');
            const statusBox = document.getElementById('statusBox');
            btn.disabled = true;
            btn.innerText = '인프라 설정 적용 및 서비스 등록 중...';

            const formData = new FormData(e.target);
            const payload = Object.fromEntries(formData.entries());

            try {
                const resp = await fetch('/api/setup/complete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const result = await resp.json();
                if (resp.ok) {
                    statusBox.className = 'p-4 rounded-xl bg-emerald-950/60 border border-emerald-500/40 text-emerald-300 text-center text-xs';
                    statusBox.innerHTML = `<strong>성공!</strong> ${result.message}<br>잠시 후 임시 웹 서버가 종료되고 포트 8005에서 Master 서비스가 시작됩니다.`;
                    statusBox.classList.remove('hidden');
                } else {
                    throw new Error(result.error || '설정 처리 중 오류가 발생했습니다.');
                }
            } catch (err) {
                statusBox.className = 'p-4 rounded-xl bg-rose-950/60 border border-rose-500/40 text-rose-300 text-center text-xs';
                statusBox.innerHTML = `<strong>오류 발생:</strong> ${err.message}`;
                statusBox.classList.remove('hidden');
                btn.disabled = false;
                btn.innerText = '다시 시도';
            }
        });
    </script>
</body>
</html>"""

VALID_IDENTIFIER = re.compile(r"^[a-zA-Z0-9_\-\.]{3,64}$")

class SetupWizardHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        html_bytes = HTML_TEMPLATE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html_bytes)))
        self.end_headers()

    def do_GET(self):
        html_bytes = HTML_TEMPLATE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html_bytes)))
        self.end_headers()
        self.wfile.write(html_bytes)

    def do_POST(self):
        if self.path == "/api/setup/complete":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                self.send_error(400, "Invalid JSON")
                return

            node_role = str(payload.get("node_role", "master")).strip()
            node_name = str(payload.get("node_name", "")).strip()
            node_id = str(payload.get("node_id", "")).strip()

            if not VALID_IDENTIFIER.match(node_id) or not VALID_IDENTIFIER.match(node_name):
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Node ID and Node Name must be 3-64 alphanumeric characters"}).encode("utf-8"))
                return

            config_dir = Path("/etc/nextgen-mc")
            try:
                config_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

            env_lines = [
                f"NODE_ROLE={node_role}",
                f"NODE_NAME={node_name}",
                f"NODE_ID={node_id}",
                "MASTER_PORT=8005",
                "PORT=8005"
            ]

            if node_role == "worker":
                tier = payload.get("hardware_tier", "standard_ssd")
                endpoint = payload.get("master_endpoint", "http://localhost:8005")
                token = payload.get("cluster_token", "")
                env_lines.extend([
                    f"MASTER_ENDPOINT={endpoint}",
                    f"CLUSTER_TOKEN={token}",
                    f"HARDWARE_TIER={tier}"
                ])
            else:
                admin_email = payload.get("admin_email", "admin@domain.com")
                master_secret = payload.get("master_secret", "master-secret")
                google_client_id = payload.get("google_client_id", "")
                google_client_secret = payload.get("google_client_secret", "")
                local_llm_url = payload.get("local_llm_url", "http://localhost:8000/v1/chat/completions")
                local_llm_model = payload.get("local_llm_model", "qwen-2.5-32b-instruct")

                env_lines.extend([
                    f"ADMIN_EMAIL={admin_email}",
                    f"MASTER_SECRET={master_secret}",
                    f"GOOGLE_CLIENT_ID={google_client_id}",
                    f"GOOGLE_CLIENT_SECRET={google_client_secret}",
                    f"LOCAL_LLM_URL={local_llm_url}",
                    f"LOCAL_LLM_MODEL={local_llm_model}"
                ])

            env_content = "\n".join(env_lines) + "\n"
            target_env = config_dir / "node.env"
            try:
                with open(target_env, "w", encoding="utf-8") as f:
                    f.write(env_content)
            except Exception:
                with open("./node.env", "w", encoding="utf-8") as f:
                    f.write(env_content)

            service_name = "mc-worker" if node_role == "worker" else "mc-master"
            resp_payload = {
                "status": "success",
                "message": f"[{node_role.upper()}] 노드 구성이 완료되었습니다. 포트 8005에서 '{service_name}' 서비스가 활성화됩니다."
            }
            resp_bytes = json.dumps(resp_payload, ensure_ascii=False).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)

            def activate_systemd():
                time.sleep(1.5)
                subprocess.run(["systemctl", "daemon-reload"], check=False)
                subprocess.run(["systemctl", "enable", "--now", service_name], check=False)
                print(f"[Wizard] Activated {service_name} on port 8005. Shutting down wizard server.")
                os._exit(0)

            import threading
            threading.Thread(target=activate_systemd, daemon=True).start()
        else:
            self.send_error(404, "Not Found")

def find_available_port(start_port=8080, max_attempts=10):
    for p in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("0.0.0.0", p)) != 0:
                return p
    return start_port

def run():
    requested_port = int(os.getenv("WIZARD_PORT", "8080"))
    port = find_available_port(requested_port)
    server = HTTPServer(("0.0.0.0", port), SetupWizardHandler)
    server_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        server_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    print("=" * 65)
    print(f"🚀 NextGen MC Platform Web Setup Wizard is running!")
    print(f"👉 External Access URL: http://{server_ip}:{port}")
    print(f"👉 Localhost Access URL: http://localhost:{port}")
    print("=" * 65)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    run()
