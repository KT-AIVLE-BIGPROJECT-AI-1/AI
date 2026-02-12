# app/services/analysis_image_service.py
# 이미지 분석 서비스
# - OCR 전처리 (pytesseract) → 텍스트 추출
# - GPT-4o Vision → 시각 분석 + OCR 텍스트 통합

import uuid
import base64
from PIL import Image
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
from openai import OpenAI

from app.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

# ============================================================
# OCR 엔진 초기화 (다중 경로 탐색)
# ============================================================

_OCR_AVAILABLE = False
_OCR_LANG = "kor+eng"  # 한국어 + 영어

# tesseract 실행 파일 경로 (우선순위 순)
_TESSERACT_PATHS = [
    "tesseract-ocr.exe",                                              # VS Code 프로젝트 루트 상대경로
    "./tesseract-ocr.exe",                                            # 명시적 상대경로
    "C:/Users/User/Desktop/AI_Claude_Github/tesseract-ocr.exe",      # 절대경로
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",                  # 기본 설치 경로
    "/usr/bin/tesseract",                                              # Linux
]

try:
    import pytesseract
    import os

    _tesseract_found = False
    for _tpath in _TESSERACT_PATHS:
        if os.path.exists(_tpath):
            pytesseract.pytesseract.tesseract_cmd = _tpath
            try:
                pytesseract.get_tesseract_version()
                _OCR_AVAILABLE = True
                _tesseract_found = True
                print(f"   ✅ OCR 엔진 (pytesseract + tesseract) 사용 가능: {_tpath}")
                break
            except Exception:
                continue

    if not _tesseract_found:
        print("   ⚠️ OCR 엔진: tesseract 실행 파일을 찾을 수 없음 → GPT-4o Vision만 사용")

except ImportError:
    print("   ⚠️ OCR 엔진: pytesseract 미설치 → GPT-4o Vision만 사용")
except Exception:
    print("   ⚠️ OCR 엔진 초기화 실패 → GPT-4o Vision만 사용")


