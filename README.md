# Next-Gen Cloud-Native Minecraft Hosting Platform

클라우드 네이티브(Docker cgroups v2), 실시간 종량제 과금(Pay-as-you-go), 다층(Tiered) ZRAM/NVMe 메모리 방어 시스템, 통합 모드팩 임포터, 그리고 로컬 LLM 기반 AI 렉 진단 파이프라인을 갖춘 엔터프라이즈급 마인크래프트 호스팅 플랫폼입니다.

---

## 🌐 포트 및 서비스 엔드포인트 명세표

기존 로컬 AI 추론 서버(`llama-server` :8000) 및 웹 프론트엔드(:3000)와의 충돌을 원천 방지하기 위해 **Master Control Plane 포트가 `8005`로 격리 배정**되었습니다.

| 포트 (Port) | 프로토콜 | 서비스 / 역할 | 접속 URL 및 엔드포인트 | 설명 |
| :--- | :---: | :--- | :--- | :--- |
| **`8005`** | TCP | **일반 유저 공식 포털** | `http://<Master-IP>:8005/` | 회원가입, 구글 1초 로그인, **19세 성인인증**, 서버 생성, 크레딧 지갑, 웹 RCON |
| **`8005`** | TCP | **어드민 통합 제어 센터** | `http://<Master-IP>:8005/admin` | 과금 티어 단가 동적 수정, 회원 관리, **민원 처리**, 어드민 직속 서버 배포, Google/LLM 설정 |
| **`8005`** | TCP | **API 명세서 (Swagger)** | `http://<Master-IP>:8005/docs` | REST API 인터랙티브 테스트 및 문서 |
| **`8080`** *(또는 8081)* | TCP | **Setup Wizard** | `http://<Host-IP>:8080` | 초기 인프라 셋업 위저드 (Google OAuth 키, 로컬 LLM 설정) |
| **`25565`** | TCP | **Velocity Ingress (Java)** | `id.domain.com` *(포트 입력 불필요)* | L4 프록시. Master의 Redis 라우팅 맵을 읽어 실제 워커 포트로 동적 포워딩 |
| **`19132`** | UDP | **Bedrock Ingress** | `id.domain.com:19132` | Geyser / Floodgate 크로스플레이 Bedrock UDP 라우팅 |
| **`25565-25999`** | TCP | **Game Container Ports** | 워커 내부 바인딩 | 실제 도커 격리 마인크래프트 서버 컨테이너 포트 대역 |
| **`25575-25999`** | TCP | **RCON Ports** | 내부 RCON 제어 | 콘솔 명령어 살균 실행 및 Graceful Shutdown용 |

---

## 🚀 설치 및 관리 스크립트 사용법 (`install.sh`)

단일 스크립트로 설치, 업데이트, 100% 완전 파괴적 클린 재설치, 서비스 복구를 모두 처리할 수 있습니다.

### 1. 원격 원클릭 설치 (One-Line Installer)
GitHub 원격 저장소에서 최신 `install.sh`를 즉시 내려받아 실행합니다:

```bash
# 원격 단일 명령 실행 (One-Line Fast Install)
curl -sSL https://github.com/gohefd321/NeoMinecraftservermanager/raw/refs/heads/main/install.sh | sudo bash
```

또는 스크립트 파일을 직접 다운로드한 후 실행:

```bash
# 스크립트 다운로드 후 실행
curl -fsSL https://github.com/gohefd321/NeoMinecraftservermanager/raw/refs/heads/main/install.sh -o install.sh
sudo bash install.sh
```

---

### 2. 옵션별 원클릭 실행 (CLI Flags)
- **⚠️ 100% 완전 파괴적 클린 재설치 (Nuclear Wipe & Fresh Reinstall)**:
  모든 마인크래프트 컨테이너, 월드 데이터, 설정, Python 캐시를 영구 삭제하고 0% 캐시 상태에서 완전히 새로 시작합니다.
  ```bash
  sudo ./install.sh --wipe
  ```
- **업데이트 및 재시작 (Update & Restart)**:
  기존 설정과 월드 데이터를 100% 보존하면서 최신 코드와 디펜던시를 갱신하고 서비스를 재기동합니다.
  ```bash
  sudo ./install.sh --update
  ```
- **의존성·방화벽·서비스 즉시 복구 (Repair & Fix)**:
  누락된 Python 패키지(`uvicorn`, `fastapi` 등)를 강제 설치하고, 방화벽 포트를 개방한 후 Master 서비스를 복구합니다.
  ```bash
  sudo ./install.sh --repair
  ```

---

## 🛡️ 방화벽 수동 설정 가이드 (Firewall Guide)

`install.sh` 실행 시 방화벽이 자동으로 감지 및 개방되지만, 수동으로 확인하거나 개방할 경우 아래 명령어를 사용하십시오.

### UFW (Ubuntu / Debian)
```bash
sudo ufw allow 8005/tcp comment "NextGen Master API"
sudo ufw allow 8080:8085/tcp comment "Setup Wizard"
sudo ufw allow 25565:25999/tcp comment "Minecraft Java & Containers"
sudo ufw allow 19132/udp comment "Minecraft Bedrock UDP"
sudo ufw reload
```

### Firewalld (RHEL / CentOS / Rocky / Alma / Fedora)
```bash
sudo firewall-cmd --permanent --add-port=8005/tcp
sudo firewall-cmd --permanent --add-port=8080-8085/tcp
sudo firewall-cmd --permanent --add-port=25565-25999/tcp
sudo firewall-cmd --permanent --add-port=19132/udp
sudo firewall-cmd --reload
```
