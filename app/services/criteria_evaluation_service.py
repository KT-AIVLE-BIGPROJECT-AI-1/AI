# app/services/criteria_evaluation_service.py

import json
from openai import OpenAI
from app.config import settings
from app.models.criteria_evaluation_schema import (
    CriteriaEvaluationRequest,
    CriteriaEvaluationResponse
)

client = OpenAI(api_key=settings.OPENAI_API_KEY)


class CriteriaEvaluationService:
    """
    법리 판단 기준 충족 평가 서비스
    
    두 가지 모드:
    1. case_detail만 있음: 증거 없이 초기 평가 → 항상 INSUFFICIENT
    2. analysis만 있음: 증거 기반 재평가 → MET/NOT_MET/INSUFFICIENT
    """
    
    @staticmethod
    def evaluate_criteria(request: CriteriaEvaluationRequest) -> CriteriaEvaluationResponse:
        """
        법리 판단 기준 충족 평가
        
        case_detail이 있으면 → 증거 없이 평가 (항상 INSUFFICIENT)
        analysis가 있으면 → 증거 분석 결과 기반 평가 (MET/NOT_MET/INSUFFICIENT)
        """
        print("\n" + "=" * 70)
        print("⚖️ 법리 판단 기준 충족 평가")
        print("=" * 70)
        
        # 첫 번째 기준만 평가 (실제로는 모든 기준을 평가할 수 있음)
        criterion = request.legal_criteria[0]
        criterion_dict = criterion if isinstance(criterion, dict) else criterion.model_dump()
        
        criterion_text = criterion_dict.get('criterion_text', '')
        legal_issue = criterion_dict.get('legal_issue', {})
        
        print(f"📋 평가 대상 기준: {criterion_text}")
        print(f"📋 법리 쟁점: {legal_issue.get('issue_name', '')}")
        
        # ============================================================
        # 모드 1: case_detail만 있음 (증거 없이 평가)
        # ============================================================
        if request.case_detail:
            print(f"🔍 모드: case_detail (증거 없이 초기 평가)")
            print(f"   - case_id: {request.case_detail.case_id}")
            print(f"   - title: {request.case_detail.title}")
            
            response = CriteriaEvaluationService._evaluate_without_analysis(
                case_detail=request.case_detail,
                criterion_text=criterion_text,
                legal_issue=legal_issue
            )
        
        # ============================================================
        # 모드 2: analysis만 있음 (증거 기반 재평가)
        # ============================================================
        elif request.analysis:
            print(f"🔍 모드: analysis (증거 기반 재평가)")
            print(f"   - analysis_type: {request.analysis.analysis_type}")
            print(f"   - status: {request.analysis.status}")
            
            # criteria_evaluation 정보 출력 (있으면)
            previous_eval = criterion_dict.get('criteria_evaluation')
            if previous_eval:
                print(f"   - 이전 평가: {previous_eval.get('status', 'UNKNOWN')}")
            
            response = CriteriaEvaluationService._evaluate_with_analysis(
                analysis=request.analysis,
                criterion_text=criterion_text,
                legal_issue=legal_issue
            )
        
        else:
            # 스키마 검증에서 이미 걸러지지만 안전장치
            raise ValueError("case_detail 또는 analysis 중 하나는 필수입니다")
        
        print("=" * 70)
        print(f"✅ 평가 완료: {response.status}")
        print("=" * 70)
        
        return response
    
    # ============================================================
    # 모드 1: 증거 없이 평가 (case_detail)
    # ============================================================
    
    @staticmethod
    def _evaluate_without_analysis(
        case_detail,
        criterion_text: str,
        legal_issue: dict
    ) -> CriteriaEvaluationResponse:
        """
        증거 없이 평가 (항상 INSUFFICIENT 반환)
        """
        # 기준에서 핵심 키워드 추출
        keywords = criterion_text.split("(")[0].strip()
        
        reason = f"{keywords}을(를) 판단하기 위한 증거가 전혀 없습니다. 증거가 없으므로 해당 행위의 존재 여부를 확인할 수 없습니다."
        
        evidence_gap = f"{keywords}에 대한 구체적인 증거 자료(목격자 진술, 피해자 진술, CCTV 영상, 물리적 증거 등)가 필요합니다."
        
        return CriteriaEvaluationResponse(
            status="INSUFFICIENT",
            reason=reason,
            evidence_gap=evidence_gap
        )
    
    # ============================================================
    # 모드 2: 증거 기반 재평가 (analysis)
    # ============================================================
    
    @staticmethod
    def _evaluate_with_analysis(
        analysis,
        criterion_text: str,
        legal_issue: dict
    ) -> CriteriaEvaluationResponse:
        """
        증거 분석 결과 기반 평가
        GPT-4o를 사용하여 증거와 법리 기준을 종합 평가
        """
        # result_data를 문자열로 변환
        result_data = analysis.result_data
        if isinstance(result_data, dict):
            result_data_str = json.dumps(result_data, ensure_ascii=False, indent=2)
        else:
            result_data_str = str(result_data)
        
        prompt = f"""당신은 법리 판단 기준 충족 여부를 평가하는 AI입니다.

**법리 쟁점:**
{legal_issue.get('issue_name', '')}

**관련 법률:**
{legal_issue.get('related_law', '')}

**판단 기준:**
{criterion_text}

**증거 분석 결과:**
유형: {analysis.analysis_type}
상태: {analysis.status}
내용:
{result_data_str}

**평가 규칙:**
1. 증거가 판단 기준을 완전히 충족하면 → status: "MET"
2. 증거가 판단 기준에 반하면 → status: "NOT_MET"
3. 증거가 불충분하면 → status: "INSUFFICIENT"

**출력 형식 (JSON만 출력):**
{{
  "status": "INSUFFICIENT|MET|NOT_MET",
  "reason": "평가 이유 (2-3문장)",
  "evidence_gap": "부족한 증거 (INSUFFICIENT일 때만, 그 외는 빈 문자열)"
}}
"""
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # JSON 파싱
            import re
            result_text = re.sub(r"```json|```", "", result_text).strip()
            result = json.loads(result_text)
            
            return CriteriaEvaluationResponse(
                status=result.get("status", "INSUFFICIENT"),
                reason=result.get("reason", ""),
                evidence_gap=result.get("evidence_gap", "")
            )
        
        except Exception as e:
            print(f"⚠️ GPT 평가 실패: {e}")
            return CriteriaEvaluationResponse(
                status="INSUFFICIENT",
                reason=f"평가 중 오류 발생: {str(e)}",
                evidence_gap="자동 평가 실패. 수동 검토 필요."
            )