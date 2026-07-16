"""사주 프로필 캡처 — fake 엔진/캐시/repo (DB·네트워크 없음)."""

from typing import Any

import pytest

from app.domains.chat.application.request.saju_profile_request import (
    SaveSajuProfileRequest,
)
from app.domains.chat.application.usecase.saju_profile_usecase import (
    GetSajuProfileUseCase,
    SaveSajuProfileUseCase,
)
from app.domains.chat.domain.entity.saju_profile import SajuProfile

# 최소 FortuneTeller raw — extract_paid_variables가 읽는 필드만
_FT_RAW: dict[str, Any] = {
    "year": {"stem": "갑", "branch": "술"},
    "month": {"stem": "정", "branch": "묘"},
    "day": {"stem": "임", "branch": "술"},
    "hour": {"stem": "을", "branch": "사"},
    "wuxingCount": {"목": 3, "화": 1, "토": 2, "금": 0, "수": 2},
}


class FakeEngine:
    def __init__(self) -> None:
        self.calls = 0

    async def analyze(self, saju_data: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        return _FT_RAW


class FakeCache:
    def __init__(self, seed: dict[str, dict[str, Any]] | None = None) -> None:
        self.store = seed or {}
        self.set_calls = 0

    async def get(self, fingerprint: str) -> dict[str, Any] | None:
        return self.store.get(fingerprint)

    async def set(self, fingerprint: str, saju_raw: dict[str, Any]) -> None:
        self.set_calls += 1
        self.store[fingerprint] = saju_raw


class FakeRepo:
    def __init__(self) -> None:
        self.saved: SajuProfile | None = None

    async def find_by_account(self, account_id: int) -> SajuProfile | None:
        return self.saved

    async def upsert(self, profile: SajuProfile) -> SajuProfile:
        self.saved = profile
        return profile


def _req(**kw: object) -> SaveSajuProfileRequest:
    base: dict[str, object] = {
        "birth_date": "1994-03-15", "birth_time": "10:00",
        "birth_time_unknown": False, "calendar": "solar", "gender": "male",
    }
    base.update(kw)
    return SaveSajuProfileRequest.model_validate(base)


async def test_save_calls_engine_on_cache_miss_and_persists() -> None:
    engine, cache, repo = FakeEngine(), FakeCache(), FakeRepo()
    usecase = SaveSajuProfileUseCase(profile_repo=repo, saju_engine=engine, cache=cache)
    res = await usecase.execute(1, _req())
    assert engine.calls == 1
    assert cache.set_calls == 1
    assert repo.saved is not None
    assert res.has_profile is True
    assert res.ilgan  # 일간 추출됨 (임수)


async def test_save_uses_cache_on_hit_skips_engine() -> None:
    engine, repo = FakeEngine(), FakeRepo()
    fp = _req().to_birth_profile().cache_fingerprint()
    cache = FakeCache({fp: _FT_RAW})
    usecase = SaveSajuProfileUseCase(profile_repo=repo, saju_engine=engine, cache=cache)
    await usecase.execute(1, _req())
    assert engine.calls == 0  # 캐시 히트 → FortuneTeller 미호출
    assert repo.saved is not None


async def test_time_unknown_maps_to_unknown_payload() -> None:
    profile = _req(birth_time=None, birth_time_unknown=True).to_birth_profile()
    assert profile.to_fortuneteller_payload()["time"] == "unknown"


async def test_get_returns_no_profile_when_absent() -> None:
    usecase = GetSajuProfileUseCase(profile_repo=FakeRepo())
    res = await usecase.execute(1)
    assert res.has_profile is False


async def test_get_returns_summary_when_present() -> None:
    repo = FakeRepo()
    repo.saved = SajuProfile(
        account_id=1, birth=_req().to_birth_profile(), saju_raw=_FT_RAW
    )
    res = await GetSajuProfileUseCase(profile_repo=repo).execute(1)
    assert res.has_profile is True
    assert sum(res.ohang.values()) == 100  # 오행 비율 합 100


def test_context_block_contains_ilgan_and_ohang() -> None:
    from app.domains.chat.domain.service.saju_summary import build_saju_context_block
    block = build_saju_context_block(_FT_RAW)
    assert "일간" in block and "오행" in block
    assert "상대(유저)의 사주" in block  # 네 사주 아님 명시


@pytest.mark.parametrize("bad", ["1994/03/15", "94-3-15", "abc"])
def test_request_rejects_bad_birth_format(bad: str) -> None:
    with pytest.raises(ValueError):
        _req(birth_date=bad)
