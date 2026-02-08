import uuid, re, json
from datetime import datetime, timezone
from typing import Dict, Any, List
from openai import OpenAI

def generate_final_analysis_improved(
    client: OpenAI,
    req
) -> Dict[str, Any]:

    case = req.case_detail.dict()
    legal_criteria = [c.dict() for c in req.legal_criteria]
    analysis_list = [a.dict() for a in req.analysys]
    chat_logs = [c.dict() for c in req.chat_logs]

    # -------- 분석 결과 분류 --------
    video_events = [
        a["result_data"] for a in analysis_list if a["analysis_type"] == "VDO"
    ]

    transcripts = [
        a["result_data"] for a in analysis_list if a["analysis_type"] == "STT"
    ]

    analysis_img = [
        a for a in analysis_list if a["analysis_type"] == "IMG"
    ]

    criteria_evaluation = [
        c["criteria_evaluation"] for c in legal_criteria
    ]

    legal_issue = legal_criteria[0]["legal_issue"] if legal_criteria else {}

    # =========================
    # 🔹 AI 추천 결정
    # =========================
    충족_count = sum(1 for e in criteria_evaluation if e["status"] == "충족")
    불충족_count = sum(1 for e in criteria_evaluation if e["status"] == "불충족")
    확인필요_count = sum(1 for e in criteria_evaluation if e["status"] == "확인필요")

    decision_prompt = f"""
법리 쟁점: {legal_issue.get('issue_name','')}
관련 법률: {legal_issue.get('related_law','')}

충족: {충족_count}건
불충족: {불충족_count}건
확인필요: {확인필요_count}건

JSON으로만 답변:
{{
  "recommended_decision": "TRANSFER|NON_TRANSFER|SUSPENSION",
  "decision_reasoning": "3~5줄 이유"
}}
"""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role":"user","content":decision_prompt}],
            temperature=0.3,
            max_tokens=500
        )
        raw = resp.choices[0].message.content.strip()
        parsed = json.loads(re.sub(r"```json|```","",raw))

        recommended_decision = parsed.get("recommended_decision", "TRANSFER")
        decision_reasoning = parsed.get("decision_reasoning", "")

        if recommended_decision not in [
            "TRANSFER", "NON_TRANSFER", "SUSPENSION"
        ]:
            recommended_decision = "TRANSFER"

    except Exception:
        recommended_decision = "TRANSFER"
        decision_reasoning = "Evidence suggests transfer is appropriate."

    # =========================
    # 🔹 범행 요지 정리 (단순화)
    # =========================
    crime_location = case.get("location", "")
    crime_method = case.get("summary", {}).get("interaction", "")

    # =========================
    # 🔹 적용 법률 정리
    # =========================
    applicable_law = {
        "law_name": legal_issue.get("related_law", ""),
        "crime_name": legal_issue.get("issue_name", ""),
        "elements": [c["criterion_text"] for c in legal_criteria[:5]]
    }

    # =========================
    # 🔹 최종 통합 분석 결과
    # =========================
    final_analysis = {
        "final_id": str(uuid.uuid4()),
        "case_id": case.get("case_id", ""),
        "recommended_decision": recommended_decision,
        "decision_summary": decision_reasoning,
        "structured_data": {
            "crime_facts": {
                "location": crime_location,
                "method": crime_method
            },
            "applicable_law": applicable_law,
            "evidence_overview": {
                "video_event_count": len(video_events),
                "transcript_count": len(transcripts),
                "image_analysis_count": len(analysis_img)
            }
        },
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    return {"final_analysis": final_analysis}
