"""
이미지 분석 서비스 (ImageAnalyzerV2 기반)
"""
from pathlib import Path
from typing import Dict, Any, Optional
import uuid
from datetime import datetime, timezone
import base64
from openai import OpenAI
from PIL import Image

from app.config import get_settings
from app.models.analysis_image_schema import ImageAnalysisResponse


class ImageAnalysisService:
    """이미지 분석 서비스"""
    
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
"""
    
    def __init__(self):
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.OPENAI_API_KEY)
    
    def image_to_data_url(self, path: Path) -> str:
        """이미지를 base64 data URL로 변환"""
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        
        ext = path.suffix.replace(".", "").lower()
        if ext == "jpg":
            ext = "jpeg"
        
        return f"data:image/{ext};base64,{b64}"
    
    def get_image_meta(self, path: Path) -> str:
        """이미지 메타데이터 추출"""
        try:
            with Image.open(path) as im:
                w, h = im.size
            return f"- 파일명: {path.name}\n- 해상도: {w}x{h}\n"
        except Exception as e:
            return f"- 파일명: {path.name}\n- 메타데이터 추출 실패: {str(e)}\n"
    
    def build_case_context(self, case_json: Optional[Dict[str, Any]]) -> str:
        """사건 컨텍스트 텍스트 생성"""
        if not case_json:
            return "[사건 정보 없음]"
        
        summary = case_json.get("summary", {})
        
        return f"""
[사건 기본 정보]
사건 제목: {case_json.get('title', '')}
사건 유형: {case_json.get('type', '')}
발생 일시: {case_json.get('occured_at', '')}
발생 장소: {case_json.get('location', '')}

[사건 설명]
{case_json.get('description', '')}

[사건 요약]
행위: {summary.get('action', '')}
객체: {summary.get('object', '')}
상호작용: {summary.get('interaction', '')}
장소: {summary.get('place', '')}
시간: {summary.get('time', '')}
결과: {summary.get('result', '')}
"""
    
    def analyze_image(
        self, 
        image_path: str,
        case_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """이미지 분석 실행"""
        path = Path(image_path)
        
        if not path.exists():
            return f"이미지 파일을 찾을 수 없습니다: {image_path}"
        
        # 1. 메타데이터 추출
        meta_text = self.get_image_meta(path)
        
        # 2. 사건 컨텍스트 생성
        case_context_text = self.build_case_context(case_context)
        
        # 3. 이미지 → base64
        data_url = self.image_to_data_url(path)
        
        # 4. GPT Vision 분석
        full_text = (
            self.FORENSIC_PROMPT
            + case_context_text
            + "\n[사진 메타]\n"
            + meta_text
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.settings.VISION_MODEL,
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
        
        except Exception as e:
            return f"이미지 분석 실패: {str(e)}"
    
    def analyze(
        self,
        file_id: str,
        file_path: str,
        case_context: Optional[Dict[str, Any]] = None
    ) -> ImageAnalysisResponse:
        """이미지 분석 전체 프로세스"""
        analysis_id = str(uuid.uuid4())
        
        try:
            result_text = self.analyze_image(file_path, case_context)
            
            if "실패" in result_text or "찾을 수 없습니다" in result_text:
                status = "FAILED"
            else:
                status = "COMPLETED"
        
        except Exception as e:
            result_text = f"분석 중 오류 발생: {str(e)}"
            status = "FAILED"
        
        return ImageAnalysisResponse(
            analysis_id=analysis_id,
            file_id=file_id,
            analysis_type="IMG",
            status=status,
            result_data=result_text,
            created_at=datetime.now(timezone.utc)
        )
