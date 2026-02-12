# app/services/report_storage_service.py
# 경찰 공식 양식에 맞춘 PDF 보고서 생성
# - INTERIM (수사보고): 범죄수사규칙 별지 제174호서식
# - FINAL (수사결과보고): 범죄수사규칙 별지 제156호서식
# - DECISION/TRANSFER (송치 결정서): 경찰수사규칙 별지 제114호서식
# - DECISION/NON_TRANSFER (불송치 결정서): 경찰수사규칙 별지 제122호서식
# - DECISION/SUSPENSION (수사중지 결정서): 경찰수사규칙 별지 제107호서식

import uuid
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image,
    HRFlowable, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def format_date():
    """날짜 포맷: YYYY.MM.DD."""
    return datetime.now().strftime("%Y.%m.%d.")


# ============================================================
# 한글 폰트 등록
# ============================================================

def register_korean_font():
    """한글 폰트 등록"""
    font_paths = [
        "app/fonts/malgun.ttf",
        "./fonts/malgun.ttf",
        "C:/Windows/Fonts/malgun.ttf",
    ]

    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont("korean_font", font_path))
                print(f"   ✅ 폰트 등록: {font_path}")
                return "korean_font"
            except Exception as e:
                print(f"   ⚠️ 폰트 등록 실패: {font_path} - {e}")
                continue

    print("   ⚠️ 기본 폰트 사용 (Helvetica)")
    return "Helvetica"


KOREAN_FONT = register_korean_font()

# Bold 폰트 등록 시도
def register_bold_font():
    """한글 Bold 폰트 등록"""
    bold_paths = [
        "app/fonts/malgunbd.ttf",
        "./fonts/malgunbd.ttf",
        "C:/Windows/Fonts/malgunbd.ttf",
    ]
    for font_path in bold_paths:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont("korean_font_bold", font_path))
                return "korean_font_bold"
            except Exception:
                continue
    return KOREAN_FONT  # Bold 없으면 일반 폰트 사용

KOREAN_FONT_BOLD = register_bold_font()

# 경찰 로고 경로 (우선순위 순으로 검색)
POLICE_LOGO_PATHS = [
    "app/images/police_logo.png",
    "./images/police_logo.png",
    "C:/Users/User/Desktop/AI_Claude_Github/images/police_logo.png",
]


def _find_police_logo() -> str:
    """사용 가능한 경찰 로고 경로를 찾아 반환"""
    for path in POLICE_LOGO_PATHS:
        if os.path.exists(path):
            print(f"   ✅ 경찰 로고 발견: {path}")
            return path
    print("   ⚠️ 경찰 로고 파일을 찾을 수 없음")
    return ""


POLICE_LOGO_PATH = _find_police_logo()


def escape_xml(text: str) -> str:
    """XML 특수문자 이스케이프"""
    if not text:
        return ""
    text = str(text)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def flatten_content(value: Any, depth: int = 0) -> str:
    """중첩된 dict/list를 서술형 텍스트로 변환"""
    if isinstance(value, str):
        return value
    elif isinstance(value, dict):
        parts = []
        for k, v in value.items():
            flat = flatten_content(v, depth + 1)
            if flat.strip():
                parts.append(flat)
        return "\n".join(parts)
    elif isinstance(value, list):
        return "\n".join(flatten_content(item, depth) for item in value)
    else:
        return str(value)


# ============================================================
# 스타일 생성 헬퍼
# ============================================================

