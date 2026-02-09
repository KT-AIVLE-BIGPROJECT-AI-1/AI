# app/core/embeddings.py

import os
import re
import pickle
import pdfplumber
import numpy as np
import pandas as pd
import torch
from typing import List, Dict, Any
from pathlib import Path
from openai import OpenAI
from transformers import AutoModel, AutoTokenizer
from app.config import settings

# HuggingFace Hub 로그인
if settings.HUGGINGFACEHUB_API_TOKEN:
    os.environ["HF_TOKEN"] = settings.HUGGINGFACEHUB_API_TOKEN

# OpenAI 클라이언트
client = OpenAI(api_key=settings.OPENAI_API_KEY)

# ============================================================
# 전역 변수
# ============================================================
criminal_law_rag = None
precedent_index = None


# ============================================================
# Getter 함수 (import 문제 해결)
# ============================================================

def get_criminal_law_rag():
    """형법 RAG 인스턴스 반환"""
    global criminal_law_rag
    if criminal_law_rag is None:
        raise RuntimeError("criminal_law_rag가 초기화되지 않았습니다. initialize_embeddings()를 먼저 호출하세요.")
    return criminal_law_rag


def get_precedent_index():
    """판례 인덱스 인스턴스 반환"""
    global precedent_index
    if precedent_index is None:
        raise RuntimeError("precedent_index가 초기화되지 않았습니다. initialize_embeddings()를 먼저 호출하세요.")
    return precedent_index


# ============================================================
# CriminalLawRAG (AI.ipynb와 100% 동일)
# ============================================================

class CriminalLawRAG:
    """형법 PDF 기반 RAG 시스템"""
    
    def __init__(self, pdf_path: str, client):
        self.pdf_path = pdf_path
        self.client = client
        self.chunks = []
        self.embeddings = None
    
    def load_and_chunk_pdf(self) -> List[Dict[str, str]]:
        """PDF를 로드하고 조항 단위로 청크 분할"""
        print(f"\n📄 PDF 로드 중: {self.pdf_path}")
        
        full_text = ""
        with pdfplumber.open(self.pdf_path) as pdf:
            total_pages = len(pdf.pages)
            for i, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
                
                if i % 10 == 0:
                    print(f"   진행: {i}/{total_pages} 페이지")
        
        print(f"✅ PDF 로드 완료 ({total_pages}페이지)")
        
        # 조항 단위 분할
        chunks = self._split_by_articles(full_text)
        print(f"✅ {len(chunks)}개 청크 생성")
        
        return chunks
    
    def _split_by_articles(self, text: str) -> List[Dict[str, str]]:
        """'제X조' 패턴으로 조항 분할"""
        pattern = r'(제\s*\d+\s*조(?:의\d+)?)'
        parts = re.split(pattern, text)
        
        chunks = []
        current_article = None
        current_text = ""
        
        for part in parts:
            if re.match(pattern, part):
                if current_article and len(current_text.strip()) > 20:
                    chunks.append({
                        "article": current_article,
                        "text": current_text.strip()
                    })
                current_article = part.strip()
                current_text = ""
            else:
                current_text += part
        
        if current_article and len(current_text.strip()) > 20:
            chunks.append({
                "article": current_article,
                "text": current_text.strip()
            })
        
        return chunks
    
    def create_embeddings(self, chunks: List[Dict[str, str]]) -> np.ndarray:
        """OpenAI 임베딩 생성"""
        print(f"\n🔢 임베딩 생성 중... ({len(chunks)}개 청크)")
        
        all_embeddings = []
        batch_size = 100
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            texts = [f"{c['article']}: {c['text'][:500]}" for c in batch]
            
            response = self.client.embeddings.create(
                model="text-embedding-3-small",
                input=texts
            )
            
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)
            
            print(f"   진행: {min(i+batch_size, len(chunks))}/{len(chunks)}")
        
        print(f"✅ 임베딩 생성 완료")
        return np.array(all_embeddings)
    
    def build_index(self):
        """인덱스 구축"""
        self.chunks = self.load_and_chunk_pdf()
        self.embeddings = self.create_embeddings(self.chunks)
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """쿼리로 관련 조문 검색"""
        if self.embeddings is None:
            raise RuntimeError("인덱스가 구축되지 않았습니다.")
        
        # 쿼리 임베딩
        response = self.client.embeddings.create(
            model="text-embedding-3-small",
            input=[query]
        )
        query_embedding = np.array(response.data[0].embedding)
        
        # 코사인 유사도
        similarities = np.dot(self.embeddings, query_embedding)
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        results = []
        for idx in top_indices:
            results.append({
                "article": self.chunks[idx]["article"],
                "text": self.chunks[idx]["text"],
                "score": float(similarities[idx])
            })
        
        return results
    
    def save_index(self, save_path: str):
        """인덱스 저장"""
        data = {
            "chunks": self.chunks,
            "embeddings": self.embeddings
        }
        with open(save_path, "wb") as f:
            pickle.dump(data, f)
        print(f"💾 RAG 인덱스 저장: {save_path}")
    
    def load_index(self, load_path: str):
        """인덱스 로드"""
        with open(load_path, "rb") as f:
            data = pickle.load(f)
        
        self.chunks = data["chunks"]
        self.embeddings = data["embeddings"]
        print(f"📂 RAG 인덱스 로드 완료 ({len(self.chunks)}개 청크)")


