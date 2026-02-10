# app/services/report_final_service.py

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
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "당신은 경찰 수사결과보고 작성 전문가입니다."},
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
            request.final_analysis.recommended_decision,
            request.final_analysis.recommended_decision
        )
        
        prompt = f"""다음 수사 결과를 바탕으로 수사결과보고를 작성하십시오.

**사건 정보:**
사건번호: {request.case_detail.case_id}
사건명: {request.case_detail.title}
담당자: {request.case_detail.assignee_user_id}
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
{request.final_analysis.legal_issue_summary}

증거 충분성 요약:
{request.final_analysis.evidence_sufficiency_summary}

잔여 리스크 요약:
{request.final_analysis.remaining_risk_summary}

**출력 형식 (JSON만 출력):**
{{
  "title": "수사결과보고",
  "content": {{
    "case_name": "{request.case_detail.title}",
    "suspect": "미상",
    "charge": "사건유형 기반 추정",
    
    "case_overview": {{
      "occurred_at": "{request.case_detail.occurred_at}",
      "location": "{request.case_detail.location}",
      "case_details": "사건 요약 내용을 서술형으로 재구성 (5-7문장)"
    }},
    
    "investigation_result": {{
      "collected_evidence": "증거 충분성 요약 내용 기반",
      "analysis_details": "각 증거에 대한 분석 결과"
    }},
    
    "legal_review": {{
      "applicable_law": "법리 쟁점 요약에서 추출",
      "elements": "각 구성요건별 충족 여부",
      "overall_judgment": "법리 판단 요약 내용"
    }},
    
    "transfer_opinion": {{
      "opinion": "{decision_kr}",
      "judgment_basis": "사건 판단 요약 내용 (5-7문장)",
      "remaining_risk": "잔여 리스크 요약 내용"
    }},
    
    "special_notes": "특이사항이 있으면 기재, 없으면 '없음'"
  }}
}}

**작성 원칙:**
- 공문서 형식 준수
- 객관적이고 명확한 서술
- 법률 용어 정확히 사용
- 근거와 결론 명확히 구분
- 송치의견에 부합하는 논리적 전개
"""
        
        return prompt