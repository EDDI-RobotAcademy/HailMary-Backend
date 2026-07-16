from typing import Any

from pydantic import BaseModel


class SajuProfileResponse(BaseModel):
    """사주 요약 — 리빌/표시용 (일간·오행). 개인정보 미포함(pillars 파생값만)."""

    has_profile: bool
    ilgan: str = ""
    ilju: str = ""
    ohang: dict[str, int] = {}
    ohang_excess: str = ""
    ohang_lack: str = ""

    @staticmethod
    def from_summary(summary: dict[str, Any]) -> "SajuProfileResponse":
        return SajuProfileResponse(
            has_profile=True,
            ilgan=summary["ilgan"],
            ilju=summary["ilju"],
            ohang=summary["ohang"],
            ohang_excess=summary["ohang_excess"],
            ohang_lack=summary["ohang_lack"],
        )
