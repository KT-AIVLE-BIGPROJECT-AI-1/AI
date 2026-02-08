from typing import Optional
from pydantic import BaseModel

class AnalysisDocRequest(BaseModel):
    file_id: str
    case_id: str
    file_type: str      # "DOCUMENT"
    file_path: str
    origin_name: str
    file_size: int
    created_at: str

class AnalysisDocResponse(BaseModel):
    analysis_id: str
    file_id: str
    analysis_type: str   # "DOC"
    result_data: str
    created_at: str
