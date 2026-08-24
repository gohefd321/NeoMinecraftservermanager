# Next-Gen Cloud-Native Minecraft Hosting Platform

클라우드 네이티브(Docker cgroups v2), 실시간 종량제 과금(Pay-as-you-go), 다층(Tiered) ZRAM/NVMe 메모리 방어 시스템, 통합 모드팩 임포터, 그리고 로컬 LLM 기반 AI 렉 진단 파이프라인을 갖춘 엔터프라이즈급 마인크래프트 호스팅 플랫폼입니다.

---

## 🌐 포트 및 서비스 엔드포인트 명세표

기존 로컬 AI 추론 서버(`llama-server` :8000) 및 웹 프론트엔드(:3000)와의 충돌을 원천 방지하기 위해 **Master Control Plane 포트가 `8005`로 격리 배정**되었습니다.

| 포트 (Port) | 프로토콜 | 서비스 / 역할 | 접속 URL 및 엔드포인트 | 설명 |
| :--- | :---: | :--- | :--- | :--- |
| **`8005`** | TCP | **Master Control Plane** | `http://<Master-IP>:8005/admin`<br>`http://<Master-IP>:8005/docs` | 중앙 API, **어드민 실시간 과금/노드 제어 대시보드**, 사용자 회원가입 |
| **`8080`** *(또는 8081)* | TCP | **Setup Wizard** | `http://<Host-IP>:8080` | 초기 인프라 셋업 위저드 (설정 완료 시 자동 종료) |
| **`25565`** | TCP | **Velocity Ingress (Java)** | `id.domain.com` *(포트 입력 불필요)* | L4 프록시. Master의 Redis 라우팅 맵을 읽어 실제 워커 포트로 동적 포워딩 |
| **`19132`** | UDP | **Bedrock Ingress** | `id.domain.com:19132` | Geyser / Floodgate 크로스플레이 Bedrock UDP 라우팅 |
| **`25565-25999`** | TCP | **Game Container Ports** | 워커 내부 바인딩 | 실제 도커 격리 마인크래프트 서버 컨테이너 포트 대역 |
| **`25575-25999`** | TCP | **RCON Ports** | 내부 RCON 제어 | 콘솔 명령어 살균 실행 및 Graceful Shutdown용 |
| **`6379`** | TCP | **Redis Cluster** | `localhost:6379` | 라우팅 맵, 1분 텔레메트리 큐, 실시간 인메모리 지갑 원장 |
| **`5432`** | TCP | **PostgreSQL** | `localhost:5432` | 10분 주기 배치 영구 장부, 유저 성인인증, 서버 설정, 티켓 |

---

## 🚀 설치 및 관리 스크립트 사용법 (`install.sh`)

단일 스크립트로 설치, 업데이트, 완전 삭제 후 재설치, 서비스 복구를 모두 처리할 수 있습니다.

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

### 2. 로컬 설치 및 대화형 메뉴 실행
로컬 클론 디렉토리에서 직접 실행하는 경우:

```bash
sudo bash /home/bettercallsixseven/nextgen-mc-platform/install.sh
```

---

### 3. 옵션별 원클릭 실행 (CLI Flags)
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
- **완전 삭제 후 클린 재설치 (Clean Reinstall)**:
  기존 컨테이너 및 설정을 깨끗하게 초기화하고 처음부터 새로 배포합니다.
  ```bash
  sudo ./install.sh --clean
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

---

## 🖥️ 어드민 대시보드 (`/admin`) 사용법

브라우저에서 **`http://<Master-IP>:8005/admin`** 에 접속합니다.

1. **실시간 종량제 요율 동적 변경**:
   - **기본 유지비**: 컨테이너 분당 기본 비용 (기본값: `0.50`원/분)
   - **청크당 요율**: 로드된 활성 청크 1개당 요율 (기본값: `0.0010`원/청크/분)
   - **플레이어당 요율**: 동시 접속자 1인당 요율 (기본값: `0.1000`원/명/분)
   - **하드웨어 티어 배율**: Standard SSD(`1.0x`), High NVMe(`1.3x`), Extreme Dedicated(`1.8x`)
   - 폼 입력 후 `과금 요율 즉시 저장`을 누르면 **실시간 텔레메트리 차감 연산에 즉시 100% 반영**됩니다.

2. **Master-as-Worker (마스터 노드 컨테이너 구동)**:
   - 마스터 노드 자체가 `MASTER+CONTAINER` 카드로 등록되어 있어, 별도의 워커 노드가 없는 단일 서버에서도 마스터 노드에서 직접 안전한 AppArmor 샌드박스 컨테이너가 배포 및 구동됩니다.
   - 개별 노드 카드의 `배율 수정` 버튼을 눌러 특정 노드의 과금 배율만 즉석 변경할 수 있습니다.

---

## ⚙️ 서비스 상태 제어 및 트러블슈팅

```bash
# Master 서비스 상태 확인
sudo systemctl status mc-master

# Master 서비스 재시작
sudo systemctl restart mc-master

# 실시간 로그 확인
sudo journalctl -u mc-master -f -n 50

# API 헬스체크
curl http://localhost:8005/health
```
