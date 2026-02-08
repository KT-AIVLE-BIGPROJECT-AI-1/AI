# app/routers/analysis.py

from fastapi import APIRouter, BackgroundTasks
from app.models.analysis_schema import (
    AnalysisUploadRequest,
    AnalysisUploadResponse,
    AnalysisTarget
)
from app.routers.stt_video import run_stt_video_background

router = APIRouter(prefix="/analysis", tags=["Analysis"])

def decide_analysis_type(file_type: str) -> str:
    mapping = {
        "VIDEO": "VDO",
        "AUDIO": "STT",
        "IMAGE": "IMG",
        "DOCUMENT": "DOC"
    }
    return mapping.get(file_type, "DOC")

@router.post("/upload", response_model=AnalysisUploadResponse)
def upload_investigation_files(
    req: AnalysisUploadRequest,
    background_tasks: BackgroundTasks
):

    targets = []
    for f in req.investigation_files:
        targets.append(
            AnalysisTarget(
                origin_name=f.origin_name,
                file_type=f.file_type,
                analysis_type=decide_analysis_type(f.file_type)
            )
        )

    background_tasks.add_task(run_stt_video_background, req)

    return {
        "status": "PENDING",
        "targets": targets
    }
