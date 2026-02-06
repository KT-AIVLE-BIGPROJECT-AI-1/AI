"""
ChromaDB 벡터 저장소 관리
"""
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import get_settings
from app.core.embeddings import get_embedding_manager


class VectorStore:
    """ChromaDB 벡터 저장소 관리 클래스"""
    
    def __init__(self):
        self.settings = get_settings()
        self.embedding_manager = get_embedding_manager()
        
        # ChromaDB 클라이언트 초기화
        self.client = chromadb.PersistentClient(
            path=str(self.settings.CHROMA_PERSIST_DIR),
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        
        # 컬렉션 초기화
        self._init_collections()
    
    def _init_collections(self):
        """벡터 DB 컬렉션 초기화"""
        # 형법 컬렉션
        self.criminal_law_collection = self.client.get_or_create_collection(
            name="criminal_law",
            metadata={"description": "형법 조문 임베딩"}
        )
        
        # 판례 컬렉션
        self.precedents_collection = self.client.get_or_create_collection(
            name="precedents",
            metadata={"description": "판례 임베딩"}
        )
    
    def initialize_criminal_law(self):
        """형법 데이터 초기 임베딩"""
        # 이미 데이터가 있으면 스킵
        if self.criminal_law_collection.count() > 0:
            print(f"✅ 형법 컬렉션 이미 초기화됨 ({self.criminal_law_collection.count()}개 문서)")
            return
        
        chunks = self.embedding_manager.load_criminal_law()
        if not chunks:
            print("⚠️ 형법 데이터 없음")
            return
        
        print(f"🔄 형법 {len(chunks)}개 청크 임베딩 중...")
        
        # 배치로 임베딩 생성
        embeddings = self.embedding_manager.create_batch_embeddings(chunks)
        
        # ChromaDB에 추가
        self.criminal_law_collection.add(
            documents=chunks,
            embeddings=embeddings,
            ids=[f"law_{i}" for i in range(len(chunks))],
            metadatas=[{"type": "criminal_law", "chunk_id": i} for i in range(len(chunks))]
        )
        
        print(f"✅ 형법 임베딩 완료: {len(chunks)}개")
    
    def initialize_precedents(self):
        """판례 데이터 초기 임베딩"""
        # 이미 데이터가 있으면 스킵
        if self.precedents_collection.count() > 0:
            print(f"✅ 판례 컬렉션 이미 초기화됨 ({self.precedents_collection.count()}개 문서)")
            return
        
        precedents = self.embedding_manager.load_precedents()
        if not precedents:
            print("⚠️ 판례 데이터 없음")
            return
        
        print(f"🔄 판례 {len(precedents)}개 임베딩 중...")
        
        # 판례 텍스트 생성
        texts = []
        metadatas = []
        for i, prec in enumerate(precedents):
            text = f"{prec.get('title', '')} {prec.get('summary', '')} {prec.get('content', '')}"
            texts.append(text)
            metadatas.append({
                "type": "precedent",
                "case_number": prec.get("case_number", ""),
                "court": prec.get("court", ""),
                "date": prec.get("date", "")
            })
        
        # 배치로 임베딩 생성
        embeddings = self.embedding_manager.create_batch_embeddings(texts)
        
        # ChromaDB에 추가
        self.precedents_collection.add(
            documents=texts,
            embeddings=embeddings,
            ids=[f"prec_{i}" for i in range(len(texts))],
            metadatas=metadatas
        )
        
        print(f"✅ 판례 임베딩 완료: {len(precedents)}개")
    
    def search_criminal_law(
        self, 
        query: str, 
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """형법 검색"""
        query_embedding = self.embedding_manager.create_embedding(query)
        
        results = self.criminal_law_collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        return self._format_results(results)
    
    def search_precedents(
        self, 
        query: str, 
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """판례 검색"""
        query_embedding = self.embedding_manager.create_embedding(query)
        
        results = self.precedents_collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        return self._format_results(results)
    
    def _format_results(self, results: Dict) -> List[Dict[str, Any]]:
        """검색 결과 포맷팅"""
        formatted = []
        
        if not results.get('documents') or not results['documents'][0]:
            return formatted
        
        for i, doc in enumerate(results['documents'][0]):
            formatted.append({
                'document': doc,
                'metadata': results['metadatas'][0][i] if results.get('metadatas') else {},
                'distance': results['distances'][0][i] if results.get('distances') else 0.0
            })
        
        return formatted


# 싱글톤 인스턴스
_vector_store = None

def get_vector_store() -> VectorStore:
    """VectorStore 싱글톤 인스턴스 반환"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
