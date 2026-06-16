"""RequestPaymentUseCase — 카드사 심사용 테스트 계정 0원 분기 (HM-BE-84).

- 테스트 계정(checker→True): PayApp 미호출 + grant_paid_report로 amount=0 DONE 결제 +
  free_granted=True. (백그라운드 합성 스폰)
- 일반 계정(checker→False): 기존대로 PayApp 호출 + free_granted=False.
"""

import asyncio
from collections.abc import Coroutine
from typing import Any

from app.domains.payment.application.request.request_payment_request import (
    RequestPaymentRequest,
)
from app.domains.payment.application.usecase.request_payment_usecase import (
    RequestPaymentUseCase,
)
from app.domains.payment.domain.entity.payment import Payment
from app.domains.payment.domain.value_object.payment_status import (
    CharacterCode,
)


class FakeGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def request_payment(self, **kwargs: Any) -> Any:
        self.calls += 1

        class _Result:
            mul_no = "mul-123"
            payurl = "https://payapp.kr/pay/abc"

        return _Result()


class FakePaymentRepo:
    def __init__(self) -> None:
        self.saved: list[Payment] = []

    async def save(self, payment: Payment) -> Payment:
        self.saved.append(payment)
        return Payment(
            payment_key=payment.payment_key,
            order_id=payment.order_id,
            user_id=payment.user_id,
            character=payment.character,
            amount=payment.amount,
            status=payment.status,
            customer_email=payment.customer_email,
            approved_at=payment.approved_at,
            expires_at=payment.expires_at,
            id=len(self.saved),
        )


class FakeUserLookup:
    async def find_user_id_by_session_token(self, token: str) -> int | None:
        return 42


class FakeChecker:
    def __init__(self, is_test: bool) -> None:
        self._is_test = is_test
        self.calls: list[int | None] = []

    async def is_test_account(self, account_id: int | None) -> bool:
        self.calls.append(account_id)
        return self._is_test


class FakeComposer:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> Coroutine[Any, Any, None]:
        self.calls.append(kwargs)

        async def _run() -> None:
            return None

        return _run()


def _request() -> RequestPaymentRequest:
    # 별칭(camelCase)로 구성 — FE 와이어 포맷과 동일.
    return RequestPaymentRequest.model_validate(
        {
            "sessionToken": "sess-tok",
            "character": CharacterCode.YEONWOO.value,
            "customerEmail": "reviewer@example.com",
        }
    )


def _usecase(*, gateway: FakeGateway, checker: FakeChecker, composer: FakeComposer) -> RequestPaymentUseCase:
    return RequestPaymentUseCase(
        gateway=gateway,  # type: ignore[arg-type]
        repo=FakePaymentRepo(),  # type: ignore[arg-type]
        user_lookup=FakeUserLookup(),
        account_checker=checker,
        background_composer=composer,
    )


async def test_test_account_skips_payapp_and_grants_free() -> None:
    gateway = FakeGateway()
    checker = FakeChecker(is_test=True)
    composer = FakeComposer()
    usecase = _usecase(gateway=gateway, checker=checker, composer=composer)

    res = await usecase.execute(_request(), account_id=7)

    assert res.free_granted is True
    assert res.payurl == ""
    assert gateway.calls == 0, "테스트 계정은 PayApp 호출 안 함"
    assert len(composer.calls) == 1, "합성 백그라운드 스폰 1회"
    await asyncio.sleep(0)  # 백그라운드 task tick


async def test_normal_account_uses_payapp() -> None:
    gateway = FakeGateway()
    checker = FakeChecker(is_test=False)
    composer = FakeComposer()
    usecase = _usecase(gateway=gateway, checker=checker, composer=composer)

    res = await usecase.execute(_request(), account_id=3)

    assert res.free_granted is False
    assert res.payurl == "https://payapp.kr/pay/abc"
    assert gateway.calls == 1, "일반 계정은 PayApp 정상 호출"
    assert composer.calls == [], "일반 계정은 무료 합성 스폰 없음"


async def test_no_account_id_uses_payapp() -> None:
    gateway = FakeGateway()
    checker = FakeChecker(is_test=False)
    usecase = _usecase(gateway=gateway, checker=checker, composer=FakeComposer())

    res = await usecase.execute(_request(), account_id=None)

    assert res.free_granted is False
    assert gateway.calls == 1
    assert checker.calls == [None], "account_id None도 checker에 전달(어댑터가 False 반환)"
