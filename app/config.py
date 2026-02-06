import os
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

CRIMINAL_LAW_PATH = DATA_DIR / "criminal_law.pdf"
RAG_INDEX_PATH = DATA_DIR / "criminal_law_rag_index.pkl"

PRECEDENT_CSV_PATH = DATA_DIR / "판례목록.csv"
PRECEDENT_EMBEDDING_CACHE = DATA_DIR / "precedent_embeddings.pt"

load_dotenv(BASE_DIR / ".env")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY가 없습니다.")


