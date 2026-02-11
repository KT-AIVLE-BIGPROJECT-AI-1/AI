# app/integrations/backend_callback_client.py

import requests
from app.config import settings


def send_stage_callback_sync(
    case_id: str,
    analysis_id: str,
    stage: str,
    payload
):
    """
    백엔드 콜백 전송
    요청 body는 반드시 아래 형식만 사용한다.

    {
      "stage": "...",
      "payload": {}
    }
    """

    if not settings.BACKEND_BASE_URL:
        print("   ⚠️ BACKEND_BASE_URL 미설정: 콜백 전송 스킵")
        return

    url = f"{settings.BACKEND_BASE_URL}/cases/{case_id}/analysis/{analysis_id}/callback"

    body = {
        "stage": stage.upper(),
        "payload": payload if payload is not None else {}
    }

    try:
        response = requests.post(url, json=body, timeout=3)

        if response.status_code >= 400:
            print(f"   ❌ 콜백 실패: {response.status_code} {response.text}")
        else:
            print(f"   📡 콜백 성공: {body['stage']}")

    except Exception as e:
        print(f"   ⚠️ 콜백 예외 발생 (무시): {e}")
