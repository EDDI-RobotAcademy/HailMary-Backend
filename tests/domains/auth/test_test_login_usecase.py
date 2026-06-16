"""TestLoginUseCase — 카드사 심사용 테스트 로그인 (HM-BE-84).

- 비활성(enabled=False) → TestLoginDisabledError (라우터 404)
- 자격증명 불일치 → TestLoginInvalidCredentialsError (라우터 401)
- 정상 → provider=test 단일 공유 계정 find-or-create + JWT 발급(SocialLoginResponse)
"""

from typing import Any

import pytest

from app.domains.auth.application.request.test_login_request import TestLoginRequest
from app.domains.auth.application.usecase.test_login_usecase import (
    TestLoginDisabledError,
    TestLoginInvalidCredentialsError,
    TestLoginUseCase,
)
from app.domains.auth.domain.entity.account import Account
from app.domains.auth.domain.value_object.provider import Provider

USERNAME = "cardtest"
PASSWORD = "long-random-secret-pw"


class FakeAccountRepo:
    def __init__(self) -> None:
        self.saved: list[Account] = []
        self._by_key: dict[tuple[Provider, str], Account] = {}
        self._next_id = 1

    async def find_by_provider_user(
        self, provider: Provider, provider_user_id: str
    ) -> Account | None:
        return self._by_key.get((provider, provider_user_id))

    async def save(self, account: Account) -> Account:
        account.id = self._next_id
        self._next_id += 1
        self._by_key[(account.provider, account.provider_user_id)] = account
        self.saved.append(account)
        return account

    async def update(self, account: Account) -> Account:
        return account

    async def find_by_id(self, account_id: int) -> Account | None:
        for a in self._by_key.values():
            if a.id == account_id:
                return a
        return None


class FakeTokenIssuer:
    def issue(self, account_id: int) -> str:
        return f"jwt-{account_id}"

    def decode(self, token: str) -> int:
        return int(token.split("-")[1])


def _usecase(
    repo: Any, *, enabled: bool = True, username: str | None = USERNAME, password: str | None = PASSWORD
) -> TestLoginUseCase:
    return TestLoginUseCase(
        account_repo=repo,
        token_issuer=FakeTokenIssuer(),
        enabled=enabled,
        username=username,
        password=password,
    )


async def test_disabled_raises() -> None:
    with pytest.raises(TestLoginDisabledError):
        await _usecase(FakeAccountRepo(), enabled=False).execute(
            TestLoginRequest(username=USERNAME, password=PASSWORD)
        )


async def test_missing_config_raises_disabled() -> None:
    with pytest.raises(TestLoginDisabledError):
        await _usecase(FakeAccountRepo(), password=None).execute(
            TestLoginRequest(username=USERNAME, password=PASSWORD)
        )


async def test_wrong_password_rejected() -> None:
    repo = FakeAccountRepo()
    with pytest.raises(TestLoginInvalidCredentialsError):
        await _usecase(repo).execute(TestLoginRequest(username=USERNAME, password="nope"))
    assert repo.saved == [], "자격증명 틀리면 계정 생성 금지"


async def test_valid_creates_test_account_and_issues_token() -> None:
    repo = FakeAccountRepo()
    res = await _usecase(repo).execute(TestLoginRequest(username=USERNAME, password=PASSWORD))

    assert res.access_token == "jwt-1"
    assert res.is_new_account is False
    assert res.profile.provider == "test"
    assert len(repo.saved) == 1
    assert repo.saved[0].provider == Provider.TEST
    assert repo.saved[0].provider_user_id == "card-review"


async def test_valid_reuses_single_shared_account() -> None:
    repo = FakeAccountRepo()
    await _usecase(repo).execute(TestLoginRequest(username=USERNAME, password=PASSWORD))
    res2 = await _usecase(repo).execute(TestLoginRequest(username=USERNAME, password=PASSWORD))

    assert len(repo.saved) == 1, "단일 공유 계정 — 두 번째 로그인은 재사용"
    assert res2.access_token == "jwt-1"
