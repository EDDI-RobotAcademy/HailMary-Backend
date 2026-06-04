"""결제 도메인에서 분석 시스템(Amplitude 등)으로 이벤트를 보내는 Port.

Hexagonal 룰: payment 도메인은 Amplitude SDK / httpx 를 직접 import 하지 않는다.
main.py가 인프라 어댑터를 주입한다.

호출 측은 fire-and-forget 으로 부르므로, 구현체는 예외를 던지지 않는다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class AnalyticsPort(Protocol):
    async def track_payment_completed(
        self,
        *,
        user_id: int,
        device_id: str | None,
        session_id: int | None,
        order_id: str,
        character: str,
        amount: int,
        method: str | None,
        easy_pay_provider: str | None,
        card_issuer_code: str | None,
        bank_code: str | None,
        approved_at: datetime,
        gender: str | None,
        birth_year: int | None = None,
    ) -> None: ...

    async def track_payment_amount_mismatch(
        self,
        *,
        user_id: int,
        order_id: str,
        character: str,
        intended_amount: int,
        received_amount: int,
    ) -> None:
        """결제 금액 변조 의심(webhook price ≠ DB amount) 1차 방어선 신호.

        기본 구현은 no-op — 분석 어댑터가 미구현이어도 안전하게 동작.
        """
        ...
