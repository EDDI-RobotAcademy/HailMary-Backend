"""CompletePortOnePaymentUseCase — 포트원 결제 검증 + 유료 발급 (HM-BE-85).

- PAID + 금액 일치 → grant_paid_report 호출, "PAID" 반환.
- 미결제 / 금액불일치 / 알수없는 캐릭터 → PortOneVerificationError.
- 테스트 채널 비허용 환경 → PortOneVerificationError.
- 이미 DONE → 포트원 조회 없이 idempotent 반환.
- webhook → 서명검증(payment_id) 후 동일 sync.
"""

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from app.domains.payment.application.usecase.complete_portone_payment_usecase import (
    CompletePortOnePaymentUseCase,
    PortOneVerificationError,
)
from app.domains.payment.domain.entity.payment import Payment
from app.domains.payment.domain.port.payment_repository_port import (
    DuplicatePaymentError,
)
from app.domains.payment.domain.port.portone_payment_port import PortOnePaymentInfo
from app.domains.payment.domain.value_object.payment_status import (
    CharacterCode,
    PaymentStatus,
)

_PAYMENT_ID = "order_portone_abc"


def _custom(**over: Any) -> str:
    data: dict[str, Any] = {
        "character": CharacterCode.YEONWOO.value,
        "sessionToken": "sess-tok",
        "email": "reviewer@example.com",
    }
    data.update(over)
    return json.dumps(data)


def _info(**over: Any) -> PortOnePaymentInfo:
    base: dict[str, Any] = {
        "payment_id": _PAYMENT_ID,
        "paid": True,
        "amount": 4900,
        "currency": "KRW",
        "order_name": "강연우의 정통 연애 사주",
        "custom_data": _custom(),
        "is_test_channel": True,
    }
    base.update(over)
    return PortOnePaymentInfo(**base)


class FakePortOne:
    def __init__(self, info: PortOnePaymentInfo | None, webhook_id: str | None = None) -> None:
        self._info = info
        self._webhook_id = webhook_id
        self.get_calls: list[str] = []

    async def get_payment(self, payment_id: str) -> PortOnePaymentInfo | None:
        self.get_calls.append(payment_id)
        return self._info

    async def verify_webhook(self, *, raw_body: str, headers: dict[str, str]) -> str | None:
        return self._webhook_id


class FakeRepo:
    def __init__(self, existing: Payment | None = None) -> None:
        self.saved: list[Payment] = []
        self._existing = existing

    async def find_by_order_id(self, order_id: str) -> Payment | None:
        return self._existing

    async def save(self, payment: Payment) -> Payment:
        self.saved.append(payment)
        return payment


class FakeUserLookup:
    def __init__(self, user_id: int | None = 42) -> None:
        self._user_id = user_id

    async def find_user_id_by_session_token(self, token: str) -> int | None:
        return self._user_id


class FakeComposer:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)

        async def _run() -> None:
            return None

        return _run()


def _usecase(
    *,
    portone: FakePortOne,
    repo: FakeRepo,
    composer: FakeComposer,
    user_lookup: FakeUserLookup | None = None,
    allow_test_channel: bool = True,
) -> CompletePortOnePaymentUseCase:
    return CompletePortOnePaymentUseCase(
        portone=portone,  # type: ignore[arg-type]
        repo=repo,  # type: ignore[arg-type]
        user_lookup=user_lookup or FakeUserLookup(),
        background_composer=composer,
        analytics=None,
        user_demographics=None,
        allow_test_channel=allow_test_channel,
    )


async def test_complete_paid_grants_report() -> None:
    portone = FakePortOne(_info())
    repo = FakeRepo()
    composer = FakeComposer()
    usecase = _usecase(portone=portone, repo=repo, composer=composer)

    result = await usecase.complete(_PAYMENT_ID, account_id=7)

    assert result == "PAID"
    assert len(repo.saved) == 1
    saved = repo.saved[0]
    assert saved.order_id == _PAYMENT_ID
    assert saved.amount == 4900
    assert saved.status == PaymentStatus.DONE
    assert len(composer.calls) == 1, "백그라운드 합성 1회 스폰"


async def test_complete_not_paid_raises() -> None:
    portone = FakePortOne(_info(paid=False))
    usecase = _usecase(portone=portone, repo=FakeRepo(), composer=FakeComposer())

    with pytest.raises(PortOneVerificationError):
        await usecase.complete(_PAYMENT_ID)


async def test_complete_amount_mismatch_raises() -> None:
    portone = FakePortOne(_info(amount=100))
    repo = FakeRepo()
    usecase = _usecase(portone=portone, repo=repo, composer=FakeComposer())

    with pytest.raises(PortOneVerificationError):
        await usecase.complete(_PAYMENT_ID)
    assert repo.saved == [], "금액 불일치면 발급 안 함"


async def test_complete_test_channel_disallowed_raises() -> None:
    portone = FakePortOne(_info(is_test_channel=True))
    usecase = _usecase(
        portone=portone,
        repo=FakeRepo(),
        composer=FakeComposer(),
        allow_test_channel=False,
    )

    with pytest.raises(PortOneVerificationError):
        await usecase.complete(_PAYMENT_ID)


