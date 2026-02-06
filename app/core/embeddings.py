"""
형법 및 판례 임베딩 초기화 및 관리
"""
import json
from pathlib import Path
from typing import List, Dict, Any
from openai import OpenAI
import pdfplumber

from app.config import get_settings


class EmbeddingManager:
    """임베딩 생성 및 관리 클래스"""
    
    def __init__(self):
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.OPENAI_API_KEY)
        self._criminal_law_chunks: List[str] = []
        self._precedents: List[Dict[str, Any]] = []
    
    def load_criminal_law(self) -> List[str]:
        """형법 PDF를 청크로 분할하여 로드"""
        if self._criminal_law_chunks:
            return self._criminal_law_chunks
        
        pdf_path = self.settings.CRIMINAL_LAW_PDF
        if not pdf_path.exists():
            print(f"⚠️ 형법 PDF 파일을 찾을 수 없습니다: {pdf_path}")
            return []
        
        chunks = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        # 조문별로 분할 (간단한 예시)
                        articles = text.split("제")
                        for article in articles:
                            if len(article.strip()) > 50:  # 너무 짧은 텍스트 제외
                                chunks.append("제" + article.strip())
        except Exception as e:
            print(f"❌ 형법 PDF 로드 실패: {e}")
            return []
        
        self._criminal_law_chunks = chunks
        return chunks
    
    def load_precedents(self) -> List[Dict[str, Any]]:
        """판례 JSON 로드"""
        if self._precedents:
            return self._precedents
        
        json_path = self.settings.PRECEDENTS_JSON
        if not json_path.exists():
            print(f"⚠️ 판례 JSON 파일을 찾을 수 없습니다: {json_path}")
            return []
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                self._precedents = json.load(f)
        except Exception as e:
            print(f"❌ 판례 JSON 로드 실패: {e}")
            return []
        
        return self._precedents
    
    def create_embedding(self, text: str) -> List[float]:
        """텍스트를 임베딩 벡터로 변환"""
        try:
            response = self.client.embeddings.create(
                model=self.settings.EMBEDDING_MODEL,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"❌ 임베딩 생성 실패: {e}")
            return []
    
    def create_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """여러 텍스트를 배치로 임베딩"""
        try:
            response = self.client.embeddings.create(
                model=self.settings.EMBEDDING_MODEL,
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            print(f"❌ 배치 임베딩 생성 실패: {e}")
            return []


# 싱글톤 인스턴스
_embedding_manager = None

def get_embedding_manager() -> EmbeddingManager:
    """EmbeddingManager 싱글톤 인스턴스 반환"""
    global _embedding_manager
    if _embedding_manager is None:
        _embedding_manager = EmbeddingManager()
    return _embedding_manager
