# app/precedent.py
import pandas as pd
import httpx, re
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer, util
from rank_bm25 import BM25Okapi
from dotenv import load_dotenv
import os

load_dotenv()
CSV_PATH = "data/판례목록.csv"
LAW_API_KEY = os.getenv("LAW_API_KEY")
SBERT_MODEL = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"

model = SentenceTransformer(SBERT_MODEL)

def load_pool():
    df = pd.read_csv(CSV_PATH, sep=",", skiprows=1, header=None, encoding="utf-8")
    df.columns = ["순번","precedent_id","title","법원","사건 유형","판결 유형","선고일자"]
    return df[df["판결 유형"]=="형사"].reset_index(drop=True)

pool_df = load_pool()
title_emb = model.encode(pool_df["title"].astype(str).tolist(), convert_to_tensor=True)

def derive_precedent_search_keywords(case_summary, legal_issue):
    from app.llm_utils import call_llm_json
    prompt = f"""
판례 제목 검색 키워드 2~5개 생성
JSON: {{"keywords":[]}}
사건:{case_summary}
쟁점:{legal_issue}
"""
    return call_llm_json(prompt).get("keywords", [])

def search_precedents_by_title(case_summary, legal_issue, keywords, top_k=20):
    query = " ".join([legal_issue.get("issue_name",""), *keywords])
    q_emb = model.encode(query, convert_to_tensor=True)
    scores = util.cos_sim(q_emb, title_emb)[0]
    top = scores.topk(top_k)

    results=[]
    for idx in top.indices:
        i=int(idx)
        results.append({
            "precedent_id": str(pool_df.iloc[i]["precedent_id"]),
            "title": pool_df.iloc[i]["title"]
        })
    return results

def fetch_precedent_bodies(candidates, limit=10):
    bodies=[]
    for p in candidates[:limit]:
        url="https://www.law.go.kr/DRF/lawService.do"
        params={"OC":LAW_API_KEY,"target":"prec","type":"XML","ID":p["precedent_id"]}
        r=httpx.get(url,params=params,timeout=30)
        bodies.append({
            "precedent_case_no": p["precedent_id"],
            "title": p["title"],
            "body": r.text
        })
    return bodies

def bm25_rerank(precedent_bodies, case_summary, legal_issue, top_k=8):
    docs=[p["body"] for p in precedent_bodies]
    tokenized=[d.split() for d in docs]
    bm25=BM25Okapi(tokenized)
    scores=bm25.get_scores(str(case_summary).split())
    top_idx=sorted(range(len(scores)), key=lambda i:scores[i], reverse=True)[:top_k]
    return [precedent_bodies[i] for i in top_idx]