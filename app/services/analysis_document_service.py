"""
문서 분석 서비스 (DocumentAnalyzerV3 기반)
"""
from pathlib import Path
from typing import Dict, Any, Optional
import uuid
from datetime import datetime, timezone
from openai import OpenAI
import pdfplumber
from docx import Document as DocxDocument
import openpyxl

from app.config import get_settings
from app.models.analysis_document_schema import (
    DocumentAnalysisResponse, 
    AnalysisStatus, 
    AnalysisType
)


class DocumentAnalysisService:
    """문서 분석 서비스"""
    
    FORENSIC_PROMPT = """당신은 수사 보조 문서 분석 담당자입니다.

아래에는 사건 개요와 문서가 제공됩니다.

문서를 정밀하게 분석하여, 다음 항목을 모두 포함한 종합 보고서를 작성하십시오:

1. 문서의 목적 및 작성 배경
2. 주요 내용 요약
   - 핵심 사실관계
   - 시간/장소/인물 정보
   - 수치/금액/증거 정보
3. 사건 개요와의 직접적 연관성

절대 규칙:
- 문서에 명시된 정보만 사용
- 추정이나 추론 금지
- 객관적이고 사실적으로 기술
- 전문적인 수사보고서 문체 사용
- 2~4개 문단으로 작성 (각 문단 3~5문장)

[사건 정보]
"""
    
    def __init__(self):
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.OPENAI_API_KEY)
    
    def extract_text_from_file(self, file_path: Path) -> str:
        """파일에서 텍스트 추출"""
        ext = file_path.suffix.lower()
        
        try:
            if ext == '.pdf':
                return self._extract_from_pdf(file_path)
            elif ext == '.docx':
                return self._extract_from_docx(file_path)
            elif ext in ['.xlsx', '.xls']:
                return self._extract_from_excel(file_path)
            elif ext == '.txt':
                return self._extract_from_txt(file_path)
            else:
                return f"지원하지 않는 파일 형식: {ext}"
        except Exception as e:
            return f"텍스트 추출 실패: {str(e)}"
    
    def _extract_from_pdf(self, path: Path) -> str:
        """PDF에서 텍스트 추출"""
        text_parts = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        return "\n\n".join(text_parts)
    
    def _extract_from_docx(self, path: Path) -> str:
        """DOCX에서 텍스트 추출"""
        doc = DocxDocument(path)
        return "\n\n".join([para.text for para in doc.paragraphs if para.text.strip()])
    
    def _extract_from_excel(self, path: Path) -> str:
        """Excel에서 텍스트 추출"""
        wb = openpyxl.load_workbook(path, data_only=True)
        text_parts = []
        
        for sheet in wb.worksheets:
            text_parts.append(f"[Sheet: {sheet.title}]")
            for row in sheet.iter_rows(values_only=True):
                row_text = "\t".join([str(cell) if cell is not None else "" for cell in row])
                if row_text.strip():
                    text_parts.append(row_text)
        
        return "\n".join(text_parts)
    
    def _extract_from_txt(self, path: Path) -> str:
        """TXT에서 텍스트 추출"""
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    
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
    
    def analyze_document(
        self, 
        file_path: str, 
        case_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """문서 분석 실행"""
        path = Path(file_path)
        
        # 1. 텍스트 추출
        doc_text = self.extract_text_from_file(path)
        
        if not doc_text or "실패" in doc_text or "지원하지 않는" in doc_text:
            return doc_text
        
        # 2. 사건 컨텍스트 생성
        case_context_text = self.build_case_context(case_context)
        
        # 3. GPT 분석
        full_prompt = (
            self.FORENSIC_PROMPT 
            + case_context_text 
            + "\n[문서 내용]\n" 
            + doc_text
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.settings.GPT_MODEL,
                messages=[{"role": "user", "content": full_prompt}],
                temperature=0.0
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            return f"GPT 분석 실패: {str(e)}"
    
    def analyze(
        self, 
        file_id: str,
        file_path: str,
        case_context: Optional[Dict[str, Any]] = None
    ) -> DocumentAnalysisResponse:
        """문서 분석 전체 프로세스"""
        analysis_id = str(uuid.uuid4())
        
        # 분석 실행
        try:
            result_text = self.analyze_document(file_path, case_context)
            status = AnalysisStatus.COMPLETED
            
            if "실패" in result_text or "오류" in result_text:
                status = AnalysisStatus.FAILED
        
        except Exception as e:
            result_text = f"분석 중 오류 발생: {str(e)}"
            status = AnalysisStatus.FAILED
        
        return DocumentAnalysisResponse(
            analysis_id=analysis_id,
            file_id=file_id,
            analysis_type=AnalysisType.DOC,
            status=status,
            result_data=result_text,
            created_at=datetime.now(timezone.utc)
        )
