# app/services/report_decision_service.py
# ✅ 공문서체 3인칭 과거 시제(~함, ~였음) 어투 프롬프트 적용
# ✅ 결정서 유형별 필수 항목:
#    송치/불송치: 범죄사실 특정, 적용 법조, 구성요건 해당성, 위법성·책임성 판단, 증거 요지 및 판단 이유
#    수사중지: 중지 사유 + 법적 근거

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


# ============================================================
# 공통 문체 지시
# ============================================================

WRITING_STYLE_DIRECTIVE = """
**[문체 규칙 — 반드시 준수]**
1. 공문서체 3인칭 과거 시제로 작성할 것.
   - 문장 끝: ~함, ~였음, ~하였음, ~됨, ~확인됨, ~판단됨
   - 예시: "피의자는 ~한 사실이 확인됨", "위 범죄사실은 ~에 의하여 인정됨"
   - 금지: ~합니다, ~입니다, ~했습니다, ~됩니다 (경어체 금지)
   - 금지: ~한다, ~이다, ~했다 (평서체 금지)
2. 객관적 사실과 증거 중심으로 서술할 것.
   - 주관적 추측, 감정적 표현 배제
   - "~한 것으로 보임", "~한 것으로 판단됨" 등 객관적 추정 표현 사용
3. 전문 법률·수사 용어를 정확히 사용할 것.
4. **[환각 방지]** 입력된 사건 정보와 분석 결과에 없는 내용을 절대로 생성하지 마십시오.
   - 제공된 데이터에서 확인할 수 없는 증거, 인물, 사실을 추가하지 말 것
   - 추측이나 가정에 의한 내용 서술 금지
"""


# ============================================================
# 결정서 유형별 필수 항목 지시
# ============================================================

TRANSFER_REQUIREMENTS = """
**[송치 결정서 필수 포함 항목]**
1. 범죄사실 특정: 일시, 장소, 방법, 결과를 구체적으로 기재
2. 적용 법조: 관련 법률 조항을 조문 단위로 명시 (예: 형법 제257조 제1항)
3. 구성요건 해당성: 객관적·주관적 구성요건별 충족 여부를 구체적으로 서술
4. 위법성·책임성 판단: 위법성조각사유(정당방위, 긴급피난 등) 해당 여부, 책임조각사유(심신장애 등) 해당 여부를 검토
5. 증거 요지: 범죄사실을 뒷받침하는 증거를 열거하고 각 증거의 증명력을 평가
6. 판단 이유: 위 검토 결과를 종합하여 송치가 상당한 이유를 논리적으로 서술
"""

NON_TRANSFER_REQUIREMENTS = """
**[불송치 결정서 필수 포함 항목]**
1. 범죄사실(피의사실) 특정: 일시, 장소, 방법, 결과를 구체적으로 기재
2. 적용 법조: 관련 법률 조항을 조문 단위로 명시
3. 구성요건 해당성: 구성요건 미충족 부분을 구체적으로 서술
4. 위법성·책임성 판단: 위법성조각사유 또는 책임조각사유 해당 여부를 검토
5. 증거 요지: 수집된 증거를 열거하고, 범죄사실 입증에 부족한 부분을 구체적으로 평가
6. 판단 이유: 위 검토 결과를 종합하여 불송치가 상당한 이유를 논리적으로 서술
   (혐의없음/죄가안됨/공소권없음 등 불송치 사유를 명시)
"""

