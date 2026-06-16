"""포트원(PortOne) V2 결제 클라이언트 — PortOnePaymentPort 구현.

공식 동기 SDK(portone-server-sdk)를 asyncio.to_thread 로 감싸 async 플로에 맞춘다.
"""

from __future__ import annotations

import asyncio
import logging

import portone_server_sdk as portone

from app.domains.payment.domain.port.portone_payment_port import (
    PortOnePaymentInfo,
    PortOnePaymentPort,
)

logger = logging.getLogger(__name__)


class PortOneClient(PortOnePaymentPort):
    def __init__(self, *, api_secret: str, webhook_secret: str | None) -> None:
        self._client = portone.PaymentClient(secret=api_secret)
        self._webhook_secret = webhook_secret

    async def get_payment(self, payment_id: str) -> PortOnePaymentInfo | None:
        def _call() -> PortOnePaymentInfo | None:
            try:
                payment = self._client.get_payment(payment_id=payment_id)
            except portone.payment.GetPaymentError as e:
                logger.warning("[PORTONE] get_payment failed id=%s: %s", payment_id, e)
                return None
            paid = isinstance(payment, portone.payment.PaidPayment)
            amount_obj = getattr(payment, "amount", None)
            amount = int(getattr(amount_obj, "total", 0) or 0)
            channel = getattr(payment, "channel", None)
            is_test = getattr(channel, "type", "") == "TEST"
            return PortOnePaymentInfo(
                payment_id=getattr(payment, "id", payment_id),
                paid=paid,
                amount=amount,
                currency=getattr(payment, "currency", "KRW") or "KRW",
                order_name=getattr(payment, "order_name", "") or "",
                custom_data=getattr(payment, "custom_data", None),
                is_test_channel=is_test,
            )

        return await asyncio.to_thread(_call)

    async def verify_webhook(
        self, *, raw_body: str, headers: dict[str, str]
    ) -> str | None:
        secret = self._webhook_secret
        if not secret:
            return None

        def _call() -> str | None:
            try:
                webhook = portone.webhook.verify(secret, raw_body, headers)
            except portone.webhook.WebhookVerificationError as e:
                logger.warning("[PORTONE] webhook verify failed: %s", e)
                return None
            data = getattr(webhook, "data", None)
            payment_id = getattr(data, "payment_id", None)
            return payment_id if isinstance(payment_id, str) else None

        return await asyncio.to_thread(_call)
