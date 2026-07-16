from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.domains.chat.domain.value_object.birth_profile import BirthProfile


@dataclass
class SajuProfile:
    """계정의 채팅 사주 프로필 — 캐릭터 간 공유(계정 단위). chat 도메인 소유.

    saju_raw = FortuneTeller 응답 원본(pillars/wuxing/tenGods 등). 개인정보(생년월일 평문)는
    birth에 보관하되 로그 금지(팀 룰 8). saju_summary는 노출용 요약(일간·오행).
    """

    account_id: int
    birth: BirthProfile
    saju_raw: dict[str, Any]
    created_at: datetime | None = None
    updated_at: datetime | None = None
    id: int | None = None