SUSPENSION_REQUIREMENTS = """
**[수사중지 결정서 필수 포함 항목]**
1. 피의사실: 일시, 장소, 방법, 결과를 구체적으로 기재
2. 수사 경과: 그간의 수사 활동 내역을 시간순으로 서술
3. 중지 사유: 수사중지의 구체적 사유를 명시
   (예: 피의자 소재불명, 참고인 소재불명, 증거 확보 곤란 등)
4. 법적 근거: 수사중지의 법적 근거를 명시
   (예: 검사의 사건사무규칙 제69조, 경찰수사규칙 관련 조항 등)
5. 향후 조치: 수사 재개 조건 또는 추가 수사 가능 사항을 서술
"""


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
                model="gpt-4.1",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"당신은 경찰 수사 결정서({user_decision_kr} 결정서) 작성 전문가입니다.\n"
                            "모든 문장을 공문서체 3인칭 과거 시제(~함, ~였음, ~확인됨, ~판단됨)로 작성합니다.\n"
                            "객관적 사실과 증거 중심으로 서술하며, 범죄사실 특정·적용 법조·구성요건 해당성·"
                            "위법성 및 책임성 판단·증거 요지·판단 이유를 반드시 포함합니다.\n"
                            "경어체(~합니다)나 평서체(~한다)는 사용하지 않습니다."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=3000
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
            
            # 내부 저장 (PDF 등) — decision_type 전달하여 양식 분기
            ReportStorageService.save_report(
                report_type="DECISION",
                case_id=request.final_analysis.case_id,
                title=title,
                content=content,
                decision_type=request.decision_type
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
    def _get_type_requirements(decision_type: str) -> str:
        """결정서 유형별 필수 항목 지시문 반환"""
        if decision_type == "TRANSFER":
            return TRANSFER_REQUIREMENTS
        elif decision_type == "NON_TRANSFER":
            return NON_TRANSFER_REQUIREMENTS
        elif decision_type == "SUSPENSION":
            return SUSPENSION_REQUIREMENTS
        return TRANSFER_REQUIREMENTS  # 기본값
    
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
        
        # 결정서 유형별 필수 항목
        type_requirements = ReportDecisionService._get_type_requirements(request.decision_type)
        
        # 수사중지인 경우 출력 형식이 다름
        if request.decision_type == "SUSPENSION":
            output_format = f"""{{
  "title": "수사중지 결정서",
  "content": {{
    "case_name": "{request.case_detail.title}",
    "suspect": "피의자 성명 (사건 정보에서 파악된 경우 기재, 파악할 수 없으면 null)",
    "charge": "죄명 (적용 법조 기반으로 기재, 반드시 포함할 것)",
    
    "ruling": "피의자에 대하여 수사중지 결정함 (구체적 사유를 포함하여 서술)",
    
    "case_overview": {{
      "occurred_at": "{request.case_detail.occurred_at}",
      "location": "{request.case_detail.location}",
      "case_details": "피의사실을 일시·장소·방법·결과를 특정하여 구체적으로 서술 (5-7문장, ~함/~였음)"
    }},
    
    "judgement_reason": {{
      "key_judgement": "수사중지 결정의 핵심 근거를 서술 (3-5문장, ~함/~였음)",
      "detailed_reason": "수사 경과·중지 사유·법적 근거를 종합한 구체적 판단 이유를 서술 (7-10문장, ~함/~였음)",
      {'"change_reason": "AI 추천과 다른 이유를 구체적으로 서술 (~함/~였음)"' if is_different else ''}
    }},
    
    "evidence_evaluation": {{
      "collected_evidence": "수집된 증거 목록 및 내용을 서술 (~함/~였음)",
      "evidence_value": "각 증거의 증명력 평가를 서술 (~함/~였음)",
      "overall_evaluation": "증거 현황에 대한 종합 평가를 서술 (~함/~였음)"
    }},
    
    "legal_review": {{
      "applicable_law": "관련 법률 조항을 조문 단위로 명시",
      "elements": "구성요건 충족 여부 검토 결과를 서술 (~함/~였음)",
      "overall_judgement": "법적 판단 근거 및 결론을 서술 (~함/~였음)"
    }},
    
    "conclusion": {{
      "final_opinion": "수사중지",
      "follow_up": "수사 재개 시 필요한 조치 사항을 서술 (~함/~였음)",
      "remarks": "기타 참고사항"
    }}
  }}
}}"""
        else:
            # 송치 또는 불송치
            output_format = f"""{{
  "title": "{user_decision_kr} 결정서",
  "content": {{
    "case_name": "{request.case_detail.title}",
    "suspect": "피의자 성명 (사건 정보에서 파악된 경우 기재, 파악할 수 없으면 null)",
    "charge": "죄명 (적용 법조 기반으로 기재, 반드시 포함할 것)",
    
    "ruling": "피의자에 대하여 (사유를 포함하여) {user_decision_kr} 결정함 (예: '증거불충분으로 혐의없음 판단되어 불송치 결정함', '범죄사실이 인정되어 송치 결정함' 등)",
    
    "case_overview": {{
      "occurred_at": "{request.case_detail.occurred_at}",
      "location": "{request.case_detail.location}",
      "case_details": "범죄사실을 일시·장소·방법·결과를 특정하여 구체적으로 서술 (5-7문장, ~함/~였음)"
    }},
    
    "judgement_reason": {{
      "key_judgement": "{user_decision_kr} 결정의 핵심 근거를 서술 (3-5문장, ~함/~였음)",
      "detailed_reason": "범죄사실과 증거를 종합한 구체적 판단 이유를 서술 (7-10문장, ~함/~였음)",
      {'"change_reason": "AI 추천과 다른 이유를 구체적으로 서술 (~함/~였음)"' if is_different else ''}
    }},
    
    "evidence_evaluation": {{
      "collected_evidence": "수집된 각 증거를 열거하고 내용을 서술 (~함/~였음)",
      "evidence_value": "각 증거의 증명력·신빙성·관련성을 구체적으로 평가 (~함/~였음)",
      "overall_evaluation": "증거 충분성에 대한 최종 판단을 서술 (~함/~였음)"
    }},
    
    "legal_review": {{
      "applicable_law": "적용 법조를 조문 단위로 명시 (예: 형법 제257조 제1항)",
      "elements": "각 구성요건(객관적·주관적 구성요건)별 충족 여부를 구체적으로 검토 (~함/~였음)",
      "overall_judgement": "위법성·책임성 판단을 포함한 법적 판단 근거 및 결론을 서술 (~함/~였음)"
    }},
    
    "conclusion": {{
      "final_opinion": "{user_decision_kr}",
      "follow_up": "후속 조치 또는 유의사항을 서술 (~함/~였음)",
      "remarks": "기타 참고사항"
    }}
  }}
}}"""
        
        prompt = f"""다음 정보를 바탕으로 수사 결정서를 작성하십시오.

{WRITING_STYLE_DIRECTIVE}

{type_requirements}

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
{request.final_analysis.legal_issues_summary}

증거 충분성 요약:
{request.final_analysis.evidence_sufficiency_summary}

잔여 리스크 요약:
{request.final_analysis.remaining_risk_summary}

**출력 형식 (반드시 아래 구조의 유효한 단일 JSON 객체만 출력하십시오. 마크다운 코드블록, 설명 텍스트, 주석을 절대 포함하지 마십시오):**
{output_format}

**작성 원칙:**
- 반드시 위 출력 형식의 유효한 단일 JSON 객체만 출력할 것 (마크다운 코드블록, 설명 텍스트, 주석 금지)
- 모든 중괄호를 정확히 열고 닫을 것
- charge(죄명) 필드를 반드시 포함할 것
- 공문서체 3인칭 과거 시제 (~함, ~였음, ~확인됨, ~판단됨)
- 사용자 판단({user_decision_kr})을 확고히 뒷받침하는 논리 전개
- 범죄사실을 일시·장소·방법·결과로 특정하여 기재
- 적용 법조를 조문 단위로 명시
- 각 구성요건의 해당성을 구체적으로 검토
- 위법성·책임성 판단을 명시적으로 포함
- 증거 요지를 열거하고 각 증거의 증명력을 평가
- 객관적이고 설득력 있는 근거 제시
- 경어체(~합니다) 및 평서체(~한다) 절대 금지
- 영문 코드가 아닌 한글(송치/불송치/수사중지)만 사용할 것
{f"- AI 추천({ai_decision_kr})과 다른 이유를 명확히 설명" if is_different else ""}
"""
        
        return prompt