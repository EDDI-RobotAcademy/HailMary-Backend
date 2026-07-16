"""포트원(PortOne) V2 결제 조회/웹훅 검증 Port — 순수 도메인.

payment 도메인이 포트원 SDK(외부 라이브러리)에 직접 의존하지 않도록 추상화.
구현체(어댑터)는 adapter/outbound/external/portone_client.py 에 둔다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PortOnePaymentInfo:
    """포트원 결제 단건 조회 결과(도메인 표현). SDK 타입에 의존하지 않는 순수 VO."""

    payment_id: str
    paid: bool  # PaidPayment(결제 완료) 여부
    amount: int  # 실제 결제 금액 (amount.total)
    currency: str
    order_name: str
    custom_data: str | None  # requestPayment 시 실어 보낸 컨텍스트(JSON 문자열)
    is_test_channel: bool  # 테스트 채널(channel.type == "TEST") 여부


class PortOnePaymentPort(Protocol):
    async def get_payment(self, payment_id: str) -> PortOnePaymentInfo | None:
        """결제 단건 조회. 조회 실패/미존재 시 None."""
        ...

    async def verify_webhook(
        self, *, raw_body: str, headers: dict[str, str]
    ) -> str | None:
        """웹훅 서명 검증 후 payment_id 반환. 검증 실패/무관 이벤트면 None."""
        ...
