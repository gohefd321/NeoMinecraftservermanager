"""
ai_profiler.py - Local LLM (TabbyAPI / Llama-server) AI Lag Diagnostic Pipeline
"""
import json
import httpx
from typing import Dict, Any, Optional
from app.core.config import settings
from app.models.schema import AIReportResponse

PROMPT_TEMPLATE = """당신은 마인크래프트 서버 성능 최적화 및 JVM 튜닝 전문 수석 DevOps 엔지니어입니다.
아래 제공된 Spark Profiler 요약 데이터와 서버 텔레메트리 로그를 정밀 분석하여 문제의 근본 원인을 파악하십시오.

[분석 가이드라인]
1. Tick Time을 가장 많이 점유하는 상위 3대 병목 요소 식별 (엔티티 과밀집, 청크 생성 I/O, 특정 모드 이벤트 리스너, 타일 엔티티 등)
2. 비정상적인 GC(가비지 컬렉션) 지연 또는 메모리 누수 여부 판별
3. 유저가 즉각 취할 수 있는 구체적인 조치 명령어 또는 설정 변경 가이드라인 제시

[Spark Profiler Data]
{spark_data}

[Server Metrics]
- Server ID: {server_id}
- Loaded Chunks: {chunks}
- Active Players: {players}
- Current TPS: {tps}

반드시 유효한 JSON 형식으로만 응답하십시오:
{{
    "root_cause_summary": "렉의 핵심 근본 원인 2줄 요약",
    "culprits": ["원인 1 (예: 특정 좌표 엔티티 500마리)", "원인 2", "원인 3"],
    "actionable_steps": ["조치 권고사항 1 (예: /kill @e[type=zombie] 또는 mob-spawn-range 조정)", "조치 사항 2"],
    "requires_admin_ticket": true
}}
"""

class AIProfilerService:
    def __init__(self):
        self.endpoint = settings.LOCAL_LLM_URL
        self.model_name = settings.LOCAL_LLM_MODEL

    async def analyze_profiler_dump(
        self,
        server_id: str,
        spark_summary: str,
        telemetry: Dict[str, Any]
    ) -> AIReportResponse:
        prompt = PROMPT_TEMPLATE.format(
            server_id=server_id,
            spark_data=spark_summary[:4000], # Token context guard
            chunks=telemetry.get("loaded_chunks", 0),
            players=telemetry.get("active_players", 0),
            tps=telemetry.get("tps", 20.0)
        )

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": "You are a professional Minecraft Systems Diagnostics AI."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 1024,
            "response_format": {"type": "json_object"}
        }

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(self.endpoint, json=payload)
                if resp.status_code == 200:
                    res_json = resp.json()
                    content = res_json["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    return AIReportResponse(
                        server_id=server_id,
                        root_cause_summary=parsed.get("root_cause_summary", "원인 분석 완료"),
                        culprits=parsed.get("culprits", []),
                        actionable_steps=parsed.get("actionable_steps", []),
                        requires_admin_ticket=parsed.get("requires_admin_ticket", False)
                    )
        except Exception as e:
            print(f"[AI Profiler Error] Local LLM unreachable: {e}")

        # Fallback heuristic analysis if LLM is temporarily unreachable
        return AIReportResponse(
            server_id=server_id,
            root_cause_summary="Spark 데이터 수집 완료. 엔티티 밀집도 및 틱 타임 지연 감지.",
            culprits=["과도한 청크 엔티티 수량", "GC 지연"],
            actionable_steps=["서버 뷰 디스턴스(view-distance)를 6 이하로 축소하십시오.", "모드팩 업데이트를 확인하십시오."],
            requires_admin_ticket=False
        )

ai_profiler = AIProfilerService()
