from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

app = FastAPI(title="Legal AI Server")

# =====================================================
# 0) Health Check (배포/모니터링용)
# =====================================================
@app.get("/health")
def health():
    return {"status": "ok"}


# =====================================================
# ===============  DTO (입/출력 모델)  =================
# =====================================================

# ---------- CASE ----------
class CaseRequest(BaseModel):
    case_id: str
    title: str
    description: str
    occured_at: Optional[str] = None
    location: str

class CaseSummaryResponse(BaseModel):
    case_id: str
    summary: Dict[str, Any]


# ---------- LEGAL ISSUE ----------
class LegalIssue(BaseModel):
    issue_name: str
    related_law: str

class LegalIssueRequest(BaseModel):
    case_id: str
    summary: Dict[str, Any]

class LegalIssueResponse(BaseModel):
    case_id: str
    issue_name: str
    related_law: str


# ---------- LEGAL CRITERIA ----------
class LegalCriteriaItem(BaseModel):
    criterion_text: str
    precedent_case_no: Optional[List[str]] = None
    precedent_decision_date: Optional[List[str]] = None

class LegalCriteriaRequest(BaseModel):
    case_id: str
    summary: Dict[str, Any]
    legal_issue: LegalIssue

class LegalCriteriaResponse(BaseModel):
    case_id: str
    legal_criteria: List[LegalCriteriaItem]


# ---------- CRITERIA EVALUATION ----------
class EvaluationItem(BaseModel):
    criterion_text: str
    status: str
    reason: str
    evidence_gap: str

class CriteriaEvaluationRequest(BaseModel):
    case_id: str
    summary: Dict[str, Any]
    legal_criteria: List[LegalCriteriaItem]

class CriteriaEvaluationResponse(BaseModel):
    case_id: str
    evaluations: List[EvaluationItem]


# =====================================================
# ===============  실제 엔드포인트  ====================
# =====================================================

# ----------------------------
# 1) CASE → /cases/summary
# ----------------------------
@app.post("/cases/summary", response_model=CaseSummaryResponse)
def generate_case_summary(case: CaseRequest):

    from app.pipeline import structure_case

    # 1️⃣ LLM으로 구조화 요약 생성 (행위/객체/결과 중심)
    summary = structure_case({
        "case_id": case.case_id,
        "title": case.title,
        "description": case.description
    })

    # 2️⃣ Spring 필드 → AI summary에 매핑 (핵심 변경 부분)
    summary["시간"] = case.occured_at.replace("T", " ")
    summary["장소"] = case.location

    # 3️⃣ 그대로 반환
    return {
        "case_id": case.case_id,
        "summary": summary
    }


# ----------------------------
# 2) Legal_Issue → /legal-issues/generate
# ----------------------------
@app.post("/legal-issues/generate", response_model=LegalIssueResponse)
def generate_legal_issue(req: LegalIssueRequest):

    # ✅ 당신 코랩의 infer_legal_issue 연결 지점
    from app.pipeline import infer_legal_issue

    legal_issue = infer_legal_issue(req.summary)

    return {
        "case_id": req.case_id,
        "issue_name": legal_issue["issue_name"],
        "related_law": legal_issue["related_law"]
    }


# ----------------------------
# 3) Legal_Criteria → /legal-criteria/judge
# ----------------------------
@app.post("/legal-criteria/judge", response_model=LegalCriteriaResponse)
def generate_legal_criteria(req: LegalCriteriaRequest):

    # ✅ 당신 전체 판례+RAG+anchor+expanded 로직 연결 지점
    from app.pipeline import build_legal_criteria

    criteria = build_legal_criteria(
        case_summary=req.summary,
        legal_issue={
        "issue_name": req.legal_issue.issue_name,
        "related_law": req.legal_issue.related_law
        }
    )

    return {
        "case_id": req.case_id,
        "legal_criteria": criteria
    }


# ----------------------------
# 4) Criteria_Evaluation → /legal-criteria/evaluate
# ----------------------------
@app.post("/legal-criteria/evaluate", response_model=CriteriaEvaluationResponse)
def evaluate_criteria(req: CriteriaEvaluationRequest):

    # ✅ 당신 평가 로직 연결 지점
    from app.evaluator import evaluate_criteria as eval_criteria

    evaluations = eval_criteria(
        case_summary=req.summary,
        legal_criteria=req.legal_criteria
    )

    return {
        "case_id": req.case_id,
        "evaluations": evaluations
    }
