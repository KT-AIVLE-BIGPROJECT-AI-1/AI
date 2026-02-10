# app/services/case_service.py

import json
import uuid
from datetime import datetime, timezone
from openai import OpenAI
from app.config import settings
from app.models.case_schema import CaseRequest, CaseResponse, CaseSummary, CaseSummaryResponse

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def utc_now_iso() -> str:
    """현재 UTC 시간을 ISO 8601 형식으로 반환"""
    return datetime.now(timezone.utc).isoformat()


class CaseService:
    @staticmethod
    def generate_case_summary(case_description: str) -> dict:
        """
        사건 내용을 6가지 요소로 구조화
        AI.ipynb의 generate_case_summary() 함수 이식
        """
        system_prompt = """당신은 사건 분석 전문가입니다.

입력된 사건 내용을 다음 6가지 요소로 구조화하십시오:

1. action: 행위 (예: 강탈, 절도, 폭행)
2. object: 대상/객체 (예: 스마트폰, 현금, 귀금속)
3. interaction: 상호작용 방식 (예: 물리적 접촉, 대면, 비대면, 협박)
4. place: 장소 (예: 서울시 주택가 골목길)
5. time: 시간 (예: 낮 시간대, 오후 2시경, 야간)
6. result: 결과 (예: 물품 탈취 성공, 도주, 미수)

각 항목은 간결하게 핵심만 추출하십시오."""

        schema = {
            "name": "case_summary",
            "schema": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "object": {"type": "string"},
                    "interaction": {"type": "string"},
                    "place": {"type": "string"},
                    "time": {"type": "string"},
                    "result": {"type": "string"}
                },
                "required": ["action", "object", "interaction", "place", "time", "result"]
            }
        }

        try:
            response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"사건 내용:\n{case_description}"}
                ],
                temperature=0.3,
                response_format={"type": "json_schema", "json_schema": schema}
            )

            summary = json.loads(response.choices[0].message.content)
            return summary

        except Exception as e:
            print(f"⚠️ Summary 생성 실패: {e}")
            return {
                "action": "",
                "object": "",
                "interaction": "",
                "place": "",
                "time": "",
                "result": ""
            }

    @staticmethod
    def create_case(request: CaseRequest) -> CaseSummaryResponse:
        """
        CASE Summary 생성
        사건 내용을 받아 6가지 요소로 구조화된 summary 반환
        """
        # Summary 생성
        summary_dict = CaseService.generate_case_summary(request.description)
        
        print("\n" + "=" * 70)
        print("📋 CASE Summary 생성 (API 명세서 준수)")
        print("=" * 70)
        print(f"\n[API 응답]\n{json.dumps(summary_dict, ensure_ascii=False, indent=2)}")
        print("\n" + "=" * 70)
        print("✅ CASE Summary 생성 완료")
        print("=" * 70)
        
        return CaseSummaryResponse(
            summary=CaseSummary(**summary_dict)
        )