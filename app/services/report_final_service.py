# app/services/report_final_service.py
# ✅ 공문서체 3인칭 과거 시제(~함, ~였음) 어투 프롬프트 적용
# ✅ 증거 평가 + 법리 검토 포함 지시

import json
from datetime import datetime
from openai import OpenAI
from app.config import settings
from app.models.report_final_schema import (
    ReportFinalRequest,
    ReportFinalResponse
)
from app.services.report_storage_service import ReportStorageService

client = OpenAI(api_key=settings.OPENAI_API_KEY)


# ============================================================
# 공통 문체 지시
# ============================================================

WRITING_STYLE_DIRECTIVE = """
**[문체 규칙 — 반드시 준수]**
1. 공문서체 3인칭 과거 시제로 작성할 것.
   - 문장 끝: ~함, ~였음, ~하였음, ~됨, ~확인됨, ~판단됨
   - 예시: "피의자는 ~한 사실이 확인됨", "수사관이 현장에 임장하여 ~을 확보하였음"
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


class ReportFinalService:
    """
    수사결과보고 생성 서비스
    
    최종 분석 결과를 바탕으로 수사결과보고 작성
    """
    
    @staticmethod
    def generate_final_report(request: ReportFinalRequest) -> ReportFinalResponse:
        """
        수사결과보고 생성 + 내부 저장
        """
        print("\n" + "=" * 70)
        print("📋 수사결과보고 생성")
        print("=" * 70)
        print(f"사건: {request.case_detail.title}")
        print(f"송치의견: {request.final_analysis.recommended_decision}")
        
        # 프롬프트 구성
        prompt = ReportFinalService._build_prompt(request)
        
        # GPT-4o로 보고서 생성
        try:
            response = client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "당신은 경찰 수사결과보고 작성 전문가입니다.\n"
                            "모든 문장을 공문서체 3인칭 과거 시제(~함, ~였음, ~확인됨, ~판단됨)로 작성합니다.\n"
                            "객관적 사실과 증거 중심으로 서술하며, 증거 평가와 법리 검토를 반드시 포함합니다.\n"
                            "경어체(~합니다)나 평서체(~한다)는 사용하지 않습니다."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=2500
            )
            
            result_text = response.choices[0].message.content.strip()
            print("[DEBUG]", result_text)
            
            # JSON 파싱
            import re
            result_text = re.sub(r"```json|```", "", result_text).strip()
            result = json.loads(result_text)
            
            title = result.get("title", "")
            content = result.get("content", {})
            
            # 내부 저장 (PDF 등)
            ReportStorageService.save_report(
                report_type="FINAL",
                case_id=request.final_analysis.case_id,
                title=title,
                content=content
            )
            
            print("=" * 70)
            print(f"✅ 수사결과보고 생성 완료")
            print("=" * 70)
            
            return ReportFinalResponse(
                title=title,
                content=content
            )
        
        except Exception as e:
            print(f"⚠️ 수사결과보고 생성 실패: {e}")
            
            return ReportFinalResponse(
                title=f"{request.case_detail.title} 수사결과보고",
                content={
                    "error": f"자동 생성 실패: {str(e)}",
                    "manual_required": "true"
                }
            )
    
    @staticmethod
    def _build_prompt(request: ReportFinalRequest) -> str:
        """수사결과보고 생성 프롬프트 구성"""
        
        # 송치의견 한글 변환
        decision_map = {
            "TRANSFER": "송치",
            "NON_TRANSFER": "불송치",
            "SUSPENSION": "수사중지"
        }
        decision_kr = decision_map.get(
            request.final_analysis.recommended_decision
        )
        
        prompt = f"""다음 수사 결과를 바탕으로 수사결과보고를 작성하십시오.

{WRITING_STYLE_DIRECTIVE}

