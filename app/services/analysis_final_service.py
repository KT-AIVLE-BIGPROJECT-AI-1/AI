# app/services/analysis_final_service.py

import json
from collections import Counter
from typing import Dict, List, Any
from openai import OpenAI

from app.config import settings
from app.models.analysis_final_schema import (
    AnalysisFinalRequest,
    AnalysisFinalResponse
)

client = OpenAI(api_key=settings.OPENAI_API_KEY)


# ============================================================
# generate_final_analysis (AI.ipynb와 100% 동일)
# ============================================================

def generate_final_analysis(
    case_detail: Dict,
    legal_criteria_with_evaluation: List[Dict],
    analysis_list: List[Dict],
    chat_logs: List[Dict],
    openai_client
) -> Dict:
    """
    모든 분석 결과를 종합하여 최종 송치 의견 생성
    API 명세서 준수 버전
    """
    
    print("\n" + "="*70)
    print("📊 최종 분석 (FINAL_ANALYSIS) 생성")
    print("="*70)
    
    # ============================================================
    # 1. 통계 수집
    # ============================================================
    
    print("\n[1단계] 통계 수집 중...")
    
    # 증거 분석 통계
    total_evidence = len(analysis_list)
    evidence_by_type = Counter(a.get('analysis_type', 'UNKNOWN') for a in analysis_list)
    
    # 법리 기준 평가 통계
    all_evaluations = []
    for criterion in legal_criteria_with_evaluation:
        eval_data = criterion.get('criteria_evaluation', {})
        if eval_data:
            all_evaluations.append(eval_data)
    
    total_criteria = len(all_evaluations)
    satisfied_count = sum(1 for e in all_evaluations if e.get('status') == 'MET')
    not_satisfied_count = sum(1 for e in all_evaluations if e.get('status') == 'NOT_MET')
    insufficient_count = sum(1 for e in all_evaluations if e.get('status') == 'INSUFFICIENT')
    
    # 법리 쟁점 추출
    legal_issues = {}
    for criterion in legal_criteria_with_evaluation:
        legal_issue = criterion.get('legal_issue', {})
        issue_name = legal_issue.get('issue_name', '')
        if issue_name and issue_name not in legal_issues:
            legal_issues[issue_name] = legal_issue.get('related_law', '')
    
    print(f"   ✅ 증거: {total_evidence}건")
    print(f"   ✅ 법리 기준: {total_criteria}건")
    print(f"   ✅ 법리 쟁점: {len(legal_issues)}개")
    
    # ============================================================
    # 2. GPT에게 최종 판단 요청
    # ============================================================
    
    print("\n[2단계] GPT 최종 판단 생성 중...")
    
    # 사건 정보 요약
    case_info = f"""
[사건 정보]
사건명: {case_detail.get('title', '미상')}
사건 유형: {case_detail.get('type', '미상')}
발생 일시: {case_detail.get('occurred_at', '미상')}
발생 장소: {case_detail.get('location', '미상')}
사건 개요: {case_detail.get('description', '미상')}
"""
    
    # 증거 현황 요약
    evidence_summary = f"""
[증거 현황]
- 총 증거: {total_evidence}건
- 증거 유형: {dict(evidence_by_type)}
"""
    
    # 법리 평가 요약
    legal_evaluation_summary = f"""
[법리 기준 평가]
- 총 평가 기준: {total_criteria}건
- 충족 (MET): {satisfied_count}건
- 불충족 (NOT_MET): {not_satisfied_count}건
- 불충분 (INSUFFICIENT): {insufficient_count}건
"""
    
    # 법리 쟁점 목록
    legal_issues_text = "\n".join([
        f"- {issue_name} (관련 법률: {law})"
        for issue_name, law in legal_issues.items()
    ])
    
    # 평가 세부 내용
    evaluation_details = []
    for idx, criterion in enumerate(legal_criteria_with_evaluation[:10], 1):
        criterion_text = criterion.get('criterion_text', '')
        eval_data = criterion.get('criteria_evaluation', {})
        status = eval_data.get('status', 'UNKNOWN')
        reason = eval_data.get('reason', '')[:100]
        
        evaluation_details.append(
            f"{idx}. {criterion_text}\n   상태: {status}\n   사유: {reason}..."
        )
    
    evaluation_details_text = "\n\n".join(evaluation_details)
    
    # GPT 프롬프트
    prompt = f"""당신은 형사 사건 분석 전문가입니다. 
아래 모든 정보를 종합하여 **최종 송치 의견**을 작성하십시오.

{case_info}

{evidence_summary}

{legal_evaluation_summary}

[법리 쟁점]
{legal_issues_text}

[법리 기준 평가 상세 (일부)]
{evaluation_details_text}

위 모든 정보를 바탕으로 다음을 작성하십시오:

1. **recommended_decision**: "TRANSFER" | "NON_TRANSFER" | "SUSPENSION" 중 하나
   - TRANSFER: 송치 (기소 의견)
   - NON_TRANSFER: 불송치 (기소 유예 또는 무혐의)
   - SUSPENSION: 보류 (추가 수사 필요)
   
   판단 기준:
   - MET가 대부분 → TRANSFER
   - NOT_MET가 대부분 → NON_TRANSFER
   - INSUFFICIENT가 많음 → SUSPENSION

2. **decision_summary**: 송치 의견에 대한 종합 요약 (200-300자)
   - 사건명, 혐의 사실
   - 증거 현황 (총 몇 건, 충족 여부)
   - 법리 쟁점 평가 결과
   - 최종 판단 및 근거

3. **legal_issues_summary**: 법리 쟁점 요약 (150-250자)
   형식:
   [법리 쟁점]
   쟁점명
   
   [관련 법률]
   법률명
   
   [구성요건]
   기준1, 기준2, 기준3

4. **evidence_sufficiency_summary**: 증거 충분성 평가 (150-200자)
   형식:
   [증거 현황]
   - 총 X건의 증거 분석 완료
   - 증거 유형: Y가지
   
   [카테고리별 증거]
   - DOC: X건
   - IMG: X건
   - VDO: X건
   - STT: X건
   
   [평가]
   증거의 충분성이 [송치/불송치/보류] 결정을 뒷받침합니다.

5. **remaining_risk_summary**: 잔여 리스크 요약 (100-150자)
   형식:
   [리스크 분석]
   주요 리스크 내용
   
   [불충분 항목]
   X건의 법리 기준이 INSUFFICIENT 상태입니다.

JSON만 출력:
{{
  "recommended_decision": "TRANSFER|NON_TRANSFER|SUSPENSION",
  "decision_summary": "...",
  "legal_issues_summary": "...",
  "evidence_sufficiency_summary": "...",
  "remaining_risk_summary": "..."
}}
"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content.strip()
        final_analysis = json.loads(content)
        
        print(f"\n✅ 최종 판단 생성 완료")
        print(f"   📋 송치 의견: {final_analysis.get('recommended_decision')}")
        
        return final_analysis
    
    except Exception as e:
        print(f"\n❌ 오류 발생: {str(e)}")
        
        return {
            "recommended_decision": "SUSPENSION",
            "decision_summary": f"시스템 오류로 인해 자동 판단이 불가능합니다. 수동 검토가 필요합니다. (오류: {str(e)})",
            "legal_issues_summary": "오류로 인한 생성 실패",
            "evidence_sufficiency_summary": "오류로 인한 생성 실패",
            "remaining_risk_summary": "오류로 인한 생성 실패"
        }


# ============================================================
# FastAPI Service
# ============================================================

class AnalysisFinalService:
    """최종 분석 서비스"""
    
    @staticmethod
    def generate_final_analysis(request: AnalysisFinalRequest) -> AnalysisFinalResponse:
        """최종 분석 생성"""
        print("\n" + "=" * 70)
        print("⚖️ 최종 분석 시작")
        print("=" * 70)
        
        # case_detail을 dict로 변환
        case_detail = request.case_detail.model_dump()
        
        # legal_criteria를 dict 리스트로 변환
        legal_criteria_with_evaluation = [
            lc.model_dump() for lc in request.legal_criteria
        ]
        
        # analysys를 dict 리스트로 변환
        analysis_list = [
            a.model_dump() for a in request.analysys
        ]
        
        # chat_logs를 dict 리스트로 변환
        chat_logs = [
            cl.model_dump() for cl in request.chat_logs
        ] if request.chat_logs else []
        
        # 최종 분석 생성
        final_result = generate_final_analysis(
            case_detail=case_detail,
            legal_criteria_with_evaluation=legal_criteria_with_evaluation,
            analysis_list=analysis_list,
            chat_logs=chat_logs,
            openai_client=client
        )
        
        print("\n" + "=" * 70)
        print("✅ 최종 분석 완료")
        print("=" * 70)
        
        return AnalysisFinalResponse(
            recommended_decision=final_result["recommended_decision"],
            decision_summary=final_result["decision_summary"],
            legal_issues_summary=final_result["legal_issues_summary"],
            evidence_sufficiency_summary=final_result["evidence_sufficiency_summary"],
            remaining_risk_summary=final_result["remaining_risk_summary"]
        )