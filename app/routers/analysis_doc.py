from fastapi import APIRouter, HTTPException
from openai import OpenAI
from app.config import OPENAI_API_KEY

from app.models.analysis_doc_schema import (
    AnalysisDocRequest,
    AnalysisDocResponse
)

from app.services.document_service import (
    DocumentAnalyzerV3,
    analyze_document_to_fixed_json
)

router = APIRouter(prefix="/analysis", tags=["Analysis"])

client = OpenAI(api_key=OPENAI_API_KEY)

document_analyzer = DocumentAnalyzerV3(
    client=client,
    model="gpt-4o-mini",
    temperature=0.0,
    chunk_size=3000
)

@router.post("/doc", response_model=AnalysisDocResponse)
def analyze_document(req: AnalysisDocRequest):

    try:
        result = analyze_document_to_fixed_json(
            analyzer=document_analyzer,
            file_id=req.file_id,
            file_path=req.file_path,
            case_json={"case_id": req.case_id},  # 최소 정보 전달
            client=client
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
