from fastapi import APIRouter, HTTPException
from openai import OpenAI

from app.config import OPENAI_API_KEY
from app.models.analysis_img_schema import (
    AnalysisImgRequest,
    AnalysisImgResponse,
)
from app.services.image_service import (
    ImageAnalyzerV2,
    analyze_image_to_fixed_json,
)

router = APIRouter(prefix="/analysis", tags=["Analysis"])

client = OpenAI(api_key=OPENAI_API_KEY)
image_analyzer = ImageAnalyzerV2(client=client)

@router.post("/img", response_model=AnalysisImgResponse)
def analyze_image(req: AnalysisImgRequest):

    try:
        result = analyze_image_to_fixed_json(
            analyzer=image_analyzer,
            file_id=req.file_id,
            file_url=req.file_path,   # presigned_url
            case_json={"case_id": req.case_id},
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
