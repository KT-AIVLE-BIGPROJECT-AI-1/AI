import tempfile
import requests
from pathlib import Path

def download_presigned_to_temp(url: str, suffix: str = "") -> Path:
    """
    presigned_url 또는 일반 URL을 받아
    임시 파일로 다운로드 후 경로(Path)를 반환
    """

    # 임시 파일 생성
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_path = Path(tmp.name)
    tmp.close()

    # 파일 다운로드
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()

    with open(tmp_path, "wb") as f:
        f.write(resp.content)

    return tmp_path