class ImageAnalyzerV2:
    FORENSIC_PROMPT = """당신은 수사 보조 이미지 분석 담당자입니다.

아래에는 사건 개요와 사진이 제공됩니다.

사진에 실제로 보이는 모든 객관적 정보를 빠짐없이 추출하여 설명문을 작성하되,
반드시 다음을 포함하십시오:

1. 사진에 나타난 모든 관찰 가능한 사실
   - 인물 (복장, 외형, 자세, 행동)
   - 물체/물품 (종류, 색상, 크기, 상태, 위치)
   - 장소 (건물, 도로, 표지판, 지형, 환경)
   - 시간 정보 (그림자, 조명, 날씨로 추정 가능한 시간대)
   - 텍스트 (간판, 표지판, 번호판 등 읽을 수 있는 모든 글자)
   - 거리/위치 관계 (사람 간 거리, 물체 배치)
2. 사건 개요와 직접적으로 연결되는 부분

절대 규칙:
- 사진에 보이는 모든 구체적 정보를 빠짐없이 포함할 것
- 색상, 위치, 크기 등은 가능한 구체적으로 기술
- 사진에 보이지 않는 내용 추가 금지
- 사건 개요에 없는 내용을 새로 만들지 말 것
- 추정, 단정, 법적 판단 금지
- 미학적 묘사 금지
- 목록/번호 사용 금지
- 설명문으로 작성 (6~10문장)

[사건 정보]
{case_info}

[사진 메타]
{meta_text}
{ocr_section}"""

    def __init__(self, client, model: str):
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

    def _format_case_info(self, case_json: dict) -> str:
        if not case_json:
            return "사건 정보 없음"
        
        info_parts = []
        if "title" in case_json:
            info_parts.append(f"사건명: {case_json['title']}")
        if "type" in case_json:
            info_parts.append(f"사건 유형: {case_json['type']}")
        if "description" in case_json:
            info_parts.append(f"사건 개요: {case_json['description']}")
        occurred_time = case_json.get('occurred_at', case_json.get('occured_at', ''))
        if occurred_time:
            info_parts.append(f"발생 일시: {occurred_time}")
        if "location" in case_json:
            info_parts.append(f"발생 장소: {case_json['location']}")
        if "summary" in case_json and case_json["summary"]:
            summary = case_json["summary"]
            if isinstance(summary, dict) and any(summary.values()):
                info_parts.append("\n사건 요약:")
                for key, value in summary.items():
                    if value:
                        info_parts.append(f"  - {key}: {value}")
        return "\n".join(info_parts)

    # ============================================================
    # OCR 전처리
    # ============================================================

    def _ocr_extract(self, image_path: Path) -> Optional[str]:
        """
        pytesseract로 이미지에서 텍스트 추출
        - 전처리: 그레이스케일 변환, 이진화
        - 한국어 + 영어 인식
        - 실패 시 None 반환
        """
        if not _OCR_AVAILABLE:
            return None

        try:
            import pytesseract

            img = Image.open(image_path)

            # 전처리: 그레이스케일
            if img.mode != 'L':
                img_gray = img.convert('L')
            else:
                img_gray = img

            # 전처리: 이진화 (텍스트 대비 향상)
            threshold = 128
            img_bin = img_gray.point(lambda p: 255 if p > threshold else 0, '1')

            # OCR 실행 (이진화 이미지)
            text_bin = pytesseract.image_to_string(
                img_bin,
                lang=_OCR_LANG,
                config='--psm 6'  # 단일 텍스트 블록으로 가정
            ).strip()

            # 원본 그레이스케일로도 시도 (이진화가 오히려 방해될 수 있음)
            text_gray = pytesseract.image_to_string(
                img_gray,
                lang=_OCR_LANG,
                config='--psm 6'
            ).strip()

            # 더 긴 결과를 선택
            ocr_text = text_bin if len(text_bin) >= len(text_gray) else text_gray

            if ocr_text and len(ocr_text) >= 2:
                # 노이즈 제거: 너무 짧은 줄 필터링
                lines = [line.strip() for line in ocr_text.split('\n') if len(line.strip()) >= 2]
                cleaned = "\n".join(lines)

                if cleaned:
                    print(f"   🔤 OCR 추출 완료: {len(cleaned)}자")
                    return cleaned

            print(f"   🔤 OCR: 의미 있는 텍스트 없음")
            return None

        except Exception as e:
            print(f"   ⚠️ OCR 실패 (무시): {e}")
            return None

    # ============================================================
    # 메인 분석
    # ============================================================

    def analyze_one(self, image_path: Path, case_json: dict = None, client=None) -> str:
        """
        이미지 분석 파이프라인:
        1. OCR 전처리 → 텍스트 추출
        2. GPT-4o Vision → 시각 분석 (OCR 텍스트 포함)
        """
        api_client = client or self.client
        case_info = self._format_case_info(case_json)
        meta_text = self._get_image_meta(image_path)
        data_url = self._image_to_data_url(image_path)

        # OCR 전처리
        ocr_text = self._ocr_extract(image_path)

        # OCR 결과를 프롬프트에 포함
        if ocr_text:
            ocr_section = (
                f"\n[OCR 추출 텍스트 (참고용 - 오류가 있을 수 있으므로 사진과 대조하여 검증)]\n"
                f"{ocr_text}\n"
            )
        else:
            ocr_section = ""

        full_text = self.FORENSIC_PROMPT.format(
            case_info=case_info,
            meta_text=meta_text,
            ocr_section=ocr_section
        )

        response = api_client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": full_text},
                        {"type": "image_url", "image_url": {"url": data_url}}
                    ]
                }
            ],
            temperature=0.0
        )

        return response.choices[0].message.content.strip()


def analyze_image_to_fixed_json(
    analyzer: ImageAnalyzerV2,
    analysis_id: str,
    file_id: str,
    file_path: Path,
    case_json: dict = None,
    client = None
) -> Dict[str, Any]:
    created_at = datetime.now(timezone.utc).isoformat()
    status = "PROCESSING"

    try:
        analysis_text = analyzer.analyze_one(file_path, case_json, client)
        status = "COMPLETED"
    except Exception as e:
        analysis_text = f"분석 실패: {str(e)}"
        status = "PENDING"

    return {
        "analysis_id": analysis_id,
        "file_id": file_id,
        "file_type": "IMAGE",
        "status": status,
        "result_data": analysis_text,
        "created_at": created_at
    }


image_analyzer = ImageAnalyzerV2(
    client=client,
    model="gpt-4o"
)


class AnalysisImageService:
    @staticmethod
    def analyze_image(request) -> dict:
        from app.models.analysis_image_schema import (
            AnalysisImageRequest,
            AnalysisImageResponse
        )

        print(f"\n🖼️ 이미지 분석 시작: {request.file_id}")

        file_path = Path(request.file_path)
        analysis_id = str(uuid.uuid4())
        case_json = None

        result = analyze_image_to_fixed_json(
            analyzer=image_analyzer,
            analysis_id=analysis_id,
            file_id=request.file_id,
            file_path=file_path,
            case_json=case_json,
            client=client
        )

        print(f"✅ 이미지 분석 완료: {result['status']}")

        from app.services.analysis_callback_service import AnalysisCallbackService
        AnalysisCallbackService.register_analysis_result(
            analysis_id=result["analysis_id"],
            result_data=result
        )

        return AnalysisImageResponse(**result)