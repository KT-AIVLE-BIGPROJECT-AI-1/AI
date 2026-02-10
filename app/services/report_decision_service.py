# app/services/report_decision_service.py

import json
from datetime import datetime
from openai import OpenAI
from app.config import settings
from app.models.report_decision_schema import (
    ReportDecisionRequest,
    ReportDecisionResponse
)
from app.services.report_storage_service import ReportStorageService

client = OpenAI(api_key=settings.OPENAI_API_KEY)

# 결정 유형 한글 변환 맵 (전역)
DECISION_MAP = {
    "TRANSFER": "송치",
    "NON_TRANSFER": "불송치",
    "SUSPENSION": "수사중지"
}


class ReportDecisionService:
    """
    수사 결정서 생성 서비스 (송치/불송치/수사중지)
    
    사용자가 선택한 decision_type을 기준으로 결정서 작성
    (AI 추천과 다를 수 있음)
    """
    
    @staticmethod
    def generate_decision_report(request: ReportDecisionRequest) -> ReportDecisionResponse:
        """
        수사 결정서 생성 + 내부 저장
        """
        # 한글 변환
        user_decision_kr = DECISION_MAP.get(request.decision_type, request.decision_type)
        ai_decision_kr = DECISION_MAP.get(
            request.final_analysis.recommended_decision,
            request.final_analysis.recommended_decision
        )
        
        print("\n" + "=" * 70)
        print("⚖️ 수사 결정서 생성")
        print("=" * 70)
        print(f"사건: {request.case_detail.title}")
        print(f"사용자 판단: {user_decision_kr}")
        print(f"AI 추천: {ai_decision_kr}")
        
        # 판단 일치 여부 확인
        is_different = (request.decision_type != request.final_analysis.recommended_decision)
        if is_different:
            print(f"⚠️ 사용자 판단과 AI 추천이 다릅니다!")
        
        # 프롬프트 구성
        prompt = ReportDecisionService._build_prompt(request, is_different, user_decision_kr, ai_decision_kr)
        
        # GPT-4o로 결정서 생성
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "당신은 경찰 수사 결정서 작성 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2500
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # JSON 파싱
            import re
            result_text = re.sub(r"```json|```", "", result_text).strip()
            result = json.loads(result_text)
            
            title = result.get("title", "")
            content = result.get("content", {})
            
            # 영문 enum이 남아있으면 한글로 치환
            content = ReportDecisionService._replace_english_decisions(content)
            
            # 내부 저장 (PDF 등)
            ReportStorageService.save_report(
                report_type="DECISION",
                case_id=request.final_analysis.case_id,
                title=title,
                content=content
            )
            
            print("=" * 70)
            print(f"✅ 수사 결정서 생성 완료")
            print("=" * 70)
            
            return ReportDecisionResponse(
                title=title,
                content=content
            )
        
        except Exception as e:
            print(f"⚠️ 수사 결정서 생성 실패: {e}")
            
            return ReportDecisionResponse(
                title=f"{request.case_detail.title} {user_decision_kr} 결정서",
                content={
                    "error": f"자동 생성 실패: {str(e)}",
                    "manual_required": "true"
                }
            )
    
    @staticmethod
    def _replace_english_decisions(content: dict) -> dict:
        """
        content 내의 모든 문자열에서 영문 결정 유형을 한글로 치환
        TRANSFER → 송치, NON_TRANSFER → 불송치, SUSPENSION → 수사중지
        """
        def replace_in_value(value):
            if isinstance(value, str):
                for eng, kor in DECISION_MAP.items():
                    value = value.replace(eng, kor)
                return value
            elif isinstance(value, dict):
                return {k: replace_in_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [replace_in_value(v) for v in value]
            return value
        
        return replace_in_value(content)
    
    @staticmethod
    def _build_prompt(
        request: ReportDecisionRequest,
        is_different: bool,
        user_decision_kr: str,
        ai_decision_kr: str
    ) -> str:
        """수사 결정서 생성 프롬프트 구성"""
        
        # 판단 불일치 시 추가 안내
        decision_note = ""
        if is_different:
            decision_note = f"""
**중요: 사용자 판단과 AI 추천 불일치**
- AI 추천: {ai_decision_kr}
- 사용자 판단: {user_decision_kr} ← 이것을 기준으로 작성
- 결정서에 판단 변경 사유를 포함하십시오.
"""
        
        prompt = f"""다음 정보를 바탕으로 수사 결정서를 작성하십시오.

**중요 규칙:**
- 영문 코드(TRANSFER, NON_TRANSFER, SUSPENSION)를 절대 사용하지 마십시오.
- 반드시 한글(송치, 불송치, 수사중지)만 사용하십시오.

**사건 정보:**
사건명: {request.case_detail.title}
사건유형: {request.case_detail.type}
사건상태: {request.case_detail.status}
발생일시: {request.case_detail.occurred_at}
발생장소: {request.case_detail.location}
사건개요: {request.case_detail.description}

**사건 요약:**
{json.dumps(request.case_detail.summary.model_dump(), ensure_ascii=False, indent=2)}

**최종 판단:**
사용자 결정: {user_decision_kr}

{decision_note}

**분석 결과 (참고):**
사건 판단 요약:
{request.final_analysis.decision_summary}

법리 판단 요약:
{request.final_analysis.legal_issue_summary}

증거 충분성 요약:
{request.final_analysis.evidence_sufficiency_summary}

잔여 리스크 요약:
{request.final_analysis.remaining_risk_summary}

**출력 형식 (JSON만 출력):**
{{
  "title": "{user_decision_kr} 결정서",
  "content": {{
    "case_name": "{request.case_detail.title}",
    "suspect": "미상",
    
    "ruling": "{user_decision_kr} 결정함",
    
    "case_overview": {{
      "occurred_at": "{request.case_detail.occurred_at}",
      "location": "{request.case_detail.location}",
      "case_details": "사건 요약 내용을 서술형으로 재구성 (5-7문장)"
    }},
    
    "judgment_reason": {{
      "key_judgment": "{user_decision_kr} 결정의 핵심 근거 (3-5문장)",
      "detailed_reason": "구체적인 판단 이유 (7-10문장)",
      {'"change_reason": "AI 추천과 다른 이유 (해당시에만)"' if is_different else ''}
    }},
    
    "evidence_evaluation": {{
      "collected_evidence": "증거 목록 및 내용",
      "evidence_value": "각 증거의 증명력 평가",
      "overall_evaluation": "증거 충분성에 대한 최종 판단"
    }},
    
    "legal_review": {{
      "applicable_law": "관련 법률 조항",
      "elements": "범죄 구성요건 충족 여부",
      "legal_judgment": "법적 판단 근거 및 결론"
    }},
    
    "conclusion": {{
      "final_opinion": "{user_decision_kr}",
      "follow_up": "후속 조치 또는 유의사항",
      "remarks": "기타 참고사항"
    }}
  }}
}}

**작성 원칙:**
- 사용자 판단({user_decision_kr})을 확고히 뒷받침하는 논리 전개
- 공문서 형식 및 법률 용어 정확히 사용
- 객관적이고 설득력 있는 근거 제시
- 판단과 근거의 명확한 연결
- 영문 코드가 아닌 한글(송치/불송치/수사중지)만 사용할 것
{f"- AI 추천({ai_decision_kr})과 다른 이유를 명확히 설명" if is_different else ""}
"""
        
        return prompt