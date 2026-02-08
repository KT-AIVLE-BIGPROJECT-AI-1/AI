from pydantic import BaseModel

class AnalysisImgRequest(BaseModel):
    file_id: str
    case_id: str
    file_type: str      # "IMAGE"
    file_path: str      # presigned_url
    origin_name: str
    file_size: int
    created_at: str

class AnalysisImgResponse(BaseModel):
    analysis_id: str
    file_id: str
    analysis_type: str   # "IMG"
    result_data: str
    created_at: str
