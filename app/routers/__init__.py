# app/routers/__init__.py

from .cases import router as cases_router
from .legal_criteria import router as legal_criteria_router
from .criteria_evaluation import router as criteria_evaluation_router
from .investigation_files import router as investigation_files_router
from .analysis_callback import router as analysis_callback_router
from .analysis_final import router as analysis_final_router
from .report_interim import router as report_interim_router
from .report_final import router as report_final_router
from .report_decision import router as report_decision_router
from .chat import router as chat_router
from .reports import router as reports_router

__all__ = [
    "cases_router",
    "legal_criteria_router",
    "criteria_evaluation_router",
    "investigation_files_router",
    "analysis_callback_router",
    "analysis_final_router",
    "report_interim_router",
    "report_final_router",
    "report_decision_router",
    "chat_router",
    "reports_router",
]