def _make_styles():
    """공통 스타일 생성"""
    styles = getSampleStyleSheet()
    
    custom = {}
    
    # 양식번호 (좌측 상단, 9pt)
    custom['form_number'] = ParagraphStyle(
        'form_number', parent=styles['Normal'],
        fontName=KOREAN_FONT, fontSize=9, alignment=TA_LEFT
    )
    
    # 소속관서 제목 (중앙, 20pt)
    custom['org_title'] = ParagraphStyle(
        'org_title', parent=styles['Normal'],
        fontName=KOREAN_FONT_BOLD, fontSize=20, leading=28,
        alignment=TA_CENTER, spaceAfter=3*mm
    )
    
    # 날짜 (우측 정렬)
    custom['date_right'] = ParagraphStyle(
        'date_right', parent=styles['Normal'],
        fontName=KOREAN_FONT, fontSize=10, alignment=TA_RIGHT
    )
    
    # 날짜 (중앙 정렬)
    custom['date_center'] = ParagraphStyle(
        'date_center', parent=styles['Normal'],
        fontName=KOREAN_FONT, fontSize=10, alignment=TA_CENTER
    )
    
    # 문서번호+날짜 라인 (좌)
    custom['doc_number'] = ParagraphStyle(
        'doc_number', parent=styles['Normal'],
        fontName=KOREAN_FONT, fontSize=10, alignment=TA_LEFT
    )
    
    # 수신/참조/제목 라벨
    custom['label_line'] = ParagraphStyle(
        'label_line', parent=styles['Normal'],
        fontName=KOREAN_FONT, fontSize=11, alignment=TA_LEFT,
        leading=18
    )
    
    # 문서 제목 (중앙, 16pt)
    custom['doc_title'] = ParagraphStyle(
        'doc_title', parent=styles['Normal'],
        fontName=KOREAN_FONT_BOLD, fontSize=16, leading=24,
        alignment=TA_CENTER, spaceAfter=5*mm
    )
    
    # 사건번호/제목 (좌, 11pt)
    custom['case_header'] = ParagraphStyle(
        'case_header', parent=styles['Normal'],
        fontName=KOREAN_FONT, fontSize=11, leading=18, alignment=TA_LEFT
    )
    
    # 서문 (본문 크기, 좌)
    custom['preamble'] = ParagraphStyle(
        'preamble', parent=styles['Normal'],
        fontName=KOREAN_FONT, fontSize=11, leading=18, alignment=TA_LEFT,
        spaceBefore=5*mm, spaceAfter=5*mm
    )
    
    # 아 래 (중앙)
    custom['below_marker'] = ParagraphStyle(
        'below_marker', parent=styles['Normal'],
        fontName=KOREAN_FONT, fontSize=11, alignment=TA_CENTER,
        spaceBefore=5*mm, spaceAfter=8*mm
    )
    
    # 섹션 번호 (Ⅰ, Ⅱ ... 14pt bold)
    custom['section_heading'] = ParagraphStyle(
        'section_heading', parent=styles['Normal'],
        fontName=KOREAN_FONT_BOLD, fontSize=13, leading=20,
        spaceBefore=8*mm, spaceAfter=3*mm, alignment=TA_LEFT
    )
    
    # 본문
    custom['body'] = ParagraphStyle(
        'body', parent=styles['Normal'],
        fontName=KOREAN_FONT, fontSize=10, leading=16,
        alignment=TA_LEFT, leftIndent=5*mm
    )
    
    # 본문 (들여쓰기 없음)
    custom['body_no_indent'] = ParagraphStyle(
        'body_no_indent', parent=styles['Normal'],
        fontName=KOREAN_FONT, fontSize=10, leading=16,
        alignment=TA_LEFT
    )
    
    # 서명란 (우측)
    custom['signature'] = ParagraphStyle(
        'signature', parent=styles['Normal'],
        fontName=KOREAN_FONT, fontSize=11, alignment=TA_CENTER,
        spaceBefore=15*mm
    )
    
    # 용지규격 (하단 우측, 8pt grey)
    custom['paper_spec'] = ParagraphStyle(
        'paper_spec', parent=styles['Normal'],
        fontName=KOREAN_FONT, fontSize=8, alignment=TA_RIGHT,
        textColor=colors.grey, spaceBefore=10*mm
    )
    
    return custom


# ============================================================
# 메인 서비스 클래스
# ============================================================