# ============================================================
# PrecedentIndex (AI.ipynb와 100% 동일)
# ============================================================

class PrecedentIndex:
    """판례 임베딩 시스템"""
    
    def __init__(self, csv_path: str, model_name: str = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"):
        self.csv_path = csv_path
        self.model_name = model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # HuggingFace 토큰 사용 (환경변수에서 자동 감지)
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            token=os.getenv("HF_TOKEN")
        )
        self.model = AutoModel.from_pretrained(
            model_name,
            token=os.getenv("HF_TOKEN")
        ).to(self.device)
        self.model.eval()
        
        self.pool_df = None
        self.embeddings = None
    
    def load_precedent_csv(self) -> pd.DataFrame:
        """CSV 로드 및 형사 판례 필터링 (AI.ipynb와 100% 동일)"""
        df = pd.read_csv(
            self.csv_path,
            sep=",",
            skiprows=1,      # ✅ 첫 줄 건너뛰기
            header=None,     # ✅ 헤더 없음
            encoding="utf-8"
        )
        
        # ✅ 컬럼명 수동 지정
        df.columns = [
            '순번', "precedent_id", "title", "법원",
            '사건 유형', '판결 유형', "선고일자"
        ]
        
        # ✅ 형사 판례만 필터링
        pool_df = df[df["판결 유형"] == "형사"].reset_index(drop=True)
        
        print(f"총 판례: {len(df):,}")
        print(f"형사 판례: {len(pool_df):,}")
        
        return pool_df
    
    def build_embeddings(self, df: pd.DataFrame) -> torch.Tensor:
        """판례 임베딩 생성"""
        print(f"\n🔢 판례 임베딩 생성 중... ({len(df)}개)")
        
        embeddings_list = []
        batch_size = 32
        
        for i in range(0, len(df), batch_size):
            batch_titles = df['title'].iloc[i:i+batch_size].tolist()
            
            inputs = self.tokenizer(
                batch_titles,
                padding=True,
                truncation=True,
                max_length=128,
                return_tensors="pt"
            ).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                batch_embeddings = outputs.last_hidden_state[:, 0, :]
                batch_embeddings = torch.nn.functional.normalize(batch_embeddings, p=2, dim=1)
            
            embeddings_list.append(batch_embeddings.cpu())
            
            if (i + batch_size) % 100 == 0:
                print(f"   진행: {min(i+batch_size, len(df))}/{len(df)}")
        
        embeddings = torch.cat(embeddings_list, dim=0)
        print(f"✅ 판례 임베딩 생성 완료")
        
        return embeddings
    
    def save_cache(self, cache_path: str):
        """임베딩 캐시 저장"""
        torch.save({
            "embeddings": self.embeddings,
            "pool_df": self.pool_df
        }, cache_path)
        print(f"💾 판례 임베딩 캐시 저장: {cache_path}")
    
    def load_cache(self, cache_path: str):
        """임베딩 캐시 로드"""
        # ✅ PyTorch 2.6+ 호환: weights_only=False 추가
        data = torch.load(cache_path, map_location=self.device, weights_only=False)
        self.embeddings = data["embeddings"]
        self.pool_df = data["pool_df"]
        print(f"📂 판례 임베딩 캐시 로드 완료")
    
    def init_index(self, cache_path: str):
        """인덱스 초기화 (캐시 우선)"""
        if os.path.exists(cache_path):
            print("✅ 기존 판례 임베딩 로드")
            self.load_cache(cache_path)
        else:
            print("📊 판례 임베딩 새로 생성")
            self.pool_df = self.load_precedent_csv()
            self.embeddings = self.build_embeddings(self.pool_df)
            self.save_cache(cache_path)
    
    def search_similar_by_title(self, query: str, top_k: int = 5) -> List[Dict]:
        """사건명 유사도 검색"""
        if self.embeddings is None:
            raise RuntimeError("인덱스가 초기화되지 않았습니다.")
        
        # 쿼리 임베딩
        inputs = self.tokenizer(
            [query],
            padding=True,
            truncation=True,
            max_length=128,
            return_tensors="pt"
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            query_embedding = outputs.last_hidden_state[:, 0, :]
            query_embedding = torch.nn.functional.normalize(query_embedding, p=2, dim=1)
        
        # 코사인 유사도
        similarities = torch.mm(query_embedding, self.embeddings.T).squeeze()
        top_indices = torch.argsort(similarities, descending=True)[:top_k]
        
        results = []
        for idx in top_indices:
            idx = idx.item()
            row = self.pool_df.iloc[idx]
            results.append({
                "precedent_id": str(row['precedent_id']),
                "title": row['title'],
                "decision_date": row['선고일자'],
                "score": float(similarities[idx])
            })
        
        return results


# ============================================================
# 초기화 함수
# ============================================================

def initialize_embeddings():
    """임베딩 시스템 초기화"""
    global criminal_law_rag, precedent_index
    
    print("\n" + "=" * 70)
    print("🚀 임베딩 시스템 초기화")
    print("=" * 70)
    
    # ✅ settings에서 경로 가져오기
    CRIMINAL_LAW_PATH = str(settings.CRIMINAL_LAW_PDF)
    RAG_INDEX_PATH = str(settings.RAG_INDEX_PATH)
    PRECEDENT_CSV_PATH = str(settings.PRECEDENT_CSV)
    PRECEDENT_CACHE_PATH = str(settings.PRECEDENT_CACHE_PATH)
    
    # ============================================================
    # 1. 형법 RAG 초기화
    # ============================================================
    print("\n📚 형법 RAG 시스템 초기화")
    
    criminal_law_rag = CriminalLawRAG(CRIMINAL_LAW_PATH, client)
    
    if os.path.exists(RAG_INDEX_PATH):
        print("✅ 기존 RAG 인덱스 발견!")
        criminal_law_rag.load_index(RAG_INDEX_PATH)
    else:
        print("📄 형법 PDF에서 새로 인덱스 구축")
        criminal_law_rag.build_index()
        criminal_law_rag.save_index(RAG_INDEX_PATH)
    
    # ============================================================
    # 2. 판례 임베딩 초기화
    # ============================================================
    print("\n📊 판례 임베딩 시스템 초기화")
    
    precedent_index = PrecedentIndex(PRECEDENT_CSV_PATH)
    precedent_index.init_index(PRECEDENT_CACHE_PATH)
    
    print("\n" + "=" * 70)
    print("✅ 임베딩 시스템 초기화 완료")
    print("=" * 70)


# ============================================================
# 헬퍼 함수
# ============================================================

def search_criminal_law(query: str, top_k: int = 5) -> List[Dict]:
    """형법 조문 검색"""
    return get_criminal_law_rag().search(query, top_k)


def search_precedents(query: str, top_k: int = 5) -> List[Dict]:
    """판례 검색"""
    return get_precedent_index().search_similar_by_title(query, top_k)