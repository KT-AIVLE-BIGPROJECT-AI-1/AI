# app/services/analysis_image_service.py

import uuid
import base64
from PIL import Image
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
from openai import OpenAI

from app.config import settings
from app.models.analysis_image_schema import (
    AnalysisImageRequest,
    AnalysisImageResponse
)

client = OpenAI(api_key=settings.OPENAI_API_KEY)


# ============================================================
# ImageAnalyzerV2 (AI.ipynb와 100% 동일)
# ============================================================

class ImageAnalyzerV2:
    """
    이미지 분석 엔진 (사건 연결형)
    - 사진의 사실만 기술
    - 사건 개요와의 관련성 명시
    - 추정/판단/미학적 묘사 금지
    """

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
"""

    def __init__(self, client, model: str):
        self.client = client
        self.model = model

    # ---------------- 이미지 메타 ----------------
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

    # ---------------- CASE를 문자열로 변환하는 내부 메서드 ----------------
    def _format_case_info(self, case_json: dict) -> str:
        """CASE JSON을 사건 정보 문자열로 변환"""
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

    # ---------------- 분석 ----------------
    def analyze_one(self, image_path: Path, case_json: dict = None, client=None) -> str:
        """
        이미지를 분석하여 설명문 생성
        
        Args:
            image_path: 이미지 파일 경로
            case_json: CASE JSON
            client: OpenAI 클라이언트
        """
        api_client = client or self.client
        
        # CASE를 문자열로 변환
        case_info = self._format_case_info(case_json)
        
        meta_text = self._get_image_meta(image_path)
        data_url = self._image_to_data_url(image_path)

        full_text = self.FORENSIC_PROMPT.format(
            case_info=case_info,
            meta_text=meta_text
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


# ============================================================
# 이미지 → 고정 JSON (ANALYSIS_IMG)
# ============================================================

def analyze_image_to_fixed_json(
    analyzer: ImageAnalyzerV2,
    analysis_id: str,
    file_id: str,
    file_path: Path,
    case_json: dict = None,
    client = None
) -> Dict[str, Any]:
    """
    이미지를 분석하여 ANALYSIS_IMG JSON 생성
    """

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
        "analysis_type": "IMG",
        "status": status,
        "result_data": analysis_text,
        "created_at": created_at
    }


# ============================================================
# FastAPI Service
# ============================================================

image_analyzer = ImageAnalyzerV2(
    client=client,
    model="gpt-4o"
)


class AnalysisImageService:
    """이미지 분석 서비스"""
    
    @staticmethod
    def analyze_image(request: AnalysisImageRequest) -> AnalysisImageResponse:
        """이미지 분석 실행"""
        print(f"\n🖼️ 이미지 분석 시작: {request.file_id}")
        
        # 파일 경로
        file_path = Path(request.file_path)
        
        # ✅ 수정: API 명세서에 case_detail 필드가 없으므로 None 처리
        case_json = None
        
        # 분석 실행
        result = analyze_image_to_fixed_json(
            analyzer=image_analyzer,
            analysis_id=request.analysis_id,
            file_id=request.file_id,
            file_path=file_path,
            case_json=case_json,
            client=client
        )
        
        print(f"✅ 이미지 분석 완료: {result['status']}")
        
        # 콜백 서비스에 분석 결과 등록 (SUMMARY용)
        from app.services.analysis_callback_service import AnalysisCallbackService
        AnalysisCallbackService.register_analysis_result(
            analysis_id=result["analysis_id"],
            result_data=result
        )
        
        return AnalysisImageResponse(**result)