"""FortuneTeller raw → 노출용 사주 요약 + 프롬프트 컨텍스트 — 순수 도메인.

extract_paid_variables(user 도메인)를 재사용해 일간·오행 등을 뽑는다. 그 함수는
domain/service 순수 함수라 도메인 간 import 허용(둘 다 domain, 외부 의존 0).
"""

from typing import Any

from app.domains.user.domain.service.saju_data_extractor import SajuDataExtractor

_extractor = SajuDataExtractor()

_OHANG_LABEL = {
    "OHANG_MOK": "목(木)", "OHANG_HWA": "화(火)", "OHANG_TO": "토(土)",
    "OHANG_GEUM": "금(金)", "OHANG_SU": "수(水)",
}


def build_saju_summary(saju_raw: dict[str, Any]) -> dict[str, Any]:
    """노출/리빌용 요약. 일간·오행 비율·과다/결핍. (개인정보 아님 — pillars 파생값만)"""
    v = _extractor.extract_paid_variables(saju_raw)
    ohang = {label: v.get(key, 0) for key, label in _OHANG_LABEL.items()}
    return {
        "ilgan": v.get("ILGAN", ""),  # 예: "임수"
        "ilju": v.get("ILJU", ""),
        "ohang": ohang,  # {"목(木)": 20, ...} 합 100
        "ohang_excess": v.get("OHANG_EXCESS", ""),
        "ohang_lack": v.get("OHANG_LACK", ""),
    }


def build_saju_context_block(saju_raw: dict[str, Any]) -> str:
    """프롬프트 주입용 — 캐릭터가 '상대의 사주'로서 참고할 컨텍스트 (한자 음독 병기)."""
    v = _extractor.extract_paid_variables(saju_raw)
    pillars = (
        f"연주 {v.get('YR_G', '')}{v.get('YR_J', '')} · "
        f"월주 {v.get('WL_G', '')}{v.get('WL_J', '')} · "
        f"일주 {v.get('IL_G', '')}{v.get('IL_J', '')} · "
        f"시주 {v.get('SI_G', '')}{v.get('SI_J', '')}"
    )
    ohang = " / ".join(f"{label} {v.get(key, 0)}" for key, label in _OHANG_LABEL.items())
    lines = [
        "[상대(유저)의 사주 — 이 값에 근거해 답하라. 네 사주가 아니다]",
        f"- 일간: {v.get('ILGAN', '')} (일주 {v.get('ILJU', '')})",
        f"- 사주 사주(四柱): {pillars}",
        f"- 오행 비율(%): {ohang}",
        f"- 과다: {v.get('OHANG_EXCESS', '')} / 결핍: {v.get('OHANG_LACK', '')}",
        "한자를 인용할 땐 음독을 병기하라. 없는 값은 지어내지 마라.",
    ]
    return "\n".join(lines)
