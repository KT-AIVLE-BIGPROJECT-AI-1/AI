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
# generate_final_analysis
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
    """
    
    print("\n" + "="*70)
    print("📊 최종 분석 (FINAL_ANALYSIS) 생성")
    print("="*70)
    
    # ============================================================
    # 1. 통계 수집
    # ============================================================
    
    print("\n[1단계] 통계 수집 중...")
    
    # 전체 증거 통계
    total_evidence = len(analysis_list)
    evidence_by_type = Counter(a.get('file_type', 'UNKNOWN') for a in analysis_list)
    
    # 법리 기준 평가 통계
    all_evaluations = []
    for criterion in legal_criteria_with_evaluation:
        eval_data = criterion.get('criteria_evaluation', {})
        if eval_data:
            all_evaluations.append(eval_data)
    
    total_criteria = len(all_evaluations)
    satisfied_count = sum(1 for e in all_evaluations if e.get('status') == 'SATISFIED')
    not_satisfied_count = sum(1 for e in all_evaluations if e.get('status') == 'NOT_SATISFIED')
    insufficient_count = sum(1 for e in all_evaluations if e.get('status') == 'INSUFFICIENT')
    
    # 법리 쟁점 추출
    legal_issues = {}
    for criterion in legal_criteria_with_evaluation:
        legal_issue = criterion.get('legal_issue', {})
        issue_name = legal_issue.get('issue_name', '')
        if issue_name and issue_name not in legal_issues:
            legal_issues[issue_name] = legal_issue.get('related_law', '')
    
    print(f"   ✅ 증거: {total_evidence}건 ({dict(evidence_by_type)})")
    print(f"   ✅ 법리 기준: {total_criteria}건 (SATISFIED:{satisfied_count} / NOT_SATISFIED:{not_satisfied_count} / INSUFFICIENT:{insufficient_count})")
    print(f"   ✅ 법리 쟁점: {len(legal_issues)}개")
    
    # ============================================================
    # 2. 증거별 요약 텍스트 생성
    # ============================================================
    
    evidence_details = []
    for a in analysis_list:
        file_type = a.get('file_type', 'UNKNOWN')
        analysis_id = a.get('analysis_id', '')
        result_data = a.get('result_data', '')
        
        if file_type in ('DOCUMENT', 'IMAGE'):
            # 문서/이미지: 텍스트 요약
            summary_text = str(result_data)[:300] if result_data else "(분석 결과 없음)"
            evidence_details.append(f"[{file_type}] {analysis_id}: {summary_text}")
        
        elif file_type == 'VIDEO':
            # 영상: VIDEO_EVENT 요약
            if isinstance(result_data, list):
                events = []
                for item in result_data:
                    if isinstance(item, dict):
                        payload = item.get('payload', [])
                        if isinstance(payload, list):
                            for evt in payload:
                                evt_type = evt.get('event_type', '')
                                evt_desc = evt.get('event_description', '')
                                start = evt.get('start_time', '')
                                end = evt.get('end_time', '')
                                events.append(f"{evt_type}: {evt_desc} ({start}s~{end}s)")
                evidence_details.append(f"[VIDEO] {analysis_id}: {', '.join(events) if events else '(이벤트 없음)'}")
            else:
                evidence_details.append(f"[VIDEO] {analysis_id}: {str(result_data)[:200]}")
        
        elif file_type == 'AUDIO':
            # 음성: stage별 요약
            if isinstance(result_data, list):
                audio_parts = []
                for item in result_data:
                    if isinstance(item, dict):
                        stage = item.get('stage', '')
                        payload = item.get('payload', {})
                        if stage == 'TRANSCRIPT':
                            content = payload.get('content', '') if isinstance(payload, dict) else ''
                            audio_parts.append(f"전사: {content[:100]}")
                        elif stage == 'KEY_STATEMENT':
                            if isinstance(payload, list):
                                stmts = [s.get('content', '') for s in payload]
                                audio_parts.append(f"핵심진술: {', '.join(stmts)}")
                        elif stage == 'CONTRADICTION':
                            if isinstance(payload, list):
                                contras = [c.get('description', '') for c in payload]
                                audio_parts.append(f"모순: {', '.join(contras)}")
                        elif stage == 'QUESTION':
                            if isinstance(payload, list):
                                qs = [q.get('question', '') for q in payload]
                                audio_parts.append(f"추가질문: {', '.join(qs)}")
                evidence_details.append(f"[AUDIO] {analysis_id}: {'; '.join(audio_parts) if audio_parts else '(내용 없음)'}")
            elif isinstance(result_data, str):
                # result_data가 JSON 문자열인 경우
                try:
                    parsed = json.loads(result_data)
                    if isinstance(parsed, list):
                        audio_parts = []
                        for item in parsed:
                            stage = item.get('stage', '')
                            payload = item.get('payload', {})
                            if stage == 'TRANSCRIPT':
                                content = payload.get('content', '') if isinstance(payload, dict) else ''
                                audio_parts.append(f"전사: {content[:100]}")
                            elif stage == 'KEY_STATEMENT':
                                if isinstance(payload, list):
                                    stmts = [s.get('content', '') for s in payload]
                                    audio_parts.append(f"핵심진술: {', '.join(stmts)}")
                            elif stage == 'CONTRADICTION':
                                if isinstance(payload, list):
                                    contras = [c.get('description', '') for c in payload]
                                    audio_parts.append(f"모순: {', '.join(contras)}")
                            elif stage == 'QUESTION':
                                if isinstance(payload, list):
                                    qs = [q.get('question', '') for q in payload]
                                    audio_parts.append(f"추가질문: {', '.join(qs)}")
                        evidence_details.append(f"[AUDIO] {analysis_id}: {'; '.join(audio_parts) if audio_parts else '(내용 없음)'}")
                    else:
                        evidence_details.append(f"[AUDIO] {analysis_id}: {str(result_data)[:200]}")
                except (json.JSONDecodeError, AttributeError):
                    evidence_details.append(f"[AUDIO] {analysis_id}: {str(result_data)[:200]}")
            else:
                evidence_details.append(f"[AUDIO] {analysis_id}: {str(result_data)[:200]}")
    
    evidence_details_text = "\n".join(evidence_details[:15])  # 최대 15건
    
    # ============================================================
    # 3. GPT에게 최종 판단 요청
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

[증거 상세]
{evidence_details_text}
"""
    
    # 법리 평가 요약
    legal_evaluation_summary = f"""
[법리 기준 평가]
- 총 평가 기준: {total_criteria}건
- 충족 (SATISFIED): {satisfied_count}건
- 불충족 (NOT_SATISFIED): {not_satisfied_count}건
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
   - SATISFIED가 대부분 → TRANSFER
   - NOT_SATISFIED가 대부분 → NON_TRANSFER
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
   - DOCUMENT: X건
   - IMAGE: X건
   - VIDEO: X건
   - AUDIO: X건
   
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
        
        # analyses를 dict 리스트로 변환 (전체 파일 타입 포함)
        analysis_list = [
            a.model_dump() for a in request.analyses
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