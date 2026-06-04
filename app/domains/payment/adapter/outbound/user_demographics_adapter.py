"""UserDemographicsPort 구현체.

payment 도메인이 user 도메인을 직접 import하지 않도록, application 레이어에서
역전된 의존성을 어댑터 레이어에서 user_repo와 묶어 제공한다.

- user_repo.find_by_id로 user 조회 (없으면 None)
- gender: user.gender.value (소문자 "male"/"female") 반환
- birth_year: user.birth_info.birth_date.year — 분석용 연령대. PII 정책상 '연도'만.
"""

from app.domains.payment.application.payment_ports import (
    UserDemographicsPort,
)
from app.domains.user.domain.port.user_repository_port import UserRepositoryPort


class UserDemographicsAdapter(UserDemographicsPort):
    def __init__(self, *, user_repo: UserRepositoryPort) -> None:
        self._user_repo = user_repo

    async def find_gender_by_user_id(self, user_id: int) -> str | None:
        user = await self._user_repo.find_by_id(user_id)
        if user is None:
            return None
        return user.gender.value

    async def find_birth_year_by_user_id(self, user_id: int) -> int | None:
        user = await self._user_repo.find_by_id(user_id)
        if user is None:
            return None
        return user.birth_info.birth_date.year
