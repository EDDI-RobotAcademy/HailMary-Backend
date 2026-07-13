from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.chat.domain.entity.saju_profile import SajuProfile
from app.domains.chat.domain.port.saju_profile_repository_port import (
    SajuProfileRepositoryPort,
)
from app.domains.chat.infrastructure.mapper.saju_profile_mapper import SajuProfileMapper
from app.domains.chat.infrastructure.orm.saju_profile_orm import SajuProfileORM


class SajuProfileRepository(SajuProfileRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_account(self, account_id: int) -> SajuProfile | None:
        orm = (
            await self._session.execute(
                select(SajuProfileORM).where(SajuProfileORM.account_id == account_id)
            )
        ).scalar_one_or_none()
        return SajuProfileMapper.to_entity(orm) if orm else None

    async def upsert(self, profile: SajuProfile) -> SajuProfile:
        orm = (
            await self._session.execute(
                select(SajuProfileORM).where(
                    SajuProfileORM.account_id == profile.account_id
                )
            )
        ).scalar_one_or_none()
        b = profile.birth
        if orm is None:
            orm = SajuProfileORM(
                account_id=profile.account_id,
                birth_date=b.birth_date,
                birth_time=b.birth_time,
                birth_time_unknown=b.time_unknown,
                calendar=b.calendar.value,
                gender=b.gender.value,
                saju_raw=profile.saju_raw,
            )
            self._session.add(orm)
        else:
            orm.birth_date = b.birth_date
            orm.birth_time = b.birth_time
            orm.birth_time_unknown = b.time_unknown
            orm.calendar = b.calendar.value
            orm.gender = b.gender.value
            orm.saju_raw = profile.saju_raw
            orm.updated_at = datetime.now()
        await self._session.flush()
        await self._session.refresh(orm)  # server_default created_at 가드 (mig 013 500 교훈)
        return SajuProfileMapper.to_entity(orm)
