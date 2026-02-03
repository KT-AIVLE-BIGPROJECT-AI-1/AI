# app/law_rag.py
import os, re
import pdfplumber
from functools import lru_cache
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv

load_dotenv()

PDF_PATH = "data/형법(법률)(제21307호)(20251231).pdf"
PERSIST_DIR = "chroma_criminal_law"
EMBED_MODEL = "text-embedding-3-small"

def _split_articles(text: str):
    parts = re.split(r"(제\d+조\([^)]+\))", text)
    out = []
    for i in range(1, len(parts), 2):
        out.append(parts[i] + parts[i+1])
    return out

def _build_rag_docs_from_pdf():
    raw_text = ""
    with pdfplumber.open(PDF_PATH) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                raw_text += t + "\n"

    start = re.search(r"제1조\([^)]+\)\s*①", raw_text)
    body = raw_text[start.start():]

    articles = _split_articles(body)

    docs = []
    for a in articles:
        m = re.match(r"(제\d+조)\(([^)]+)\)", a)
        if not m: continue
        no, title = m.group(1), m.group(2)
        text = a[m.end():].strip()

        docs.append(
            Document(
                page_content=f"형법 {no} {title} {text}",
                metadata={"law":"형법","article":no,"title":title}
            )
        )
    return docs

@lru_cache(maxsize=1)
def build_criminal_law_vectordb():
    embeddings = OpenAIEmbeddings(model=EMBED_MODEL)

    if os.path.isdir(PERSIST_DIR) and os.listdir(PERSIST_DIR):
        return Chroma(persist_directory=PERSIST_DIR, embedding_function=embeddings)

    docs = _build_rag_docs_from_pdf()
    splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=150)
    split_docs = splitter.split_documents(docs)

    return Chroma.from_documents(
        documents=split_docs,
        embedding=embeddings,
        persist_directory=PERSIST_DIR
    )