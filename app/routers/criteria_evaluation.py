from fastapi import APIRouter
from openai import OpenAI

from app.models.criteria_evaluation_schema import (
    EvaluateCriteriaRequest,
    CriteriaEvaluationResponse
)

from app.services.criteria_evaluation_service import (
    evaluate_criterion_with_single_evidence
)

router = APIRouter()
client = OpenAI()

@router.post(
    "/legal-criteria/evaluate",
    response_model=CriteriaEvaluationResponse
)
def evaluate_legal_criteria(req: EvaluateCriteriaRequest):

    # 👉 단일 증거 그대로 사용
    single_evidence = req.analysis.analysis.result_data

    # 평가할 기준 1개 선택
    first_criterion = req.legal_criteria[0]

    result = evaluate_criterion_with_single_evidence(
        client=client,
        criterion_text=first_criterion.criterion_text,
        single_evidence=single_evidence
    )

    return CriteriaEvaluationResponse(
        status=result["status"],
        reason=result["reason"],
        evidence_gap=result["evidence_gap"]
    )
