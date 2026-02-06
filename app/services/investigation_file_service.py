"""
파일 업로드 및 분류 서비스
"""
from pathlib import Path
from typing import List, Dict, Any
import uuid
import shutil
from datetime import datetime, timezone
from fastapi import UploadFile

from app.config import get_settings, PathManager
from app.models.investigation_file_schema import (
    FileType,
    InvestigateFileResponse
)


class FileClassifier:
    """파일 타입 분류기"""
    
    DOCUMENT_EXTS = {".pdf", ".docx", ".xlsx", ".xls", ".txt", ".log", ".csv"}
    IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp", ".gif"}
    VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv"}
    AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"}
    
    @classmethod
    def get_file_type(cls, filename: str) -> FileType:
        """파일 확장자로 타입 판별"""
        ext = Path(filename).suffix.lower()
        
        if ext in cls.DOCUMENT_EXTS:
            return FileType.DOCUMENT
        elif ext in cls.IMAGE_EXTS:
            return FileType.IMAGE
        elif ext in cls.VIDEO_EXTS:
            return FileType.VIDEO
        elif ext in cls.AUDIO_EXTS:
            return FileType.AUDIO
        else:
            return FileType.DOCUMENT  # 기본값


class InvestigationFileService:
    """파일 업로드 및 관리 서비스"""
    
    def __init__(self):
        self.settings = get_settings()
        self.path_manager = PathManager()
    
    async def upload_file(
        self,
        case_id: str,
        file: UploadFile
    ) -> InvestigateFileResponse:
        """단일 파일 업로드"""
        # 파일 ID 생성
        file_id = str(uuid.uuid4())
        
        # 원본 파일명
        origin_name = file.filename
        
        # 파일 타입 자동 판별
        file_type = FileClassifier.get_file_type(origin_name)
        
        # 저장 경로 생성 (확장자 유지)
        ext = Path(origin_name).suffix
        file_path = self.path_manager.get_upload_path(f"{file_id}{ext}")
        
        # 파일 저장
        try:
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            
            file_size = file_path.stat().st_size
        
        except Exception as e:
            raise Exception(f"파일 저장 실패: {str(e)}")
        
        return InvestigateFileResponse(
            file_id=file_id,
            case_id=case_id,
            origin_name=origin_name,
            file_path=str(file_path),
            file_type=file_type,
            file_size=file_size,
            created_at=datetime.now(timezone.utc)
        )
    
    async def upload_files(
        self,
        case_id: str,
        files: List[UploadFile]
    ) -> List[InvestigateFileResponse]:
        """배치 파일 업로드"""
        results = []
        
        for file in files:
            try:
                result = await self.upload_file(case_id, file)
                results.append(result)
            except Exception as e:
                print(f"⚠️ 파일 업로드 실패 ({file.filename}): {e}")
                continue
        
        return results
    
    def classify_file(self, filename: str) -> FileType:
        """파일 타입 분류"""
        return FileClassifier.get_file_type(filename)
