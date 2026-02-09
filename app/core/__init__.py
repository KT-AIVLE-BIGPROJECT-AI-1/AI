# app/core/__init__.py

from .embeddings import (
    get_criminal_law_rag,
    get_precedent_index,
    initialize_embeddings,
    search_criminal_law,
    search_precedents
)

from .moleg_api import (
    search_precedent_by_case_number
)

__all__ = [
    "get_criminal_law_rag",
    "get_precedent_index",
    "initialize_embeddings",
    "search_criminal_law",
    "search_precedents",
    "search_precedent_by_case_number"
]