class ReportStorageService:
    """
    보고서 저장 서비스
    - 메모리에 JSON 저장
    - PDF 파일로 저장 (app/reports/)
    """
    
    # 메모리 저장소
    _reports: Dict[str, Dict[str, Any]] = {}
    
    # PDF 저장 경로
    PDF_SAVE_DIR = Path("app/reports")
    
    @staticmethod
    def _ensure_pdf_dir():
        """PDF 저장 디렉토리 생성"""
        ReportStorageService.PDF_SAVE_DIR.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def save_report(
        report_type: str,
        case_id: str,
        title: str,
        content: Dict[str, Any],
        decision_type: str = None
    ) -> Dict[str, Any]:
        """
        보고서 저장
        - 메모리에 JSON 저장
        - PDF 파일로 저장 (app/reports/)
        
        Args:
            report_type: INTERIM | FINAL | DECISION
            case_id: 사건 ID
            title: 보고서 제목
            content: 보고서 내용
            decision_type: TRANSFER | NON_TRANSFER | SUSPENSION (DECISION일 때만)
        """
        report_id = str(uuid.uuid4())
        created_at = utc_now_iso()
        
        # PDF 파일 생성
        pdf_path = ReportStorageService._save_as_pdf(
            report_id=report_id,
            report_type=report_type,
            title=title,
            content=content,
            decision_type=decision_type
        )
        
        report_data = {
            "report_id": report_id,
            "report_type": report_type,
            "decision_type": decision_type,
            "case_id": case_id,
            "title": title,
            "content": content,
            "pdf_path": str(pdf_path),
            "created_at": created_at
        }
        
        # 메모리 저장
        ReportStorageService._reports[report_id] = report_data
        
        print(f"📁 보고서 저장 완료: {report_id} ({report_type})")
        print(f"📄 PDF 저장 위치: {pdf_path}")
        
        return report_data
    
    @staticmethod
    def _save_as_pdf(
        report_id: str,
        report_type: str,
        title: str,
        content: Dict[str, Any],
        decision_type: str = None
    ) -> Path:
        """보고서 유형별로 경찰 공식 양식에 맞춰 PDF 생성"""
        ReportStorageService._ensure_pdf_dir()
        
        # 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = f"_{decision_type}" if decision_type else ""
        filename = f"{report_type}{suffix}_{timestamp}_{report_id[:8]}.pdf"
        pdf_path = ReportStorageService.PDF_SAVE_DIR / filename
        
        # PDF 문서 생성
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            rightMargin=20*mm,
            leftMargin=20*mm,
            topMargin=15*mm,
            bottomMargin=20*mm
        )
        
        st = _make_styles()
        story = []
        
        try:
            if report_type == "INTERIM":
                story = ReportStorageService._build_interim(title, content, st)
            elif report_type == "FINAL":
                story = ReportStorageService._build_final(title, content, st)
            elif report_type == "DECISION":
                story = ReportStorageService._build_decision(
                    title, content, st, decision_type
                )
            else:
                # fallback
                story = ReportStorageService._build_generic(title, content, st)
            
            doc.build(story)
            return pdf_path
            
        except Exception as e:
            print(f"   ❌ PDF 생성 실패: {e}")
            return pdf_path

    # ============================================================
    # 수사보고 (INTERIM) — 범죄수사규칙 별지 제174호서식
    # ============================================================

    @staticmethod
    def _build_interim(title: str, content: Dict[str, Any], st: dict) -> list:
        """
        수사보고 양식:
        ■ 범죄수사규칙 [별지 제174호서식]
        소 속 관 서
        제 0000-000000 호   YYYY.MM.DD.
        수 신 :
        참 조 :
        제 목 : 수사보고 (   )
        피의자 ___ 에 대한 ___ 사건에 관하여 아래와 같이 수사하였기에 보고합니다.
        - 아 래 -
        (본문)
        """
        story = []
        
        # 1. 양식번호
        story.append(Paragraph(
            escape_xml("■ 범죄수사규칙 [별지 제174호서식]"),
            st['form_number']
        ))
        story.append(Spacer(1, 5*mm))
        
        # 1-1. 경찰 로고 (중앙 정렬)
        if POLICE_LOGO_PATH and os.path.exists(POLICE_LOGO_PATH):
            try:
                logo = Image(POLICE_LOGO_PATH, width=25*mm, height=25*mm)
                logo.hAlign = 'CENTER'
                story.append(logo)
                story.append(Spacer(1, 3*mm))
            except Exception as e:
                print(f"   ⚠️ 로고 로딩 실패: {e}")
        
        # 2. 소속관서
        story.append(Paragraph(escape_xml("소 속 관 서"), st['org_title']))
        story.append(Spacer(1, 8*mm))
        
        # 3. 문서번호 + 날짜
        story.append(Paragraph(
            escape_xml(f"제 0000-000000 호                    {format_date()}"),
            st['doc_number']
        ))
        story.append(Spacer(1, 5*mm))
        
        # 4. 수신 / 참조 / 제목
        story.append(Paragraph(escape_xml("수 신 :"), st['label_line']))
        story.append(Paragraph(escape_xml("참 조 :"), st['label_line']))
        
        # 제목에서 괄호 안 내용 추출
        subtitle = content.get("case_name", "")
        title_text = f"제 목 : 수사보고 ( {subtitle} )" if subtitle else f"제 목 : {title}"
        story.append(Paragraph(escape_xml(title_text), st['label_line']))
        story.append(Spacer(1, 8*mm))
        
        # 5. 서문
        suspect = content.get("suspect", "미상")
        case_name = content.get("case_name", "")
        preamble = f"피의자 {suspect} 에 대한 {case_name} 사건에 관하여 아래와 같이 수사하였기에 보고합니다."
        story.append(Paragraph(escape_xml(preamble), st['preamble']))
        
        # 6. - 아 래 -
        story.append(Paragraph(escape_xml("- 아 래 -"), st['below_marker']))
        
        # 7. 본문 내용
        # 섹션 매핑
        section_map = [
            ("사건 개요", "case_overview"),
            ("수사 경과", "investigation_progress"),
            ("현재 상황", "current_status"),
            ("향후 계획", "future_plan"),
        ]
        
        for label, key in section_map:
            value = content.get(key)
            if not value:
                continue
            story.append(Paragraph(
                f"<b>{escape_xml(label)}</b>",
                st['section_heading']
            ))
            text = flatten_content(value)
            for line in text.split('\n'):
                line = line.strip()
                if line:
                    story.append(Paragraph(escape_xml(line), st['body']))
                    story.append(Spacer(1, 1*mm))
            story.append(Spacer(1, 3*mm))
        
        # 8. 용지규격
        story.append(Spacer(1, 10*mm))
        story.append(Paragraph("210㎜ × 297㎜(백상지 80g/㎡)", st['paper_spec']))
        
        return story

    # ============================================================
    # 수사결과보고 (FINAL) — 범죄수사규칙 별지 제156호서식
    # ============================================================

    @staticmethod
    def _build_final(title: str, content: Dict[str, Any], st: dict) -> list:
        """
        수사결과보고 양식:
        ■ 범죄수사규칙 [별지 제156호서식]
        소 속 관 서
        제 0000-000000 호   YYYY.MM.DD.
        수 신 :
        참 조 :
        제 목 : 수사결과보고
        피의사건에 관하여 다음과 같이 수사하였기에 결과 보고합니다.
        Ⅰ. 피의자 인적사항
        Ⅱ. 범죄경력자료 및 수사경력자료
        Ⅲ. 범죄사실
        Ⅳ. 적용법조
        Ⅴ. 증거관계
        Ⅵ. 수사결과 및 의견
        Ⅶ. 수사참여경찰관
        """
        story = []
        
        # 1. 양식번호
        story.append(Paragraph(
            escape_xml("■ 범죄수사규칙 [별지 제156호서식]"),
            st['form_number']
        ))
        story.append(Spacer(1, 5*mm))
        
        # 1-1. 경찰 로고 (중앙 정렬)
        if POLICE_LOGO_PATH and os.path.exists(POLICE_LOGO_PATH):
            try:
                logo = Image(POLICE_LOGO_PATH, width=25*mm, height=25*mm)
                logo.hAlign = 'CENTER'
                story.append(logo)
                story.append(Spacer(1, 3*mm))
            except Exception as e:
                print(f"   ⚠️ 로고 로딩 실패: {e}")
        
        # 2. 소속관서
        story.append(Paragraph(escape_xml("소 속 관 서"), st['org_title']))
        story.append(Spacer(1, 8*mm))
        
        # 3. 문서번호 + 날짜
        story.append(Paragraph(
            escape_xml(f"제 0000-000000 호                    {format_date()}"),
            st['doc_number']
        ))
        story.append(Spacer(1, 5*mm))
        
        # 4. 수신 / 참조 / 제목
        story.append(Paragraph(escape_xml("수 신 :"), st['label_line']))
        story.append(Paragraph(escape_xml("참 조 :"), st['label_line']))
        story.append(Paragraph(escape_xml("제 목 : 수사결과보고"), st['label_line']))
        story.append(Spacer(1, 8*mm))
        
        # 5. 서문
        story.append(Paragraph(
            escape_xml("피의사건에 관하여 다음과 같이 수사하였기에 결과 보고합니다."),
            st['preamble']
        ))
        story.append(Spacer(1, 5*mm))
        
        # 6. 섹션 Ⅰ~Ⅶ
        
        # Ⅰ. 피의자 인적사항
        story.append(Paragraph(escape_xml("Ⅰ. 피의자 인적사항"), st['section_heading']))
        suspect = content.get("suspect", "미상")
        if isinstance(suspect, dict):
            for k, v in suspect.items():
                story.append(Paragraph(escape_xml(f"{k} : {v}"), st['body']))
        else:
            story.append(Paragraph(escape_xml(str(suspect)), st['body']))
        story.append(Spacer(1, 3*mm))
        
        # Ⅱ. 범죄경력자료 및 수사경력자료
        story.append(Paragraph(escape_xml("Ⅱ. 범죄경력자료 및 수사경력자료"), st['section_heading']))
        criminal_record = content.get("criminal_record", "해당 없음")
        story.append(Paragraph(escape_xml(flatten_content(criminal_record)), st['body']))
        story.append(Spacer(1, 3*mm))
        
        # Ⅲ. 범죄사실
        story.append(Paragraph(escape_xml("Ⅲ. 범죄사실"), st['section_heading']))
        case_overview = content.get("case_overview", {})
        text = flatten_content(case_overview)
        for line in text.split('\n'):
            line = line.strip()
            if line:
                story.append(Paragraph(escape_xml(line), st['body']))
                story.append(Spacer(1, 1*mm))
        story.append(Spacer(1, 3*mm))
        
        # Ⅳ. 적용법조
        story.append(Paragraph(escape_xml("Ⅳ. 적용법조"), st['section_heading']))
        legal = content.get("legal_review", {})
        applicable_law = legal.get("applicable_law", "") if isinstance(legal, dict) else str(legal)
        story.append(Paragraph(escape_xml(flatten_content(applicable_law or "해당 없음")), st['body']))
        story.append(Spacer(1, 3*mm))
        
        # Ⅴ. 증거관계
        story.append(Paragraph(escape_xml("Ⅴ. 증거관계"), st['section_heading']))
        inv_result = content.get("investigation_result", {})
        text = flatten_content(inv_result)
        for line in text.split('\n'):
            line = line.strip()
            if line:
                story.append(Paragraph(escape_xml(line), st['body']))
                story.append(Spacer(1, 1*mm))
        story.append(Spacer(1, 3*mm))
        
        # Ⅵ. 수사결과 및 의견
        story.append(Paragraph(escape_xml("Ⅵ. 수사결과 및 의견"), st['section_heading']))
        opinion = content.get("transfer_opinion", {})
        text = flatten_content(opinion)
        for line in text.split('\n'):
            line = line.strip()
            if line:
                story.append(Paragraph(escape_xml(line), st['body']))
                story.append(Spacer(1, 1*mm))
        # 특이사항
        special = content.get("special_notes", "")
        if special and special != "없음":
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph(escape_xml(f"[특이사항] {special}"), st['body']))
        story.append(Spacer(1, 3*mm))
        
        # Ⅶ. 수사참여경찰관
        story.append(Paragraph(escape_xml("Ⅶ. 수사참여경찰관"), st['section_heading']))
        officers = content.get("officers", "")
        story.append(Paragraph(escape_xml(flatten_content(officers) or " "), st['body']))
        
        # 7. 용지규격
        story.append(Spacer(1, 10*mm))
        story.append(Paragraph("210㎜ × 297㎜(백상지 80g/㎡)", st['paper_spec']))
        
        return story

    # ============================================================
    # 결정서 (DECISION) — 송치/불송치/수사중지
    # ============================================================

    @staticmethod
    def _build_decision(
        title: str,
        content: Dict[str, Any],
        st: dict,
        decision_type: str = None
    ) -> list:
        """
        결정서 공통 양식 (경찰 로고 포함):
        ■ 경찰수사규칙 [별지 제XXX호서식]
        [경찰 로고]
        소 속 관 서
                                    YYYY.MM.DD.
        사건번호  0000-00000호, 0000-00000호
        제  목  XX 결정서
        ─────────────────────────
        아래와 같이 XX 결정합니다.
        Ⅰ~Ⅳ or Ⅰ~Ⅵ
        사법경찰관  계급
        """
        
        # decision_type 추론
        if not decision_type:
            decision_type = ReportStorageService._infer_decision_type(content, title)
        
        # 결정 유형별 설정
        config = {
            "TRANSFER": {
                "form": "■ 경찰수사규칙 [별지 제114호서식]",
                "title": "송치 결정서",
                "preamble": "아래와 같이 송치 결정합니다.",
                "sections": "transfer"
            },
            "NON_TRANSFER": {
                "form": "■ 경찰수사규칙 [별지 제122호서식]",
                "title": "불송치 결정서",
                "preamble": "아래와 같이 불송치 결정합니다.",
                "sections": "non_transfer"
            },
            "SUSPENSION": {
                "form": "■ 경찰수사규칙 [별지 제107호서식]",
                "title": "수사중지 결정서",
                "preamble": "아래와 같이 수사중지 결정합니다.",
                "sections": "suspension"
            }
        }
        
        cfg = config.get(decision_type, config["TRANSFER"])
        story = []
        
        # 1. 양식번호
        story.append(Paragraph(escape_xml(cfg["form"]), st['form_number']))
        story.append(Spacer(1, 5*mm))
        
        # 2. 경찰 로고 (중앙)
        if POLICE_LOGO_PATH and os.path.exists(POLICE_LOGO_PATH):
            try:
                logo = Image(POLICE_LOGO_PATH, width=25*mm, height=25*mm)
                logo.hAlign = 'CENTER'
                story.append(logo)
                story.append(Spacer(1, 3*mm))
            except Exception as e:
                print(f"   ⚠️ 로고 로딩 실패: {e}")
        
        # 3. 소속관서
        story.append(Paragraph(escape_xml("소 속 관 서"), st['org_title']))
        story.append(Spacer(1, 5*mm))
        
        # 4. 날짜 (우측)
        story.append(Paragraph(escape_xml(format_date()), st['date_right']))
        story.append(Spacer(1, 5*mm))
        
        # 5. 사건번호 / 제목
        story.append(Paragraph(
            escape_xml("사건번호    0000-00000호, 0000-00000호"),
            st['case_header']
        ))
        story.append(Paragraph(
            escape_xml(f"제    목    {cfg['title']}"),
            st['case_header']
        ))
        story.append(Spacer(1, 2*mm))
        
        # 6. 구분선
        story.append(HRFlowable(
            width="100%", thickness=1, color=colors.black,
            spaceBefore=2*mm, spaceAfter=5*mm
        ))
        
        # 7. 서문
        story.append(Paragraph(escape_xml(cfg["preamble"]), st['preamble']))
        story.append(Spacer(1, 5*mm))
        
        # 8. 섹션 (유형별 분기)
        if cfg["sections"] == "transfer":
            ReportStorageService._add_transfer_sections(story, content, st)
        elif cfg["sections"] == "non_transfer":
            ReportStorageService._add_non_transfer_sections(story, content, st)
        elif cfg["sections"] == "suspension":
            ReportStorageService._add_suspension_sections(story, content, st)
        
        # 9. 서명란
        story.append(Paragraph(escape_xml("사법경찰관    계급"), st['signature']))
        
        # 10. 용지규격
        story.append(Spacer(1, 10*mm))
        story.append(Paragraph("210㎜ × 297㎜(백상지 80g/㎡)", st['paper_spec']))
        
        return story

    # ── 송치 결정서 섹션 (별지 제114호) ──

    @staticmethod
    def _add_transfer_sections(story: list, content: dict, st: dict):
        """
        Ⅰ. 피의자 인적사항
        Ⅱ. 범죄경력자료 및 수사경력자료
        Ⅲ. 범죄사실
        Ⅳ. 적용법조
        Ⅴ. 증거관계
        Ⅵ. 송치 결정 이유
        """
        # Ⅰ
        story.append(Paragraph(escape_xml("Ⅰ. 피의자 인적사항"), st['section_heading']))
        suspect = content.get("suspect", "미상")
        if isinstance(suspect, dict):
            for k, v in suspect.items():
                story.append(Paragraph(escape_xml(f"  {k} : {v}"), st['body']))
        else:
            story.append(Paragraph(escape_xml(f"  성명 : {suspect}"), st['body']))
        story.append(Spacer(1, 3*mm))
        
        # Ⅱ
        story.append(Paragraph(escape_xml("Ⅱ. 범죄경력자료 및 수사경력자료"), st['section_heading']))
        story.append(Paragraph(escape_xml(flatten_content(content.get("criminal_record", "해당 없음"))), st['body']))
        story.append(Spacer(1, 3*mm))
        
        # Ⅲ
        story.append(Paragraph(escape_xml("Ⅲ. 범죄사실"), st['section_heading']))
        case_text = flatten_content(content.get("case_overview", ""))
        for line in case_text.split('\n'):
            if line.strip():
                story.append(Paragraph(escape_xml(line.strip()), st['body']))
                story.append(Spacer(1, 1*mm))
        story.append(Spacer(1, 3*mm))
        
        # Ⅳ
        story.append(Paragraph(escape_xml("Ⅳ. 적용법조"), st['section_heading']))
        legal = content.get("legal_review", {})
        applicable = legal.get("applicable_law", "") if isinstance(legal, dict) else str(legal)
        story.append(Paragraph(escape_xml(flatten_content(applicable or "해당 없음")), st['body']))
        story.append(Spacer(1, 3*mm))
        
        # Ⅴ
        story.append(Paragraph(escape_xml("Ⅴ. 증거관계"), st['section_heading']))
        evidence = content.get("evidence_evaluation", content.get("investigation_result", {}))
        text = flatten_content(evidence)
        for line in text.split('\n'):
            if line.strip():
                story.append(Paragraph(escape_xml(line.strip()), st['body']))
                story.append(Spacer(1, 1*mm))
        story.append(Spacer(1, 3*mm))
        
        # Ⅵ
        story.append(Paragraph(escape_xml("Ⅵ. 송치 결정 이유"), st['section_heading']))
        reason = content.get("judgment_reason", content.get("transfer_opinion", {}))
        text = flatten_content(reason)
        for line in text.split('\n'):
            if line.strip():
                story.append(Paragraph(escape_xml(line.strip()), st['body']))
                story.append(Spacer(1, 1*mm))
        story.append(Spacer(1, 5*mm))

    # ── 불송치 결정서 섹션 (별지 제122호) ──

    @staticmethod
    def _add_non_transfer_sections(story: list, content: dict, st: dict):
        """
        Ⅰ. 피의자
        Ⅱ. 죄명
        Ⅲ. 주문
        Ⅳ. 피의사실과 불송치 이유
        """
        # Ⅰ
        story.append(Paragraph(escape_xml("Ⅰ. 피의자"), st['section_heading']))
        suspect = content.get("suspect", "미상")
        story.append(Paragraph(escape_xml(flatten_content(suspect)), st['body']))
        story.append(Spacer(1, 3*mm))
        
        # Ⅱ
        story.append(Paragraph(escape_xml("Ⅱ. 죄명"), st['section_heading']))
        charge = content.get("charge", "")
        if not charge:
            legal = content.get("legal_review", {})
            charge = legal.get("applicable_law", "해당 없음") if isinstance(legal, dict) else str(legal)
        story.append(Paragraph(escape_xml(flatten_content(charge)), st['body']))
        story.append(Spacer(1, 3*mm))
        
        # Ⅲ
        story.append(Paragraph(escape_xml("Ⅲ. 주문"), st['section_heading']))
        ruling = content.get("ruling", "불송치 결정함")
        story.append(Paragraph(escape_xml(flatten_content(ruling)), st['body']))
        story.append(Spacer(1, 3*mm))
        
        # Ⅳ
        story.append(Paragraph(escape_xml("Ⅳ. 피의사실과 불송치 이유"), st['section_heading']))
        # 피의사실
        case_text = flatten_content(content.get("case_overview", ""))
        for line in case_text.split('\n'):
            if line.strip():
                story.append(Paragraph(escape_xml(line.strip()), st['body']))
                story.append(Spacer(1, 1*mm))
        story.append(Spacer(1, 3*mm))
        # 불송치 이유
        reason = content.get("judgment_reason", {})
        text = flatten_content(reason)
        for line in text.split('\n'):
            if line.strip():
                story.append(Paragraph(escape_xml(line.strip()), st['body']))
                story.append(Spacer(1, 1*mm))
        story.append(Spacer(1, 5*mm))

    # ── 수사중지 결정서 섹션 (별지 제107호) ──

    @staticmethod
    def _add_suspension_sections(story: list, content: dict, st: dict):
        """
        Ⅰ. 피의자
        Ⅱ. 죄명
        Ⅲ. 주문
        Ⅳ. 피의사실과 수사중지 이유
        """
        # Ⅰ
        story.append(Paragraph(escape_xml("Ⅰ. 피의자"), st['section_heading']))
        suspect = content.get("suspect", "미상")
        story.append(Paragraph(escape_xml(flatten_content(suspect)), st['body']))
        story.append(Spacer(1, 3*mm))
        
        # Ⅱ
        story.append(Paragraph(escape_xml("Ⅱ. 죄명"), st['section_heading']))
        charge = content.get("charge", "")
        if not charge:
            legal = content.get("legal_review", {})
            charge = legal.get("applicable_law", "해당 없음") if isinstance(legal, dict) else str(legal)
        story.append(Paragraph(escape_xml(flatten_content(charge)), st['body']))
        story.append(Spacer(1, 3*mm))
        
        # Ⅲ
        story.append(Paragraph(escape_xml("Ⅲ. 주문"), st['section_heading']))
        ruling = content.get("ruling", "수사중지 결정함")
        story.append(Paragraph(escape_xml(flatten_content(ruling)), st['body']))
        story.append(Spacer(1, 3*mm))
        
        # Ⅳ
        story.append(Paragraph(escape_xml("Ⅳ. 피의사실과 수사중지 이유"), st['section_heading']))
        case_text = flatten_content(content.get("case_overview", ""))
        for line in case_text.split('\n'):
            if line.strip():
                story.append(Paragraph(escape_xml(line.strip()), st['body']))
                story.append(Spacer(1, 1*mm))
        story.append(Spacer(1, 3*mm))
        reason = content.get("judgment_reason", {})
        text = flatten_content(reason)
        for line in text.split('\n'):
            if line.strip():
                story.append(Paragraph(escape_xml(line.strip()), st['body']))
                story.append(Spacer(1, 1*mm))
        story.append(Spacer(1, 5*mm))

    # ── 결정 유형 추론 ──

    @staticmethod
    def _infer_decision_type(content: dict, title: str) -> str:
        """content/title에서 결정 유형 추론"""
        # title 기반
        combined = title + " " + str(content.get("ruling", "")) + " " + str(
            content.get("conclusion", {}).get("final_opinion", "") if isinstance(content.get("conclusion"), dict) else ""
        )
        
        if "불송치" in combined:
            return "NON_TRANSFER"
        elif "수사중지" in combined:
            return "SUSPENSION"
        elif "송치" in combined:
            return "TRANSFER"
        
        return "TRANSFER"  # 기본값

    # ── 제네릭 fallback ──

    @staticmethod
    def _build_generic(title: str, content: Dict[str, Any], st: dict) -> list:
        """유형 미지정 시 기본 레이아웃"""
        story = []
        story.append(Paragraph(escape_xml(title), st['doc_title']))
        story.append(Spacer(1, 5*mm))
        story.append(Paragraph(escape_xml(format_date()), st['date_right']))
        story.append(Spacer(1, 10*mm))
        
        for key, value in content.items():
            story.append(Paragraph(
                f"<b>{escape_xml(str(key))}</b>",
                st['section_heading']
            ))
            text = flatten_content(value)
            for line in text.split('\n'):
                if line.strip():
                    story.append(Paragraph(escape_xml(line.strip()), st['body']))
                    story.append(Spacer(1, 1*mm))
            story.append(Spacer(1, 3*mm))
        
        story.append(Paragraph("210㎜ × 297㎜(백상지 80g/㎡)", st['paper_spec']))
        return story

    # ============================================================
    # CRUD 메서드
    # ============================================================
    
    @staticmethod
    def get_report(report_id: str) -> Optional[Dict[str, Any]]:
        """보고서 조회"""
        return ReportStorageService._reports.get(report_id)
    
    @staticmethod
    def get_all_reports() -> List[Dict[str, Any]]:
        """모든 보고서 조회"""
        return list(ReportStorageService._reports.values())
    
    @staticmethod
    def delete_report(report_id: str) -> bool:
        """보고서 삭제 (메모리 + PDF 파일)"""
        if report_id in ReportStorageService._reports:
            report = ReportStorageService._reports[report_id]
            
            # PDF 파일 삭제
            pdf_path = Path(report.get("pdf_path", ""))
            if pdf_path.exists():
                pdf_path.unlink()
                print(f"📄 PDF 파일 삭제: {pdf_path}")
            
            # 메모리에서 삭제
            del ReportStorageService._reports[report_id]
            print(f"🗑️ 보고서 삭제 완료: {report_id}")
            return True
        return False
    
    @staticmethod
    def get_reports_by_case(case_id: str) -> List[Dict[str, Any]]:
        """특정 사건의 모든 보고서 조회"""
        return [
            report for report in ReportStorageService._reports.values()
            if report.get("case_id") == case_id
        ]