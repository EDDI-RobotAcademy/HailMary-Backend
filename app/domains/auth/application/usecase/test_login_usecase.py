"""카드사 심사용 테스트 로그인 UseCase (HM-BE-84).

OAuth가 아니라 설정된 ID/PW를 검증해 **단일 공유 테스트 계정**(provider=test)을
find-or-create 하고 일반 계정과 동일한 JWT(SocialLoginResponse)를 발급한다.
이 계정의 결제는 request_payment 단계에서 0원으로 자동 발급된다(provider=test 감지).

`test_login_enabled`가 False면 비활성 — 라우터에서 404로 매핑(없는 것처럼).
심사 종료 후 플래그 False + 재배포로 엔드포인트/0원감지/FE버튼 전부 차단.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from app.domains.auth.application.request.test_login_request import TestLoginRequest
from app.domains.auth.application.response.account_profile_response import (
    AccountProfileResponse,
)
from app.domains.auth.application.response.social_login_response import (
    SocialLoginResponse,
)
from app.domains.auth.domain.entity.account import Account
from app.domains.auth.domain.port.account_repository_port import (
    AccountAlreadyExistsError,
    AccountRepositoryPort,
)
from app.domains.auth.domain.port.token_port import TokenIssuerPort
from app.domains.auth.domain.value_object.provider import Provider


class TestLoginDisabledError(Exception):
    """test_login_enabled=False — 비활성. 라우터에서 404."""

    __test__ = False  # pytest가 'Test*' 클래스로 오수집하지 않게


class TestLoginInvalidCredentialsError(Exception):
    """ID/PW 불일치. 라우터에서 401."""

    __test__ = False


class TestLoginUseCase:
    __test__ = False  # pytest 수집 대상 아님 (이름이 'Test'로 시작)
    # 단일 공유 테스트 계정 자연키 (provider=test, provider_user_id 고정)
    _PROVIDER_USER_ID = "card-review"

    def __init__(
        self,
        *,
        account_repo: AccountRepositoryPort,
        token_issuer: TokenIssuerPort,
        enabled: bool,
        username: str | None,
        password: str | None,
    ) -> None:
        self._account_repo = account_repo
        self._token_issuer = token_issuer
        self._enabled = enabled
        self._username = username
        self._password = password

    async def execute(self, request: TestLoginRequest) -> SocialLoginResponse:
        if not self._enabled or not self._username or not self._password:
            raise TestLoginDisabledError("테스트 로그인이 비활성화되어 있습니다.")
        # 상수시간 비교 (타이밍 공격 방지)
        ok_user = secrets.compare_digest(request.username, self._username)
        ok_pass = secrets.compare_digest(request.password, self._password)
        if not (ok_user and ok_pass):
            raise TestLoginInvalidCredentialsError("아이디 또는 비밀번호가 올바르지 않습니다.")

        now = datetime.now(UTC)
        account = await self._account_repo.find_by_provider_user(
            Provider.TEST, self._PROVIDER_USER_ID
        )
        if account is None:
            try:
                account = await self._account_repo.save(
                    Account(
                        provider=Provider.TEST,
                        provider_user_id=self._PROVIDER_USER_ID,
                        email=None,
                        email_verified=False,
                        nickname="심사용 테스트",
                        profile_image_url=None,
                        last_login_at=now,
                    )
                )
            except AccountAlreadyExistsError:
                # 동시 첫 로그인 레이스 — 승자가 만든 계정 재조회.
                account = await self._account_repo.find_by_provider_user(
                    Provider.TEST, self._PROVIDER_USER_ID
                )
        else:
            account.last_login_at = now
            account = await self._account_repo.update(account)

        if account is None or account.id is None:
            raise RuntimeError("테스트 계정 생성/조회 실패")

        return SocialLoginResponse(
            access_token=self._token_issuer.issue(account.id),
            is_new_account=False,
            profile=AccountProfileResponse.from_account(account),
        )
