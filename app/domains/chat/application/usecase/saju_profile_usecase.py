import logging

from app.domains.chat.application.request.saju_profile_request import (
    SaveSajuProfileRequest,
)
from app.domains.chat.application.response.saju_profile_response import (
    SajuProfileResponse,
)
from app.domains.chat.domain.entity.saju_profile import SajuProfile
from app.domains.chat.domain.port.saju_cache_port import SajuCachePort
from app.domains.chat.domain.port.saju_engine_port import SajuEnginePort
from app.domains.chat.domain.port.saju_profile_repository_port import (
    SajuProfileRepositoryPort,
)
from app.domains.chat.domain.service.saju_summary import build_saju_summary

logger = logging.getLogger(__name__)


class GetSajuProfileUseCase:
    def __init__(self, *, profile_repo: SajuProfileRepositoryPort) -> None:
        self._repo = profile_repo

    async def execute(self, account_id: int) -> SajuProfileResponse:
        profile = await self._repo.find_by_account(account_id)
        if profile is None:
            return SajuProfileResponse(has_profile=False)
        return SajuProfileResponse.from_summary(build_saju_summary(profile.saju_raw))


class SaveSajuProfileUseCase:
    """확인 모달 제출 → (캐시 조회 → 미스 시 FortuneTeller 1회) → 저장 → 요약 반환.

    개인정보(생년월일·성별)는 로그 금지(팀 룰 8) — fingerprint/결과만 다룬다.
    """

    def __init__(
        self,
        *,
        profile_repo: SajuProfileRepositoryPort,
        saju_engine: SajuEnginePort,
        cache: SajuCachePort,
    ) -> None:
        self._repo = profile_repo
        self._engine = saju_engine
        self._cache = cache

    async def execute(
        self, account_id: int, request: SaveSajuProfileRequest
    ) -> SajuProfileResponse:
        birth = request.to_birth_profile()
        fingerprint = birth.cache_fingerprint()

        saju_raw = await self._cache.get(fingerprint)
        if saju_raw is None:
            saju_raw = await self._engine.analyze(birth.to_fortuneteller_payload())
            await self._cache.set(fingerprint, saju_raw)
        else:
            logger.info("saju 캐시 히트 (account=%d)", account_id)

        saved = await self._repo.upsert(
            SajuProfile(account_id=account_id, birth=birth, saju_raw=saju_raw)
        )
        return SajuProfileResponse.from_summary(build_saju_summary(saved.saju_raw))
