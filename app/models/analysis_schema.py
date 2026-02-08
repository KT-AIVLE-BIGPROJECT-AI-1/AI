from typing import List, Dict, Any, Literal
from pydantic import BaseModel

# ---------- 타입 정의 ----------
CaseStatus = Literal["OPEN", "ONGOING", "DONE"]
CaseType = Literal["ASSAULT", "THEFT", "FRAUD", "TRAFFIC", "OTHER"]
FileType = Literal["VIDEO", "AUDIO", "IMAGE", "DOCUMENT"]
AnalysisType = Literal["VDO", "STT", "IMG", "DOC"]

# ---------- 요청 구조 ----------
class CaseSummary(BaseModel):
    action: str
    object: str
    interaction: str
    place: str
    time: str
    result: str

class CaseDetail(BaseModel):
    case_id: str
    title: str
    description: str
    summary: CaseSummary
    type: CaseType
    status: CaseStatus
    occurred_at: str
    location: str

class InvestigationFile(BaseModel):
    job_id: str
    file_type: FileType
    origin_name: str
    presigned_url: str
    content_type: str

class AnalysisUploadRequest(BaseModel):
    case_detail: CaseDetail
    investigation_files: List[InvestigationFile]
    legal_criteria: List[Dict[str, Any]]   # 당신이 준 구조 그대로 유지

# ---------- 응답 구조 ----------
class AnalysisTarget(BaseModel):
    origin_name: str
    file_type: FileType
    analysis_type: AnalysisType

class AnalysisUploadResponse(BaseModel):
    status: Literal["PENDING"]
    targets: List[AnalysisTarget]
