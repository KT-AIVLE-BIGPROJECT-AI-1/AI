import os
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer
from app.config import PRECEDENT_CSV_PATH, PRECEDENT_EMBEDDING_CACHE

class PrecedentIndex:
    def __init__(self):
        self.model = SentenceTransformer("snunlp/KR-SBERT-V40K-klueNLI-augSTS")
        self.pool_df = None
        self.embeddings = None

    def load_precedent_csv(self):
        df = pd.read_csv(
            PRECEDENT_CSV_PATH,
            sep=",",
            skiprows=1,
            header=None,
            encoding="utf-8"
        )

        df.columns = [
            '순번', "precedent_id", "title", "법원",
            '사건 유형', '판결 유형', "선고일자"
        ]

        # 형사 판례만 필터링
        pool_df = df[df["판결 유형"] == "형사"].reset_index(drop=True)

        print(f"총 판례: {len(df):,}")
        print(f"형사 판례: {len(pool_df):,}")

        self.pool_df = pool_df

    def build_embeddings(self):
        titles = self.pool_df["title"].astype(str).tolist()
        print("📊 판례 제목 임베딩 생성 중...")
        self.embeddings = self.model.encode(
            titles,
            convert_to_tensor=True,
            show_progress_bar=True
        )

    def save_cache(self):
        torch.save({
            "embeddings": self.embeddings,
            "pool_df": self.pool_df
        }, PRECEDENT_EMBEDDING_CACHE)
        print("💾 판례 임베딩 캐시 저장 완료")

    def load_cache(self):
        data = torch.load(
            PRECEDENT_EMBEDDING_CACHE,
            weights_only=False   # ⭐
        )
        self.embeddings = data["embeddings"]
        self.pool_df = data["pool_df"]
        print("📂 판례 임베딩 캐시 로드 완료")


    def init_index(self):
        if os.path.exists(PRECEDENT_EMBEDDING_CACHE):
            print("✅ 기존 판례 임베딩 로드")
            self.load_cache()
        else:
            print("⚠️ 판례 임베딩 없음 → 새로 생성")
            self.load_precedent_csv()
            self.build_embeddings()
            self.save_cache()

    def search_similar(self, query: str, top_k: int = 5):
        query_vec = self.model.encode(query, convert_to_tensor=True)
        similarities = torch.nn.functional.cosine_similarity(
            query_vec, self.embeddings
        )

        top_indices = similarities.topk(top_k).indices.tolist()

        results = []
        for idx in top_indices:
            row = self.pool_df.iloc[idx]
            results.append({
                "precedent_id": str(row["precedent_id"]),
                "title": row["title"],
                "court": row["법원"],
                "decision_date": row["선고일자"],
                "similarity": float(similarities[idx])
            })
        return results