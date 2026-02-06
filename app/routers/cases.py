from fastapi import APIRouter, Depends
from openai import OpenAI

from app.models.case_schema import CaseSummaryRequest, CaseSummaryResponse
from app.services.case_service import summarize_case
from app.config import OPENAI_API_KEY

router = APIRouter(prefix="/cases")

def get_client():
    return OpenAI(api_key=OPENAI_API_KEY)

@router.post("/summary", response_model=CaseSummaryResponse)
def create_case_summary(
    body: CaseSummaryRequest,
    client: OpenAI = Depends(get_client)
):
    return summarize_case(body.dict(), client)
