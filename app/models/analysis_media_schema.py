# app/models/analysis_media_schema.py

from pydantic import BaseModel, Field
from typing import Optional


class AnalysisMediaRequest(BaseModel):
    file_id: str
    case_id: str
    file_type: str
    file_path: Optional[str] = Field(default=None, description="로컬 파일 경로")
    presigned_url: Optional[str] = Field(default=None, description="S3 presigned URL")
    origin_name: str
    file_size: int
    created_at: str