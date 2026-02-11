# app/routers/analysis_media.py

from fastapi import APIRouter, HTTPException
from app.models.analysis_media_schema import AnalysisMediaRequest
from app.services.analysis_media_service import AnalysisMediaService

router = APIRouter(prefix="/analysis", tags=["Analysis - Media"])


@router.post("/stt-video")
async def analyze_media(request: AnalysisMediaRequest):
    """
    미디어 분석 (비디오/오디오)

    **video 응답:**
```json
    {
      "stage": "VIDEO_EVENT",
      "payload": [
        {"start_time": 2.0, "end_time": 6.0, "event_type": "MOVEMENT", "event_description": "..."}
      ]
    }
```

    **audio 응답:**
```json
    [
      {"stage": "TRANSCRIPT", "payload": {"content": "..."}},
      {"stage": "KEY_STATEMENT", "payload": [...]},
      {"stage": "CONTRADICTION", "payload": [...]},
      {"stage": "QUESTION", "payload": [...]}
    ]
```
    """
    try:
        response = AnalysisMediaService.analyze_media(request)
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"필수 라이브러리 미설치: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"미디어 분석 실패: {str(e)}")