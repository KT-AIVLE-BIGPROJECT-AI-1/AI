from fastapi import APIRouter, Depends
from openai import OpenAI

from app.models.final_analysis_schema import (
    FinalAnalysisRequest,
    FinalAnalysisResponse
)
from app.services.final_analysis_service import generate_final_analysis_improved
from app.config import OPENAI_API_KEY

router = APIRouter(prefix="/analysis", tags=["Final Analysis"])

def get_client():
    return OpenAI(api_key=OPENAI_API_KEY)

@router.post("/final", response_model=FinalAnalysisResponse)
def create_final_analysis(
    req: FinalAnalysisRequest,
    client: OpenAI = Depends(get_client)
):
    return generate_final_analysis_improved(client, req)
