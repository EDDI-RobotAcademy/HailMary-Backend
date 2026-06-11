from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domains.payment.domain.value_object.payment_status import (
    CharacterCode,
    PaymentMethod,
    PaymentStatus,
)

REVIEW_PERIOD_DAYS = 30


@dataclass
class Payment:
    """결제 도메인 엔티티 — 토스페이먼츠 승인 결과를 우리 도메인 표현으로."""

    payment_key: str
    order_id: str
    user_id: int
    character: CharacterCode
    amount: int
    status: PaymentStatus
    customer_email: str
    approved_at: datetime
    expires_at: datetime
    method: PaymentMethod | None = None
    easy_pay_provider: str | None = None
    card_issuer_code: str | None = None
    bank_code: str | None = None
    # 결과지 메일 확정 후 발송 (2026-06-05): 확정 시각 / 발송 시각 (NULL=미발송)
    email_confirmed_at: datetime | None = None
    result_email_sent_at: datetime | None = None
    # 소셜 로그인 계정 귀속 (HM-BE-80). 로그인 상태 결제 시 요청 시점에 연결. NULL=비로그인 결제.
    account_id: int | None = None
    # Amplitude 식별자 — 결제 요청 시점의 FE device_id/session_id를 보관했다가
    # webhook payment_completed 발화에 그대로 실어 FE 유저 흐름과 잇는다. NULL=미전달(구버전 FE).
    device_id: str | None = None
    session_id: int | None = None
    id: int | None = None

    @classmethod
    def from_approval(
        cls,
        *,
        payment_key: str,
        order_id: str,
        user_id: int,
        character: CharacterCode,
        amount: int,
        status: PaymentStatus,
        customer_email: str,
        approved_at: datetime,
        method: PaymentMethod | None = None,
        easy_pay_provider: str | None = None,
        card_issuer_code: str | None = None,
        bank_code: str | None = None,
        account_id: int | None = None,
        device_id: str | None = None,
        session_id: int | None = None,
    ) -> "Payment":
        return cls(
            payment_key=payment_key,
            order_id=order_id,
            user_id=user_id,
            character=character,
            amount=amount,
            status=status,
            customer_email=customer_email,
            approved_at=approved_at,
            expires_at=approved_at + timedelta(days=REVIEW_PERIOD_DAYS),
            method=method,
            easy_pay_provider=easy_pay_provider,
            card_issuer_code=card_issuer_code,
            bank_code=bank_code,
            account_id=account_id,
            device_id=device_id,
            session_id=session_id,
        )

    def is_active(self, now: datetime) -> bool:
        return self.status == PaymentStatus.DONE and now < self.expires_at
