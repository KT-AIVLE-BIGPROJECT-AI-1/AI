# app/models/case_schema.py

from pydantic import BaseModel, Field
from typing import Optional


class CaseRequest(BaseModel):
    title: str
    description: str
    type: str
    occurred_at: str
    location: str


class CaseSummary(BaseModel):
    action: str
    object: str
    interaction: str
    place: str
    time: str
    result: str


class CaseResponse(BaseModel):
    case_id: str
    title: str
    description: str
    summary: Optional[CaseSummary] = None
    type: str
    status: str = "OPEN"
    occurred_at: str
    location: str
    created_at: str
    updated_at: str


class CaseSummaryResponse(BaseModel):
    summary: CaseSummary