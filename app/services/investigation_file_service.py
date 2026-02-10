# app/services/investigation_file_service.py

from app.models.investigation_file_schema import (
    InvestigationFilesRequest,
    InvestigationFilesResponse,
    AnalysisTarget
)
from app.services.analysis_callback_service import AnalysisCallbackService


class InvestigationFileService:
    
    @staticmethod
    def schedule_analysis(request: InvestigationFilesRequest) -> InvestigationFilesResponse:
        """
        조사 파일 분석 작업 스케줄링
        이미 업로드된 파일들에 대한 분석 작업 등록
        """
        print("\n" + "=" * 70)
        print("📂 조사 파일 분석 작업 등록")
        print("=" * 70)
        print(f"사건: {request.case_detail.title} ({request.case_detail.case_id})")
        print(f"파일 수: {len(request.investigation_files)}개")
        print(f"법리 기준: {len(request.legal_criteria)}개")
        
        targets = []
        
        # 콜백 서비스에 등록할 파일 목록
        callback_files = []
        
        for file_info in request.investigation_files:
            target = AnalysisTarget(
                origin_name=file_info.origin_name,
                file_type=file_info.file_type
            )
            
            targets.append(target)
            
            # 콜백 서비스 등록용 데이터
            callback_files.append({
                "analysis_id": file_info.analysis_id,
                "file_type": file_info.file_type,
                "origin_name": file_info.origin_name
            })
            
            print(f"  [{file_info.analysis_id}] {file_info.origin_name} ({file_info.file_type})")
        
        # 콜백 서비스에 파일 등록
        case_detail_dict = request.case_detail.model_dump()
        AnalysisCallbackService.register_investigation_files(
            case_id=request.case_detail.case_id,
            case_detail=case_detail_dict,
            files=callback_files
        )
        
        print("=" * 70)
        print(f"✅ {len(targets)}개 파일 분석 대기 (PENDING)")
        print("=" * 70)
        
        return InvestigationFilesResponse(
            status="PENDING",
            targets=targets
        )