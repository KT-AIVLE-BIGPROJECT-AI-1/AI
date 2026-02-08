from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel

CaseType = Literal["ASSAULT","THEFT","FRAUD","TRAFFIC","OTHER"]
CaseStatus = Literal["OPEN","ONGOING","DONE"]

# -------- CASE ----------
class CaseSummary(BaseModel):
    action: str
    object: str
    interaction: str
    place: str
    time: str
    result: str

class CaseDetail(BaseModel):
    title: str
    description: str
    summary: CaseSummary
    type: CaseType
    status: CaseStatus
    occurred_at: str
    location: str

# -------- LEGAL CRITERIA ----------
class LegalIssue(BaseModel):
    issue_name: str
    related_law: str

class CriteriaEvaluation(BaseModel):
    analysis_id: Optional[str]
    status: str
    reason: str
    evidence_gap: Optional[str]

class LegalCriterionItem(BaseModel):
    criterion_text: str
    precedent_case_no: str
    precedent_decision_date: str
    legal_issue: LegalIssue
    criteria_evaluation: CriteriaEvaluation

# -------- ANALYSIS (파일 분석 결과) ----------
class AnalysisItem(BaseModel):
    analysis_id: str
    analysis_type: Literal["DOC","STT","VDO","IMG"]
    status: str
    result_data: Dict[str, Any]

# -------- CHAT LOG ----------
class UsedContext(BaseModel):
    analysis_ids: Optional[List[str]] = None
    type: Optional[str] = None

class ChatLogItem(BaseModel):
    role: Literal["USER","AI"]
    message: str
    used_context: Optional[UsedContext]
    created_at: str

# -------- 최종 요청 DTO ----------
class FinalAnalysisRequest(BaseModel):
    case_detail: CaseDetail
    legal_criteria: List[LegalCriterionItem]
    analysys: List[AnalysisItem]
    chat_logs: List[ChatLogItem]

# -------- 최종 응답 DTO (단순 패스스루) ----------
class FinalAnalysisResponse(BaseModel):
    final_analysis: Dict[str, Any]
