from pydantic import BaseModel
from typing import Optional, Dict, Any

# ========== 요청 ==========
class CaseSummaryRequest(BaseModel):
    title: Optional[str] = None
    description: str
    type: Optional[str] = None
    occurred_at: Optional[str] = None
    location: Optional[str] = None

# ========== 응답 ==========
# class Summary(BaseModel):
#     action: str
#     object: str
#     interaction: str
#     place: str
#     time: str
#     result: str

class CaseSummaryResponse(BaseModel):
    summary: Dict[str, Any]