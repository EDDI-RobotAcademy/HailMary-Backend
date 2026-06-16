"""PayApp 결제 요청 UseCase.

FE → BE → PayApp payrequest → mul_no/payurl 받음 → DB에 payment(status=READY) 저장 → FE에 payurl 반환.
실제 결제완료/취소 처리는 PayApp webhook (handle_payapp_feedback_usecase.py).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

from app.domains.payment.application.payment_ports import (
    TestAccountCheckerPort,
    UserLookupPort,
)
from app.domains.payment.application.request.request_payment_request import (
    RequestPaymentRequest,
)
from app.domains.payment.application.response.request_payment_response import (
    RequestPaymentResponse,
)
from app.domains.payment.application.usecase._grant_paid_report import grant_paid_report
from app.domains.payment.domain.entity.payment import Payment
from app.domains.payment.domain.port.payapp_payment_port import PayAppPaymentPort
from app.domains.payment.domain.port.payment_repository_port import (
    PaymentRepositoryPort,
)
from app.domains.payment.domain.value_object.character_price import (
    get_character_goods_name,
    get_character_price,
)
from app.domains.payment.domain.value_object.payment_status import PaymentStatus

# PayApp payrequest 필수 파라미터지만 smsuse=n 이라 SMS 발송 X — 더미.
_DUMMY_RECV_PHONE = "01000000000"


class RequestPaymentUseCase:
    def __init__(
        self,
        *,
        gateway: PayAppPaymentPort,
        repo: PaymentRepositoryPort,
        user_lookup: UserLookupPort,
        account_checker: TestAccountCheckerPort | None = None,
        background_composer: Callable[..., Coroutine[Any, Any, None]] | None = None,
    ) -> None:
        self._gateway = gateway
        self._repo = repo
        self._user_lookup = user_lookup
        self._account_checker = account_checker
        self._background_composer = background_composer

    async def execute(
        self, request: RequestPaymentRequest, account_id: int | None = None
    ) -> RequestPaymentResponse:
        # account_id: 로그인 상태면 계정 JWT에서 추출(선택). 결제를 계정에 귀속(보관함).
        # 1. sessionToken → user_id (만료/위조 차단)
        user_id = await self._user_lookup.find_user_id_by_session_token(
            request.session_token
        )
        if user_id is None:
            raise ValueError("세션이 만료되었거나 잘못된 토큰입니다.")

        # 2. BE 가격 마스터로 amount 결정 (FE 위변조 차단)
        amount = get_character_price(request.character)
        goods_name = get_character_goods_name(request.character)

        # 3. orderId 발급 (uuid4)
        order_id = f"order_{uuid.uuid4().hex}"

        # 3.5 카드사 심사용 테스트 계정이면 PayApp 건너뛰고 0원 무료 발급 (쿠폰과 동일 인프라).
        # account_checker는 test_login_enabled=False면 항상 False → 일반 사용자엔 영향 0.
        if (
            self._account_checker is not None
            and await self._account_checker.is_test_account(account_id)
        ):
            saved = await grant_paid_report(
                repo=self._repo,
                user_id=user_id,
                character=request.character,
                customer_email=request.customer_email,
                amount=0,
                order_id=order_id,
                payment_key=f"test-{order_id}",
                paid_report_creator=None,
                saju_hash_resolver=None,
                analytics=None,  # 테스트 결제는 Amplitude 미발화(분석 오염 방지)
                user_demographics=None,
                log_tag="TEST",
                method="test_free",
                background_composer=self._background_composer,
                account_id=account_id,
                device_id=request.device_id,
                session_id=request.session_id,
            )
            return RequestPaymentResponse(
                order_id=saved.order_id, payurl="", free_granted=True
            )

        # 4. PayApp payrequest
        result = await self._gateway.request_payment(
            order_id=order_id,
            amount=amount,
            goods_name=goods_name,
            recv_phone=_DUMMY_RECV_PHONE,
            recv_email=request.customer_email,
        )

        # 5. payment(status=READY) 저장. payment_key 자리에 PayApp mul_no 박음 (식별자 역할).
        # approved_at은 실제 결제완료 webhook 시점에 갱신.
        # device_id/session_id: webhook payment_completed 발화 때 FE 유저와 잇는 Amplitude 식별자.
        now = datetime.now(UTC)
        payment = Payment.from_approval(
            payment_key=result.mul_no,
            order_id=order_id,
            user_id=user_id,
            character=request.character,
            amount=amount,
            status=PaymentStatus.READY,
            customer_email=request.customer_email,
            approved_at=now,
            account_id=account_id,
            device_id=request.device_id,
            session_id=request.session_id,
        )
        await self._repo.save(payment)

        return RequestPaymentResponse(order_id=order_id, payurl=result.payurl)
