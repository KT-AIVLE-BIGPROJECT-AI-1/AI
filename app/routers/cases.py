# app/routers/cases.py

from fastapi import APIRouter, HTTPException
from app.models.case_schema import CaseRequest, CaseResponse
from app.services.case_service import CaseService

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.post("/summary", response_model=CaseResponse)
async def create_case_summary(request: CaseRequest):
    """
    CASE 생성 및 Summary 추출
    
    사건 정보를 받아 6가지 요소로 구조화합니다.
    
    **요청:**
    ```json
    {
      "title": "강도 사건",
      "description": "서울시 주택가 골목길에서 발생한 스마트폰 강탈 사건",
      "type": "THEFT",
      "occurred_at": "2026-02-03T12:10:00Z",
      "location": "서울시 주택가 골목길"
    }
    ```
    
    **응답:**
    - case_id, title, description, type, occurred_at, location
    - summary: action, object, interaction, place, time, result
    - status, created_at, updated_at
    """
    try:
        response = CaseService.create_case(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CASE 생성 실패: {str(e)}")