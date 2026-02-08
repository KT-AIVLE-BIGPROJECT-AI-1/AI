import uuid, base64, requests, tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

from PIL import Image
from openai import OpenAI

from app.core.case_context import build_case_context


# ---------------- presigned_url → 로컬 파일 ----------------
def download_presigned_to_temp(url: str) -> Path:
    resp = requests.get(url)
    resp.raise_for_status()

    suffix = Path(url).suffix or ".jpg"

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(resp.content)
    tmp.close()

    return Path(tmp.name)


# ============================================================
# ImageAnalyzerV2 (FastAPI 버전)
# ============================================================

class ImageAnalyzerV2:
    FORENSIC_PROMPT = """당신은 수사 보조 이미지 분석 담당자입니다.

아래에는 사건 개요와 사진이 제공됩니다.

사진에 실제로 보이는 모든 객관적 정보를 빠짐없이 추출하여 설명문을 작성하되,
반드시 다음을 포함하십시오:

1. 사진에 나타난 모든 관찰 가능한 사실
2. 사건 개요와 직접적으로 연결되는 부분

절대 규칙:
- 사진에 보이는 사실만 기술
- 추정·단정·법적 판단 금지
- 목록/번호 사용 금지
- 연속된 설명문으로 6~10문장 작성

[사건 정보]
"""

    def __init__(self, client: OpenAI, model: str = "gpt-4o-mini"):
        self.client = client
        self.model = model

    def _image_to_data_url(self, path: Path) -> str:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        ext = path.suffix.replace(".", "").lower()
        if ext == "jpg":
            ext = "jpeg"

        return f"data:image/{ext};base64,{b64}"

    def _get_image_meta(self, path: Path) -> str:
        with Image.open(path) as im:
            w, h = im.size
        return f"- 파일명: {path.name}\n- 해상도: {w}x{h}\n"

    def analyze_one(self, image_path: Path, case_json: dict) -> str:
        case_context = build_case_context(case_json, self.client)
        meta_text = self._get_image_meta(image_path)
        data_url = self._image_to_data_url(image_path)

        prompt = self.FORENSIC_PROMPT + case_context + "\n[사진 메타]\n" + meta_text

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            temperature=0.0,
        )

        return resp.choices[0].message.content.strip()


# ============================================================
# 고정 JSON 변환 함수
# ============================================================

def analyze_image_to_fixed_json(
    analyzer: ImageAnalyzerV2,
    file_id: str,
    file_url: str,
    case_json: dict,
) -> Dict[str, Any]:

    analysis_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    try:
        local_path = download_presigned_to_temp(file_url)
        analysis_text = analyzer.analyze_one(local_path, case_json)
    except Exception as e:
        analysis_text = f"분석 실패: {str(e)}"

    return {
        "analysis_id": analysis_id,
        "file_id": file_id,
        "analysis_type": "IMG",
        "result_data": analysis_text,
        "created_at": created_at,
    }
