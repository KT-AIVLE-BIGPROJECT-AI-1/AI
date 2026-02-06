# =========================
# 수정 필요
# =========================

# app/routers/cases.py
# from openai import OpenAI
from fastapi import APIRouter, HTTPException, Depends
from app.models.case_schema import CaseRequest, CaseResponse
# from app.models.case_schema import CaseSummaryRequest, CaseSummaryResponse
from app.services.case_service import CaseService
# from app.services.case_service import summarize_case
# from app.config import OPENAI_API_KEY

router = APIRouter(prefix="/cases", tags=["Cases"])
# router = APIRouter(prefix="/cases")

def get_client():
    return OpenAI(api_key=OPENAI_API_KEY)

@router.post("/summary", response_model=CaseResponse)
async def create_case_summary(request: CaseRequest):
    """
    CASE 생성 및 Summary 추출
    
    - 사건 정보를 받아 6가지 요소로 구조화
    - action, object, interaction, place, time, result
    """
    try:
        response = CaseService.create_case(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CASE 생성 실패: {str(e)}")

# @router.post("/summary", response_model=CaseSummaryResponse)
# def create_case_summary(
#     body: CaseSummaryRequest,
#     client: OpenAI = Depends(get_client)
# ):
#     return summarize_case(body.dict(), client)

