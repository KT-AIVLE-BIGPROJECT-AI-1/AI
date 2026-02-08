import requests

BACKEND_BASE_URL = "http://backend-server"

def send_callback(case_id: str, analysis_id: str, stage: str, payload: dict):
    url = f"{BACKEND_BASE_URL}/cases/{case_id}/analysis/{analysis_id}/callback"
    body = {
        "stage": stage,
        "payload": payload
    }
    try:
        r = requests.post(url, json=body, timeout=30)
        print(f"📡 Sent stage={stage} | status={r.status_code}")
    except Exception as e:
        print(f"❌ Callback 실패({stage}): {e}")