async def test_complete_unknown_character_raises() -> None:
    portone = FakePortOne(_info(custom_data=_custom(character="ghost")))
    usecase = _usecase(portone=portone, repo=FakeRepo(), composer=FakeComposer())

    with pytest.raises(PortOneVerificationError):
        await usecase.complete(_PAYMENT_ID)


async def test_complete_idempotent_when_already_done() -> None:
    existing = Payment.from_approval(
        payment_key=f"portone-{_PAYMENT_ID}",
        order_id=_PAYMENT_ID,
        user_id=42,
        character=CharacterCode.YEONWOO,
        amount=4900,
        status=PaymentStatus.DONE,
        customer_email="reviewer@example.com",
        approved_at=datetime.now(UTC),
    )
    portone = FakePortOne(_info())
    repo = FakeRepo(existing=existing)
    usecase = _usecase(portone=portone, repo=repo, composer=FakeComposer())

    result = await usecase.complete(_PAYMENT_ID)

    assert result == "PAID"
    assert portone.get_calls == [], "이미 DONE이면 포트원 조회조차 안 함"
    assert repo.saved == [], "중복 발급 없음"


async def test_webhook_verifies_and_syncs() -> None:
    portone = FakePortOne(_info(), webhook_id=_PAYMENT_ID)
    repo = FakeRepo()
    composer = FakeComposer()
    usecase = _usecase(portone=portone, repo=repo, composer=composer)

    await usecase.handle_webhook(raw_body="{}", headers={})

    assert len(repo.saved) == 1, "웹훅이 결제를 동기화해 발급"


def _done_payment() -> Payment:
    return Payment.from_approval(
        payment_key=f"portone-{_PAYMENT_ID}",
        order_id=_PAYMENT_ID,
        user_id=42,
        character=CharacterCode.YEONWOO,
        amount=4900,
        status=PaymentStatus.DONE,
        customer_email="reviewer@example.com",
        approved_at=datetime.now(UTC),
    )


async def test_complete_duplicate_grant_is_idempotent() -> None:
    # FE 결제완료 호출 + 포트원 웹훅이 동시에 발급 → 진 쪽은 repo.save에서 DuplicatePaymentError.
    # 승자가 이미 DONE 커밋 → 500이 아니라 "PAID"(idempotent)로 처리돼야 함 (prod 사고 회귀).
    class RacingRepo(FakeRepo):
        def __init__(self) -> None:
            super().__init__()
            self._won = False

        async def find_by_order_id(self, order_id: str) -> Payment | None:
            return _done_payment() if self._won else None  # 승자 커밋 후엔 DONE

        async def save(self, payment: Payment) -> Payment:
            self._won = True  # 동시 승자가 방금 커밋한 상황 모사
            raise DuplicatePaymentError("order_id 중복")

    portone = FakePortOne(_info())
    usecase = _usecase(portone=portone, repo=RacingRepo(), composer=FakeComposer())

    result = await usecase.complete(_PAYMENT_ID)

    assert result == "PAID"


async def test_complete_duplicate_but_not_done_reraises() -> None:
    # order_id 충돌인데 DONE이 아니면(예외 상황) 거짓 PAID 대신 재raise(500).
    class DupRepo(FakeRepo):
        async def save(self, payment: Payment) -> Payment:
            raise DuplicatePaymentError("order_id 중복")

    portone = FakePortOne(_info())
    usecase = _usecase(portone=portone, repo=DupRepo(), composer=FakeComposer())

    with pytest.raises(DuplicatePaymentError):
        await usecase.complete(_PAYMENT_ID)


async def test_webhook_transient_error_propagates() -> None:
    # 일시 오류(DB blip 등)는 웹훅 밖으로 전파돼야 포트원이 재시도함(모바일 발급 유실 방지).
    class BoomPortOne(FakePortOne):
        async def get_payment(self, payment_id: str) -> PortOnePaymentInfo | None:
            raise RuntimeError("db blip")

    portone = BoomPortOne(_info(), webhook_id=_PAYMENT_ID)
    usecase = _usecase(portone=portone, repo=FakeRepo(), composer=FakeComposer())

    with pytest.raises(RuntimeError):
        await usecase.handle_webhook(raw_body="{}", headers={})


async def test_webhook_verification_error_swallowed() -> None:
    # 영구 실패(미완료 등)는 흡수 → 재시도 무의미. (예외 밖으로 안 나감)
    portone = FakePortOne(_info(paid=False), webhook_id=_PAYMENT_ID)
    repo = FakeRepo()
    usecase = _usecase(portone=portone, repo=repo, composer=FakeComposer())

    await usecase.handle_webhook(raw_body="{}", headers={})

    assert repo.saved == []


async def test_webhook_unverified_noop() -> None:
    portone = FakePortOne(_info(), webhook_id=None)
    repo = FakeRepo()
    usecase = _usecase(portone=portone, repo=repo, composer=FakeComposer())

    await usecase.handle_webhook(raw_body="bad", headers={})

    assert repo.saved == [], "서명 검증 실패면 아무것도 안 함"
