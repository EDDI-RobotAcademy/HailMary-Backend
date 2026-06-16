"""소셜 로그인 라우터 + 계정 JWT 인증 의존성.

기존 사주 세션 인증(user/adapter/inbound/api/auth.py — session_token)과 별개.
헤더 규칙: 이 라우터와 보관함/깨비 저장 계열은 Authorization: Bearer <계정 JWT>.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.domains.auth.application.request.social_login_request import SocialLoginRequest
from app.domains.auth.application.request.test_login_request import TestLoginRequest
from app.domains.auth.application.request.update_last_used_request import (
    UpdateLastUsedRequest,
)
from app.domains.auth.application.response.account_profile_response import (
    AccountProfileResponse,
)
from app.domains.auth.application.response.social_login_response import (
    SocialLoginResponse,
)
from app.domains.auth.application.usecase.delete_account_usecase import (
    DeleteAccountUseCase,
)
from app.domains.auth.application.usecase.get_me_usecase import GetMeUseCase
from app.domains.auth.application.usecase.social_login_usecase import (
    SocialLoginUseCase,
    UnsupportedProviderError,
)
from app.domains.auth.application.usecase.test_login_usecase import (
    TestLoginDisabledError,
    TestLoginInvalidCredentialsError,
    TestLoginUseCase,
)
from app.domains.auth.application.usecase.update_last_used_usecase import (
    UpdateLastUsedUseCase,
)
from app.domains.auth.domain.port.oauth_client_port import OAuthExchangeError
from app.domains.auth.domain.port.token_port import TokenDecodeError, TokenIssuerPort

router = APIRouter(prefix="/api/auth", tags=["auth"])

_BEARER = "Bearer "


# main.py에서 app.dependency_overrides로 교체된다.
def get_social_login_usecase() -> SocialLoginUseCase:
    raise NotImplementedError


def get_test_login_usecase() -> TestLoginUseCase:
    raise NotImplementedError


def get_me_usecase() -> GetMeUseCase:
    raise NotImplementedError


def get_update_last_used_usecase() -> UpdateLastUsedUseCase:
    raise NotImplementedError


def get_delete_account_usecase() -> DeleteAccountUseCase:
    raise NotImplementedError


def get_token_issuer() -> TokenIssuerPort:
    raise NotImplementedError


# main.py에서 override — JWT 미설정/누락/위조 시 None(401 안 던짐). 선택적 계정 인지용.
async def get_optional_account_id(request: Request) -> int | None:
    raise NotImplementedError


async def get_current_account_id(
    request: Request,
    token_issuer: TokenIssuerPort = Depends(get_token_issuer),
) -> int:
    """Authorization: Bearer <계정 JWT> → account_id. 실패 시 401."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith(_BEARER):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth[len(_BEARER):].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return token_issuer.decode(token)
    except TokenDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired account token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


@router.post("/login", response_model=SocialLoginResponse)
async def social_login(
    body: SocialLoginRequest,
    usecase: SocialLoginUseCase = Depends(get_social_login_usecase),
) -> SocialLoginResponse:
    try:
        return await usecase.execute(body)
    except UnsupportedProviderError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except OAuthExchangeError as e:
        # code 만료/위조/redirect_uri 불일치 등 — 제공자 교환 실패
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


@router.post("/test-login", response_model=SocialLoginResponse)
async def test_login(
    body: TestLoginRequest,
    usecase: TestLoginUseCase = Depends(get_test_login_usecase),
) -> SocialLoginResponse:
    """카드사 심사용 테스트 로그인 (ID/PW). 비활성 시 404(없는 것처럼)."""
    try:
        return await usecase.execute(body)
    except TestLoginDisabledError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except TestLoginInvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


@router.get("/me", response_model=AccountProfileResponse)
async def get_me(
    account_id: int = Depends(get_current_account_id),
    usecase: GetMeUseCase = Depends(get_me_usecase),
) -> AccountProfileResponse:
    try:
        return await usecase.execute(account_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    account_id: int = Depends(get_current_account_id),
    usecase: DeleteAccountUseCase = Depends(get_delete_account_usecase),
) -> None:
    """회원탈퇴 — 계정 + 귀속 데이터 정리(결제 기록은 법적 보관, account_id만 언링크)."""
    await usecase.execute(account_id)


@router.post("/last-used", status_code=status.HTTP_204_NO_CONTENT)
async def update_last_used(
    body: UpdateLastUsedRequest,
    account_id: int = Depends(get_current_account_id),
    usecase: UpdateLastUsedUseCase = Depends(get_update_last_used_usecase),
) -> None:
    """로그인 사용자가 설문 제출 시 계정 마지막 사용값 갱신 (FE fire-and-forget)."""
    try:
        await usecase.execute(account_id, body)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
