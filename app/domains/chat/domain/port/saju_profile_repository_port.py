from typing import Protocol

from app.domains.chat.domain.entity.saju_profile import SajuProfile


class SajuProfileRepositoryPort(Protocol):
    """계정 사주 프로필 저장/조회 — 계정당 1건(upsert)."""

    async def find_by_account(self, account_id: int) -> SajuProfile | None: ...

    async def upsert(self, profile: SajuProfile) -> SajuProfile: ...
