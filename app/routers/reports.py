from fastapi import APIRouter
from app.models.report_schema import ReportDraftRequest, ReportDraftResponse
from app.services.report_service import (
    make_interim_report,
    make_final_report,
    make_decision_report
)

router = APIRouter(prefix="/reports", tags=["reports"])

@router.post("/interim-draft", response_model=ReportDraftResponse)
def interim_draft(req: ReportDraftRequest):
    return make_interim_report(req)

@router.post("/final-draft", response_model=ReportDraftResponse)
def final_draft(req: ReportDraftRequest):
    return make_final_report(req)

@router.post("/decision-draft", response_model=ReportDraftResponse)
def decision_draft(req: ReportDraftRequest):
    return make_decision_report(req)

