"""포트원(PortOne) 결제 완료 검증 + 유료 결과 발급 UseCase.

FE 결제창 완료(redirect) → /complete 호출, 또는 포트원 웹훅 → 동일 sync 로직.
서버에서 get_payment 로 결제를 재검증(PAID + 금액 일치)한 뒤에만 grant_paid_report
(쿠폰/테스트 계정과 동일 무료발급 인프라 재활용)로 유료 결과지를 발급한다.

결제 컨텍스트(character/sessionToken/email/account/device/session)는 requestPayment 시
customData(JSON)로 실어 보내며, complete/webhook 모두 이 customData에서 복원한다.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from app.domains.payment.application.payment_ports import (
    UserDemographicsPort,
    UserLookupPort,
)
from app.domains.payment.application.usecase._grant_paid_report import grant_paid_report
from app.domains.payment.domain.port.analytics_port import AnalyticsPort
from app.domains.payment.domain.port.payment_repository_port import (
    DuplicatePaymentError,
    PaymentRepositoryPort,
)
from app.domains.payment.domain.port.portone_payment_port import PortOnePaymentPort
from app.domains.payment.domain.value_object.character_price import get_character_price
from app.domains.payment.domain.value_object.payment_status import (
    CharacterCode,
    PaymentStatus,
)

logger = logging.getLogger(__name__)


class PortOneVerificationError(Exception):
    """포트원 결제 검증 실패 — 라우터에서 400 매핑."""


class CompletePortOnePaymentUseCase:
    def __init__(
        self,
        *,
        portone: PortOnePaymentPort,
        repo: PaymentRepositoryPort,
        user_lookup: UserLookupPort,
        background_composer: Callable[..., Coroutine[Any, Any, None]],
        analytics: AnalyticsPort | None = None,
        user_demographics: UserDemographicsPort | None = None,
        allow_test_channel: bool = False,
    ) -> None:
        self._portone = portone
        self._repo = repo
        self._user_lookup = user_lookup
        self._background_composer = background_composer
        self._analytics = analytics
        self._user_demographics = user_demographics
        self._allow_test_channel = allow_test_channel

    async def complete(self, payment_id: str, account_id: int | None = None) -> str:
        """결제 검증 후 유료 결과 발급. 반환: 'PAID'. (idempotent — 이미 DONE이면 바로 반환)"""
        if await self._already_done(payment_id):
            return "PAID"

        info = await self._portone.get_payment(payment_id)
        if info is None or not info.paid:
            raise PortOneVerificationError("결제가 완료되지 않았습니다.")
        if info.is_test_channel and not self._allow_test_channel:
            raise PortOneVerificationError("테스트 결제가 허용되지 않는 환경입니다.")

        custom = self._parse_custom_data(info.custom_data)
        character = self._resolve_character(custom)

        expected = get_character_price(character)
        if info.amount != expected:
            raise PortOneVerificationError(
                f"결제 금액이 일치하지 않습니다 (기대 {expected}, 실제 {info.amount})."
            )

        session_token = custom.get("sessionToken")
        customer_email = custom.get("email")
        if not isinstance(session_token, str) or not isinstance(customer_email, str):
            raise PortOneVerificationError("결제 컨텍스트(customData)가 불완전합니다.")

        user_id = await self._user_lookup.find_user_id_by_session_token(session_token)
        if user_id is None:
            raise PortOneVerificationError("세션이 만료되었거나 잘못된 토큰입니다.")

        # webhook ↔ complete 경합 대비 재확인 (DONE이면 중복 발급 안 함).
        if await self._already_done(payment_id):
            return "PAID"

        try:
            await grant_paid_report(
                repo=self._repo,
                user_id=user_id,
                character=character,
                customer_email=customer_email,
                amount=info.amount,
                order_id=payment_id,
                payment_key=f"portone-{payment_id}",
                paid_report_creator=None,
                saju_hash_resolver=None,
                analytics=self._analytics,
                user_demographics=self._user_demographics,
                log_tag="PORTONE",
                method="portone_kakaopay",
                background_composer=self._background_composer,
                account_id=account_id
                if account_id is not None
                else custom.get("accountId"),
                device_id=custom.get("deviceId"),
                session_id=custom.get("sessionId"),
            )
        except DuplicatePaymentError:
            # FE 결제완료 호출과 포트원 웹훅이 동시에 발급 시도 → 진 쪽은 여기.
            # 다른 요청이 이미 발급 완료 → idempotent 성공 처리(중복 합성/500 방지).
            logger.info(
                "[PORTONE] 중복 발급 감지(동시 complete/webhook) — 이미 발급됨 처리 id=%s",
                payment_id,
            )
        return "PAID"

    async def handle_webhook(self, *, raw_body: str, headers: dict[str, str]) -> None:
        """포트원 웹훅 — 서명 검증 후 sync. 어떤 실패에도 예외를 밖으로 던지지 않음
        (라우터가 항상 200을 반환해 재시도 폭주를 막기 위함)."""
        try:
            payment_id = await self._portone.verify_webhook(
                raw_body=raw_body, headers=headers
            )
            if payment_id is None:
                return
            await self.complete(payment_id)
        except PortOneVerificationError as e:
            logger.warning("[PORTONE webhook] 검증 실패: %s", e)
        except Exception:  # noqa: BLE001 — 웹훅은 항상 흡수 (재시도 무의미)
            logger.exception("[PORTONE webhook] 처리 중 예외")

    async def _already_done(self, payment_id: str) -> bool:
        existing = await self._repo.find_by_order_id(payment_id)
        return existing is not None and existing.status == PaymentStatus.DONE

    @staticmethod
    def _parse_custom_data(custom_data: str | None) -> dict[str, Any]:
        if not custom_data:
            return {}
        try:
            parsed = json.loads(custom_data)
        except (ValueError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _resolve_character(custom: dict[str, Any]) -> CharacterCode:
        raw = custom.get("character")
        try:
            return CharacterCode(raw)
        except ValueError as e:
            raise PortOneVerificationError(
                f"알 수 없는 캐릭터: {raw}"
            ) from e