**[수사결과보고서 필수 포함 항목]**
- 증거 평가: 수집된 각 증거의 증명력, 신빙성, 관련성을 평가하여 서술할 것
- 법리 검토: 적용 법조를 명시하고, 각 구성요건별 충족 여부를 검토하여 서술할 것

**사건 정보:**
사건번호: {request.case_detail.case_id}
사건명: {request.case_detail.title}
사건유형: {request.case_detail.type}
사건상태: {request.case_detail.status}
발생일시: {request.case_detail.occurred_at}
발생장소: {request.case_detail.location}
사건개요: {request.case_detail.description}

**사건 요약:**
{json.dumps(request.case_detail.summary.model_dump(), ensure_ascii=False, indent=2)}

**최종 분석 결과:**
송치의견: {decision_kr}

사건 판단 요약:
{request.final_analysis.decision_summary}

법리 판단 요약:
{request.final_analysis.legal_issues_summary}

증거 충분성 요약:
{request.final_analysis.evidence_sufficiency_summary}

잔여 리스크 요약:
{request.final_analysis.remaining_risk_summary}

**출력 형식 (반드시 아래 구조의 유효한 단일 JSON 객체만 출력하십시오. 마크다운 코드블록, 설명 텍스트, 주석을 절대 포함하지 마십시오):**
{{
  "title": "수사결과보고",
  "content": {{
    "case_name": "{request.case_detail.title}",
    "suspect": "피의자 성명 (사건 정보에서 파악된 경우 기재, 파악할 수 없으면 null)",
    "charge": "죄명 (적용 법조 기반으로 기재, 반드시 포함할 것)",
    
    "case_overview": {{
      "occurred_at": "{request.case_detail.occurred_at}",
      "location": "{request.case_detail.location}",
      "case_details": "범죄사실을 특정하여 서술 (일시, 장소, 방법, 결과를 구체적으로 기재, 5-7문장, ~함/~였음)"
    }},
    
    "investigation_result": {{
      "collected_evidence": "수집된 각 증거를 열거하고, 각 증거의 증명력·신빙성·관련성을 평가하여 서술 (~함/~였음)",
      "analysis_details": "각 증거에 대한 분석 결과를 구체적으로 서술 (~함/~였음)"
    }},
    
    "legal_review": {{
      "applicable_law": "적용 법조를 조문 단위로 명시 (예: 형법 제257조 제1항 등)",
      "elements": "각 구성요건(객관적 구성요건, 주관적 구성요건)별 충족 여부를 구체적으로 검토하여 서술 (~함/~였음)",
      "overall_judgement": "위법성·책임성 판단을 포함한 법리 검토 결과를 서술 (~함/~였음)"
    }},
    
    "transfer_opinion": {{
      "opinion": "{decision_kr}",
      "judgement_basis": "증거와 법리에 근거한 {decision_kr} 판단 이유를 구체적으로 서술 (5-7문장, ~함/~였음)",
      "remaining_risk": "잔여 리스크 또는 유의사항을 서술 (~함/~였음)"
    }},
    
    "special_notes": "특이사항이 있으면 기재, 없으면 '없음'"
  }}
}}

**작성 원칙:**
- 반드시 위 출력 형식의 유효한 단일 JSON 객체만 출력할 것 (마크다운 코드블록, 설명 텍스트, 주석 금지)
- 모든 중괄호를 정확히 열고 닫을 것
- 공문서체 3인칭 과거 시제 (~함, ~였음, ~확인됨, ~판단됨)
- 객관적 사실과 증거 중심으로 서술
- 증거 평가: 각 증거의 증명력, 신빙성, 관련성을 구체적으로 평가
- 법리 검토: 적용 법조, 구성요건 충족 여부, 위법성·책임성 판단을 포함
- 법률 용어 정확히 사용
- 근거와 결론 명확히 구분
- 송치의견에 부합하는 논리적 전개
- 경어체(~합니다) 및 평서체(~한다) 절대 금지
"""
        
        return prompt