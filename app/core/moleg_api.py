# app/core/moleg_api.py

import os
import re
import json
import subprocess
import xml.etree.ElementTree as ET
from typing import Dict, Any


# LAW_API_KEY 로드
LAW_API_KEY = os.environ.get("LAW_API_KEY", "")
if not LAW_API_KEY:
    print("⚠️ LAW_API_KEY가 설정되지 않았습니다. 판례 전문 조회 기능이 제한됩니다.")
else:
    print(f"✅ LAW_API_KEY 로드 완료")


def parse_precedent_xml_struct(xml_text: str) -> Dict[str, Any]:
    """법제처 판례 XML을 파싱하여 구조화된 데이터 반환"""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return {"raw": xml_text, "precedent_decision_date": None}

    def get_text(tag):
        elem = root.find(f".//{tag}")
        return elem.text.strip() if elem is not None and elem.text else ""

    # 선고일자 파싱 (예: "20220428" → "2022-04-28")
    date_elem = root.find(".//선고일자")
    if date_elem is not None and date_elem.text:
        raw = date_elem.text.strip()
        if len(raw) == 8:
            precedent_decision_date = f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
        else:
            precedent_decision_date = raw
    else:
        precedent_decision_date = None

    return {
        "판시사항": get_text("판시사항"),
        "판결요지": get_text("판결요지"),
        "참조조문": get_text("참조조문"),
        "참조판례": get_text("참조판례"),
        "판례내용": get_text("판례내용"),
        "precedent_decision_date": precedent_decision_date
    }


def fetch_precedent_body_by_curl(case_id: str) -> Dict[str, Any]:
    """법제처 API를 통해 판례 전문 XML 조회"""
    case_id = int(case_id)

    cmd = [
        "curl", "-sS",
        "-H", "User-Agent: Mozilla/5.0",
        f"https://www.law.go.kr/DRF/lawService.do?OC={LAW_API_KEY}&target=prec&type=XML&ID={case_id}"
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return parse_precedent_xml_struct(result.stdout)
    except subprocess.TimeoutExpired:
        print(f"   ⚠️ API 타임아웃 (case_id={case_id})")
        return {"precedent_decision_date": None}
    except Exception as e:
        print(f"   ⚠️ API 호출 실패 (case_id={case_id}): {e}")
        return {"precedent_decision_date": None}


def search_precedent_by_case_number(case_no: str) -> str:
    """
    판례 번호로 판례 전문 조회
    
    Args:
        case_no: 판례 번호 (예: "200012345")
    
    Returns:
        판례 전문 텍스트 (판시사항 + 판결요지 + 판례내용)
    """
    if not LAW_API_KEY:
        return "법제처 API 키가 설정되지 않았습니다."
    
    try:
        result = fetch_precedent_body_by_curl(case_no)
        
        # 전문 조합
        parts = []
        
        if result.get("판시사항"):
            parts.append(f"[판시사항]\n{result['판시사항']}")
        
        if result.get("판결요지"):
            parts.append(f"\n[판결요지]\n{result['판결요지']}")
        
        if result.get("판례내용"):
            parts.append(f"\n[판례내용]\n{result['판례내용']}")
        
        if parts:
            return "\n\n".join(parts)
        else:
            return "판례 전문 조회 실패"
    
    except Exception as e:
        print(f"   ❌ 판례 조회 오류: {e}")
        return f"오류 발생: {str(e)}"