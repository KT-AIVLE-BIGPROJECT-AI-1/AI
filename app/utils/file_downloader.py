# app/utils/file_downloader.py

import os
import tempfile
import httpx
from pathlib import Path
from urllib.parse import urlparse, unquote


def download_from_presigned_url(presigned_url: str, timeout: float = 120.0) -> Path:
    """
    S3 presigned URL에서 파일을 다운로드하여 임시 경로에 저장
    Returns: 다운로드된 파일의 로컬 Path
    """
    parsed = urlparse(presigned_url)
    filename = unquote(os.path.basename(parsed.path))
    if not filename:
        filename = "downloaded_file"

    tmp_dir = tempfile.mkdtemp(prefix="ai_analysis_")
    local_path = Path(tmp_dir) / filename

    print(f"   📥 파일 다운로드 중: {filename}")

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(presigned_url)
        response.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(response.content)

    file_size = local_path.stat().st_size
    print(f"   ✅ 다운로드 완료: {local_path} ({file_size:,} bytes)")
    return local_path


def cleanup_temp_file(file_path: Path):
    """임시 파일 및 디렉토리 삭제"""
    try:
        if file_path and file_path.exists():
            parent = file_path.parent
            file_path.unlink()
            if parent.exists() and str(parent).startswith(tempfile.gettempdir()):
                parent.rmdir()
            print(f"   🗑️ 임시 파일 삭제: {file_path}")
    except Exception as e:
        print(f"   ⚠️ 임시 파일 삭제 실패: {e}")