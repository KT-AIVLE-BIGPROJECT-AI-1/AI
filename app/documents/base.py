from app.models.report_schema import ReportDraftRequest

def normalize_case_context(req: ReportDraftRequest):
    c = req.case_detail
    f = req.final_analysis

    return {
        "사건명": c.title,
        "사건요약(원문)": c.summary,
        "사건설명": c.description,
        "발생일시": c.occurred_at.isoformat(),
        "발생장소": c.location,
        "사건유형": c.type,
        "현재상태": c.status,

        # 🔽 결정 기준(핵심)
        "최종결정_기준": f.recommended_decision,
        "사용자판단(참고)": req.decision_type,

        "판단요약": f.decision_summary,
        "법리요약": f.legal_issue_summary,
        "증거요약": f.evidence_sufficiency_summary,
        "잔여위험": f.remaining_risk_summary,
    }
