import os
import pickle
import numpy as np
import pdfplumber
from typing import List, Dict
from openai import OpenAI

class CriminalLawRAG:
    def __init__(self, client: OpenAI):
        self.client = client
        self.chunks = []
        self.embeddings = []

    def load_and_chunk_pdf(self, pdf_path: str) -> List[Dict[str, str]]:
        print("📚 형법 PDF 로드 및 청크 분할 중...")

        full_text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"

        chunks = self._split_by_articles(full_text)
        print(f"✅ {len(chunks)}개 청크로 분할 완료")
        return chunks

    def _split_by_articles(self, text: str) -> List[Dict[str, str]]:
        lines = text.split("\n")
        chunks = []
        current_chunk = []
        current_article = "서론"

        for line in lines:
            if line.strip().startswith("제") and "조" in line[:10]:
                if current_chunk:
                    chunk_text = "\n".join(current_chunk)
                    if len(chunk_text.strip()) > 20:
                        chunks.append({
                            "article": current_article,
                            "text": chunk_text.strip()
                        })

                current_article = line.strip()[:20]
                current_chunk = [line]
            else:
                current_chunk.append(line)

        if current_chunk:
            chunk_text = "\n".join(current_chunk)
            if len(chunk_text.strip()) > 20:
                chunks.append({
                    "article": current_article,
                    "text": chunk_text.strip()
                })

        return chunks

    def create_embeddings(self, chunks):
        print("\n🔢 임베딩 생성 중...")

        embeddings = []
        batch_size = 100

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            batch_texts = [chunk["text"] for chunk in batch]

            response = self.client.embeddings.create(
                model="text-embedding-3-small",
                input=batch_texts
            )

            batch_embeddings = [item.embedding for item in response.data]
            embeddings.extend(batch_embeddings)

        print(f"✅ {len(embeddings)}개 임베딩 생성 완료")
        return embeddings

    def build_index(self, pdf_path: str):
        self.chunks = self.load_and_chunk_pdf(pdf_path)
        self.embeddings = self.create_embeddings(self.chunks)
        print("✅ RAG 인덱스 구축 완료")

    def save_index(self, save_path: str):
        data = {
            "chunks": self.chunks,
            "embeddings": self.embeddings
        }
        with open(save_path, "wb") as f:
            pickle.dump(data, f)
        print(f"💾 RAG 인덱스 저장 완료: {save_path}")

    def load_index(self, load_path: str):
        print(f"📂 RAG 인덱스 로드 중: {load_path}")
        with open(load_path, "rb") as f:
            data = pickle.load(f)
        self.chunks = data["chunks"]
        self.embeddings = data["embeddings"]
        print(f"✅ RAG 인덱스 로드 완료 ({len(self.chunks)}개 청크)")

    def search(self, query: str, top_k: int = 5):
        query_response = self.client.embeddings.create(
            model="text-embedding-3-small",
            input=[query]
        )
        query_embedding = query_response.data[0].embedding

        similarities = []
        for idx, chunk_embedding in enumerate(self.embeddings):
            similarity = self._cosine_similarity(query_embedding, chunk_embedding)
            similarities.append((idx, similarity))

        similarities.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, similarity in similarities[:top_k]:
            results.append({
                "article": self.chunks[idx]["article"],
                "text": self.chunks[idx]["text"],
                "similarity": similarity
            })

        return results

    @staticmethod
    def _cosine_similarity(vec1, vec2):
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))