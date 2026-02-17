# app/services/report_interim_service.py
# ✅ 공문서체 3인칭 과거 시제(~함, ~였음) 어투 프롬프트 적용

import json
import re
from datetime import datetime
from openai import OpenAI
from app.config import settings
from app.models.report_interim_schema import (
    ReportInterimRequest,
    ReportInterimResponse
)
from app.services.report_storage_service import ReportStorageService

client = OpenAI(api_key=settings.OPENAI_API_KEY)

# ── 보고서 텍스트 정제 유틸 ──
_UUID_RE = re.compile(r'\(?\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b\)?')
_STATUS_MAP = {
    "NOT_SATISFIED": "미충족",
    "SATISFIED": "충족",
    "INSUFFICIENT": "불충분",
    "TRANSFER": "송치",
    "NON_TRANSFER": "불송치",
    "SUSPENSION": "수사중지",
}

def _sanitize_text(obj):
    """dict/list/str 재귀 - UUID 제거 + 영문 상태값 한글 변환"""
    if isinstance(obj, str):
        text = _UUID_RE.sub('', obj)
        for eng, kor in _STATUS_MAP.items():
            text = text.replace(eng, kor)
        text = re.sub(r'\s{2,}', ' ', text).strip()
        text = re.sub(r'\(\s*\)', '', text).strip()
        return text
    elif isinstance(obj, dict):
        return {k: _sanitize_text(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_text(v) for v in obj]
    return obj



# ============================================================
# 공통 문체 지시 (모든 보고서 서비스에서 사용)
# ============================================================

WRITING_STYLE_DIRECTIVE = """
**[문체 규칙 — 반드시 준수]**
1. 공문서체 3인칭 과거 시제로 작성할 것.
   - 문장 끝: ~함, ~였음, ~하였음, ~됨, ~확인됨, ~판단됨
   - 예시: "피의자는 ~한 사실이 확인됨", "수사관이 현장에 임장하여 ~을 확보하였음"
   - 금지: ~합니다, ~입니다, ~했습니다, ~됩니다 (경어체 금지)
   - 금지: ~한다, ~이다, ~했다 (평서체 금지)
2. 객관적 사실과 증거 중심으로 서술할 것.
   - 주관적 추측, 감정적 표현 배제
   - "~한 것으로 보임", "~한 것으로 판단됨" 등 객관적 추정 표현 사용
3. 전문 법률·수사 용어를 정확히 사용할 것.
   - 피의자, 피해자, 참고인, 임의동행, 긴급체포, 현행범체포, 압수, 수색,
     송치, 불송치, 기소, 불기소, 구성요건, 위법성, 책임성 등
"""


class ReportInterimService:
    """
    수사보고 생성 서비스
    
    수사 활동 로그를 기반으로 수사보고 작성
    """
    
    @staticmethod
    def generate_interim_report(request: ReportInterimRequest) -> ReportInterimResponse:
        """
        수사보고 생성 + 내부 저장
        
        - 사건 정보와 활동 로그를 분석
        - GPT-4o로 수사보고 작성
        - 내부 저장 후 title + content만 반환
        """
        print("\n" + "=" * 70)
        print("📄 수사보고 생성")
        print("=" * 70)
        print(f"사건: {request.case_detail.title}")
        print(f"활동 로그: {len(request.selected_activity_logs)}건")
        
        # 활동 로그 통계
        activity_stats = {}
        for log in request.selected_activity_logs:
            key = f"{log.field}_{log.activity_type}"
            activity_stats[key] = activity_stats.get(key, 0) + 1
        
        print(f"활동 통계: {json.dumps(activity_stats, ensure_ascii=False)}")
        
        # 프롬프트 구성
        prompt = ReportInterimService._build_prompt(request)
        
        # GPT-4o로 보고서 생성
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "당신은 경찰 수사보고 작성 전문가입니다.\n"
                            "모든 문장을 공문서체 3인칭 과거 시제(~함, ~였음, ~확인됨, ~판단됨)로 작성합니다.\n"
                            "객관적 사실과 증거 중심으로 서술하며, 경어체(~합니다)나 평서체(~한다)는 사용하지 않습니다."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # JSON 파싱
            import re
            result_text = re.sub(r"```json|```", "", result_text).strip()
            result = json.loads(result_text)
            
            title = result.get("title", "")
            content = _sanitize_text(result.get("content", {}))
            
            # 내부 저장 (PDF 등)
            ReportStorageService.save_report(
                report_type="INTERIM",
                case_id=request.case_detail.case_id,
                title=title,
                content=content
            )
            
            print("=" * 70)
            print(f"✅ 수사보고 생성 완료")
            print("=" * 70)
            
            return ReportInterimResponse(
                title=title,
                content=content
            )
        
        except Exception as e:
            print(f"⚠️ 수사보고 생성 실패: {e}")
            
            return ReportInterimResponse(
                title=f"{request.case_detail.title} 수사보고",
                content={
                    "error": f"자동 생성 실패: {str(e)}",
                    "manual_required": "true"
                }
            )
    
    @staticmethod
    def _build_prompt(request: ReportInterimRequest) -> str:
        """수사보고 생성 프롬프트 구성"""
        
        # 활동 로그를 시간순으로 정리
        logs_by_time = sorted(
            request.selected_activity_logs,
            key=lambda x: x.created_at
        )
        
        # 활동 로그를 카테고리별로 분류
        logs_by_field = {}
        for log in logs_by_time:
            if log.field not in logs_by_field:
                logs_by_field[log.field] = []
            logs_by_field[log.field].append({
                "activity_type": log.activity_type,
                "payload": log.payload,
                "created_at": log.created_at
            })
        
        prompt = f"""다음 수사 정보를 바탕으로 수사보고를 작성하십시오.

{WRITING_STYLE_DIRECTIVE}

**사건 정보:**
제목: {request.case_detail.title}
사건유형: {request.case_detail.type}
발생일시: {request.case_detail.occurred_at}
발생장소: {request.case_detail.location}
사건개요: {request.case_detail.description}

**사건 요약:**
{json.dumps(request.case_detail.summary.model_dump(), ensure_ascii=False, indent=2)}

**수사 활동 내역 ({len(request.selected_activity_logs)}건):**
{json.dumps(logs_by_field, ensure_ascii=False, indent=2)}

**출력 형식 (JSON만 출력):**
{{
  "title": "수사보고",
  "content": {{
    "case_name": "{request.case_detail.title}",
    "suspect": "피의자 성명 (미상이면 null로 출력)",
    "case_overview": "사건의 기본 정보와 경위를 서술형으로 기재 (3-5문장, ~함/~였음 어미 사용)",
    "investigation_progress": "시간순 수사 활동 내역을 서술형으로 기재 (5-7문장, ~함/~였음 어미 사용)",
    "current_status": {{
      "collected_evidence": "수집된 증거 목록 및 분석 결과를 서술형으로 기재",
      "legal_review": "법리 쟁점 및 판단 기준 검토 상황을 서술형으로 기재"
    }},
    "future_plan": "추가 수사 방향 및 예상 일정을 서술형으로 기재 (3-5문장, ~함/~였음 어미 사용)"
  }}
}}

**작성 원칙:**
- 공문서체 3인칭 과거 시제 (~함, ~였음, ~확인됨, ~판단됨)
- 객관적 사실과 증거 중심으로 서술
- 시간순 정리
- 구체적인 수치와 일자 포함
- 전문적인 법률·수사 용어 사용
- 경어체(~합니다) 및 평서체(~한다) 절대 금지
- 내부 시스템 ID(UUID, 영문+숫자+하이픈 조합)를 보고서 내용에 절대 포함하지 마십시오
- 영문 상태코드(SATISFIED, NOT_SATISFIED, INSUFFICIENT 등)를 한글(충족, 미충족, 불충분)로 변환하여 사용하십시오
"""
        
        return prompt