# NeoMinecraftservermanager

클라우드 네이티브 환경(Docker cgroups v2), 실시간 종량제 과금, 다층(Tiered) ZRAM/NVMe 메모리 방어 시스템, 통합 모드팩 임포터, 그리고 로컬 LLM 추론 기반 AI 렉 진단 파이프라인을 갖춘 엔터프라이즈급 마인크래프트 호스팅 플랫폼입니다.

---

## 📁 프로젝트 디렉토리 구조

```text
NeoMinecraftservermanager/
├── install.sh                                # 단일 실행 원클릭 설치 및 위저드 런처
├── setup-wizard/                             # 웹 기반 초기 설정 위저드
│   ├── main.go                               # 경량 Go 웹 서버 (포트 8080)
│   ├── static/index.html                     # 모던 Glassmorphism UI
│   └── service_templates/                    # systemd 유닛 템플릿
│       ├── mc-master.service
│       └── mc-worker.service
├── security/                                 # 보안 및 격리 프로필
│   ├── apparmor/minecraft-secure.profile     # AppArmor 시스템콜/경로 격리
│   ├── seccomp/minecraft-seccomp.json        # Seccomp 화이트리스트 필터
│   └── rootless-docker-setup.sh              # Rootless Docker & 권한 분리
├── scripts/                                  # 시스템 및 컨테이너 프로비저닝
│   ├── provision-zram-tier.sh                # Tier 2 ZRAM + Tier 3 NVMe Swap 구성
│   └── deploy-mc-sandbox.sh                  # Sandboxed Docker Container 배포기 (Gen-ZGC)
├── backend/                                  # Master 노드 제어 평면 (FastAPI)
│   ├── app/
│   │   ├── main.py                           # API 엔트리포인트 및 라이프사이클
│   │   ├── core/
│   │   │   ├── config.py                     # 환경 설정
│   │   │   ├── security.py                   # RCON/SSRF 방어, Path Traversal, JWT
│   │   │   └── database.py                   # Postgres/Redis 연결 풀
│   │   ├── models/
│   │   │   └── schema.py                     # Pydantic v2 데이터 모델 (19세 인증 포함)
│   │   ├── services/
│   │   │   ├── billing_engine.py             # 1분 텔레메트리 & 차등 과금 & RCON Shutdown
│   │   │   ├── node_scheduler.py             # 자원 가용성 체크 & Least-Loaded 스케줄러
│   │   │   ├── modpack_importer.py           # Modrinth/CurseForge Zip Slip 방어 파서
│   │   │   └── ai_profiler.py                # Spark 프로파일러 로컬 LLM 분석기
│   │   └── api/
│   │       ├── v1/
│   │       │   ├── auth.py                   # Google OAuth & 19세 성인인증
│   │       │   ├── nodes.py                  # Worker 헬스체크 및 어드민 뷰
│   │       │   ├── servers.py                # 마인크래프트 서버 라이프사이클 & RCON
│   │       │   └── modpacks.py               # 모드팩 임포트 및 검색
│   │       └── routes.py
│   └── requirements.txt
├── worker/                                   # Worker 노드 데이터 평면
│   ├── agent.py                              # Host/ZRAM 메트릭 수집 데몬
│   └── requirements.txt
└── tests/
    └── test_platform.py                      # 보안, 스케줄러, 과금 자동화 테스트
```

---

## 🚀 빠른 시작 (Deployment)

### 옵션 1: 단일 명령어로 배포 및 셋업 위저드 자동 실행
가장 빠르게 시스템을 구축하는 방법입니다. 아래 명령어를 실행하여 공식 저장소에서 설치 스크립트를 다운로드하고 즉시 실행합니다.
```bash
curl -sSL https://raw.githubusercontent.com/gohefd321/NeoMinecraftservermanager/refs/heads/main/install.sh | sudo bash
```

### 옵션 2: Git 저장소 클론을 통한 수동 설치
코드를 직접 확인하거나 수정 후 배포하려면 Git을 통해 저장소를 클론합니다.
```bash
git clone https://github.com/gohefd321/NeoMinecraftservermanager.git
cd NeoMinecraftservermanager
sudo bash install.sh
```

### 3. 웹 브라우저에서 초기 위저드 완료
설치 스크립트 실행 후 브라우저를 열고 `http://<HOST_IP>:8080`에 접속하여 노드 역할(Master / Worker) 및 파라미터를 입력합니다. 설정 완료 즉시 systemd 백그라운드 서비스로 등록되어 자동 실행됩니다.

---

## 🛡️ 핵심 기능 및 보안 아키텍처

### 1. 다층(Tiered) 메모리 및 OOM 방어
- **Tier 1 (RAM)**: 물리 할당 메모리 (컨테이너당 `--memory=4096m`).
- **Tier 2 (ZRAM)**: Host OS 커널에 LZ4 압축 알고리즘 적용 (우선순위 `32767`).
- **Tier 3 (NVMe Swap)**: ZRAM 고갈 시 NVMe 스왑으로 롤오버 (우선순위 `10`).
- **JVM 튜닝**: Java 21 Generational ZGC (`-XX:+UseZGC -XX:+ZGenerational`) 및 Aikar's Flags 자동 주입.

### 2. 원격 코드 실행(RCE) 및 해킹 방어
- **RCON 명령어 살균**: CRLF (`\r\n`), 세미콜론, 백틱, 쉘 파이프라인 인젝션 차단 및 허용 명령어 화이트리스트 검증.
- **SSRF 방어**: 모드팩 및 웹훅 URL 호출 시 RFC 1918 사설 IP 및 클라우드 메타데이터(169.254.169.254) 접근 차단.
- **Zip Slip 방어**: `.mrpack` 및 `manifest.json` 임포트 시 `../` 경로 탈출 시도 원천 차단.
- **도커 샌드박싱**: `cap-drop=ALL`, `--security-opt no-new-privileges:true`, AppArmor 및 Seccomp 프로파일 결합.

### 3. 실시간 종량제 과금 & 노드 차등 배율
- **1분 단위 메트릭**: `Loaded Chunks` 및 `Active Players` 기반 실시간 요율 연산.
- **하드웨어 티어별 배율**:
  - Standard SSD: `1.0x`
  - High NVMe: `1.3x`
  - Extreme Dedicated: `1.8x`
- **초고속 인메모리 차감**: Redis Lua Script로 원자적 차감 후 10분 주기 PostgreSQL 배치 동기화.
- **Graceful Shutdown**: 잔여 크레딧 0원 도달 시 인게임 경고 타이머 -> `save-all` -> `stop` 순서로 데이터 유실 없는 안전 종료.

### 4. 로컬 추론 기반 AI 렉 진단 파이프라인
- 서버 TPS 저하 시 Spark Profiler 요약 데이터를 로컬 LLM(TabbyAPI / Llama-server)에 전달.
- 병목 원인(엔티티 밀집, GC 지연, 모드 루프 등)을 인간의 언어로 진단하고 관리자 헬프데스크 티켓과 연동.

---

## 🧪 자동화 테스트 검증
```bash
python3 -m pytest tests/test_platform.py -v
```
모든 보안 살균, SSRF 차단, Path Traversal 방어, 노드 스케줄러 임계치, 과금 공식, 클라이언트 모드 필터링 테스트가 100% 통과합니다.
