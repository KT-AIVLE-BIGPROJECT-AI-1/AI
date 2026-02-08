import os
import json
from openai import OpenAI
from app.models.report_schema import ReportDraftRequest

from dotenv import load_dotenv
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# --------------------------------------
# 유틸
# --------------------------------------

def normalize_case_context(req: ReportDraftRequest) -> dict:
    c = req.case_detail
    f = req.final_analysis

    return {
        "사건명": c.title,
        "사건요약(원문)": c.summary,
        "사건설명": c.description,
        "발생일시": c.occurred_at.isoformat(),
        "발생장소": c.location,
        "사건유형": c.type,
        "현재상태": c.status,

        "최종결정_기준": f.recommended_decision,
        "사용자판단": req.decision_type,

        "판단요약": f.decision_summary,
        "법리요약": f.legal_issue_summary,
        "증거요약": f.evidence_sufficiency_summary,
        "잔여위험": f.remaining_risk_summary,
    }

def decision_title(decision: str) -> str:
    if decision == "TRANSFER":
        return "송치 결정서"
    elif decision == "NON_TRANSFER":
        return "불송치 결정서"
    elif decision == "SUSPENSION":
        return "수사중지 결정서"
    else:
        return "수사 결정서"

# --------------------------------------
# 내부 LLM 호출 (서비스 레이어)
# --------------------------------------

def call_llm(prompt: str) -> dict:
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1200
        )

        raw = resp.choices[0].message.content.strip()

        if raw.startswith("```"):
            raw = raw.replace("```json", "").replace("```", "").strip()

        parsed = json.loads(raw)

        if "title" not in parsed or "content" not in parsed:
            raise ValueError("Invalid LLM format")

        return parsed

    except Exception as e:
        return {
            "title": "초안 생성 실패",
            "content": {
                "error": str(e),
                "message": "LLM 호출 실패로 초안을 생성하지 못했습니다."
            }
        }

# --------------------------------------
# ① 수사보고 초안
# --------------------------------------

def make_interim_report(req: ReportDraftRequest):
    ctx = normalize_case_context(req)

    prompt = f"""
아래 사건을 바탕으로 '수사보고' 초안을 작성하라.

사건 정보:
{ctx}

작성 기준:
- 최종 판단 기준 = {ctx['최종결정_기준']}
- 사건요약(원문)을 기준으로 정리

JSON 출력:
{{
 "title": "수사보고",
 "content": {{
   "사건개요": "...",
   "확인사실": "...",
   "잔여쟁점": "..."
 }}
}}
"""
    return call_llm(prompt)

# --------------------------------------
# ② 수사결과보고 초안
# --------------------------------------

def make_final_report(req: ReportDraftRequest):
    ctx = normalize_case_context(req)

    prompt = f"""
아래 사건 정보를 바탕으로 '수사결과보고' 초안을 작성하라.

사건 정보:
{ctx}

작성 기준:
- 최종 판단 기준 = {ctx['최종결정_기준']}

JSON 출력:
{{
 "title": "수사결과보고",
 "content": {{
   "범죄사실": "...",
   "적용법조": "...",
   "증거관계": "...",
   "수사결과및의견": "..."
 }}
}}
"""
    return call_llm(prompt)

# --------------------------------------
# ③ 수사결정서 초안
# --------------------------------------

def make_decision_report(req: ReportDraftRequest):
    ctx = normalize_case_context(req)
    decision = req.decision_type

    prompt = f"""
당신은 경찰 수사 실무 문서 작성 AI이다.

아래 사건 정보를 바탕으로
'{decision}' 유형의 결정서를 작성하라.

=== 사건 정보 ===
{ctx}

작성 원칙:
- 반드시 decision_type = {decision} 기준으로 작성
- 단정적 법률판단 금지
- 사실 중심 기술

JSON 출력:
{{
 "title": "{decision_title(decision)}",
 "content": {{
   "범죄사실": "...",
   "증거관계": "...",
   "결정이유": "..."
 }}
}}
"""
    return call_llm(prompt)

