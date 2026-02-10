# app/routers/analysis_callback.py

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.models.analysis_callback_schema import (
    AnalysisCallbackRequest,
    AnalysisResultItem
)
from app.services.analysis_callback_service import AnalysisCallbackService

router = APIRouter(prefix="/cases", tags=["Analysis - Callback"])


@router.post("/{case_id}/analysis/{analysis_id}/callback")
async def handle_analysis_callback(
    case_id: str,
    analysis_id: str,
    request: AnalysisCallbackRequest
):
    """
    분석 콜백 (저장 / 조회)
    
    각 stage의 JSON은 이전 단계에서 실제로 생성된 데이터.
    SUMMARY는 ANALYSIS_DOC/IMG 결과에서 가져옴.
    
    ---
    
    **저장 모드** (외부 AI → 서버, payload에 데이터 있음):
    
    요청:
    ```json
    {"stage": "TRANSCRIPT", "payload": {"content": "사건 당시..."}}
    ```
    응답:
    ```json
    {"message": "Callback received"}
    ```
    
    ---
    
    **조회 모드** (백엔드 → AI, payload가 {}):
    
    요청:
    ```json
    {"stage": "TRANSCRIPT | KEY_STATEMENT | CONTRADICTION | QUESTION | VIDEO_EVENT | SUMMARY", "payload": {}}
    ```
    
    응답 — 문서/이미지:
    ```json
    {
      "analysis_id": "doc-file-id",
      "result_data": {
        "stage": "SUMMARY",
        "payload": {"summary": "...", "confidence": 0.93, "keywords": [...]}
      }
    }
    ```
    
    응답 — 음성 (CONTRADICTION 있는 경우):
    ```json
    {
      "analysis_id": "audio-file-id",
      "result_data": [
        {"stage": "TRANSCRIPT", "payload": {"content": "..."}},
        {"stage": "KEY_STATEMENT", "payload": [{"temp_id": "ks-1", "content": "..."}]},
        {"stage": "CONTRADICTION", "payload": [{"statement_temp_id": "ks-1", "description": "...", "type": "TIME"}]},
        {"stage": "QUESTION", "payload": [{"statement_temp_id": "ks-1", "question": "..."}]}
      ]
    }
    ```
    
    응답 — 음성 (CONTRADICTION 없는 경우):
    ```json
    {
      "analysis_id": "audio-file-id",
      "result_data": [
        {"stage": "TRANSCRIPT", "payload": {"content": "..."}},
        {"stage": "KEY_STATEMENT", "payload": [{"temp_id": "ks-1", "content": "..."}]}
      ]
    }
    ```
    
    응답 — 영상:
    ```json
    {
      "analysis_id": "video-file-id",
      "result_data": [
        {"stage": "VIDEO_EVENT", "payload": [{"start_time": 12.3, "end_time": 18.7, "event_type": "ASSAULT", "event_description": "..."}]},
        {"stage": "VIDEO_EVENT", "payload": [{"start_time": 25.1, "end_time": 32.4, "event_type": "ESCAPE", "event_description": "..."}]}
      ]
    }
    ```
    
    **음성 파일 stage 의존성:**
    - TRANSCRIPT → 항상 생성
    - KEY_STATEMENT → 항상 생성
    - CONTRADICTION → KEY_STATEMENT에서 모순이 감지된 경우에만 생성
    - QUESTION → CONTRADICTION이 있을 때만 생성 (CONTRADICTION 없으면 QUESTION도 없음)
    """
    try:
        result = AnalysisCallbackService.handle_callback(
            case_id=case_id,
            analysis_id=analysis_id,
            request=request
        )
        
        # 저장 모드 → {"message": "Callback received"}
        if isinstance(result, dict):
            return JSONResponse(content=result)
        
        # 조회 모드 → 파일별 분석 결과 배열
        return JSONResponse(content=[item.model_dump() for item in result])
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"콜백 처리 실패: {str(e)}")