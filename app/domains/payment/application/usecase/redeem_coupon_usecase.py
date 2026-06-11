"""무료 쿠폰 리뎀션 UseCase (prod 노출).

유효한 1회용 코드를 원자적으로 소진하고 amount=0 결제(DONE)를 생성해
PayApp 을 우회하면서 유료 결과지 합성을 트리거한다.

결과지 합성은 **백그라운드**(`background_composer`)로 돌려 redeem 응답을 막지 않는다 —
도윤 결과지의 긴 AI 합성 대기를 버튼에서 떼어내 결과 로딩 화면이 흡수하게 한다.
dev bypass 와 동일 골격이되, 환경 가드 대신 "유효 쿠폰 코드"가 가드 역할.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

from app.domains.payment.application.payment_ports import (
    UserDemographicsPort,
    UserLookupPort,
)
from app.domains.payment.application.usecase._grant_paid_report import (
    grant_paid_report,
)
from app.domains.payment.domain.port.analytics_port import AnalyticsPort
from app.domains.payment.domain.port.coupon_repository_port import (
    CouponRepositoryPort,
)
from app.domains.payment.domain.port.payment_repository_port import (
    PaymentRepositoryPort,
)
from app.domains.payment.domain.service.coupon_code_generator import (
    normalize_coupon_code,
)
from app.domains.payment.domain.value_object.payment_status import CharacterCode

logger = logging.getLogger(__name__)


class CouponNotRedeemableError(Exception):
    """쿠폰이 없거나 이미 소진됨 — 라우터에서 409 로 매핑."""


class RedeemCouponUseCase:
    def __init__(
        self,
        *,
        coupon_repo: CouponRepositoryPort,
        repo: PaymentRepositoryPort,
        user_lookup: UserLookupPort,
        background_composer: Callable[..., Coroutine[Any, Any, None]] | None = None,
        analytics: AnalyticsPort | None = None,
        user_demographics: UserDemographicsPort | None = None,
    ) -> None:
        self._coupon_repo = coupon_repo
        self._repo = repo
        self._user_lookup = user_lookup
        self._background_composer = background_composer
        self._analytics = analytics
        self._user_demographics = user_demographics

    async def execute(
        self,
        *,
        session_token: str,
        character: CharacterCode,
        customer_email: str,
        code: str,
        account_id: int | None = None,
        device_id: str | None = None,
        session_id: int | None = None,
    ) -> str:
        """쿠폰 소진 + 무료 결과지 발급. 응답: orderId.

        순서가 핵심: user 확인 → 원자적 소진 → 발급. 소진을 발급보다 먼저 잡아
        동시 제출을 직렬화한다.
        """
        user_id = await self._user_lookup.find_user_id_by_session_token(session_token)
        if user_id is None:
            raise ValueError("세션이 만료되었거나 잘못된 토큰입니다.")

        normalized = normalize_coupon_code(code)
        order_id = f"coupon_{uuid.uuid4().hex}"

        redeemed = await self._coupon_repo.redeem_if_active(
            code=normalized,
            user_id=user_id,
            order_id=order_id,
            used_at=datetime.now(UTC),
        )
        if not redeemed:
            raise CouponNotRedeemableError("사용할 수 없는 쿠폰입니다.")

        logger.warning(
            "[COUPON] redeemed code-suffix=%s user=%s order=%s",
            normalized[-4:],
            user_id,
            order_id,
        )

        saved = await grant_paid_report(
            repo=self._repo,
            user_id=user_id,
            character=character,
            customer_email=customer_email,
            amount=0,  # 100% 무료 — PayApp 완전 우회
            order_id=order_id,
            payment_key=f"coupon-{order_id}",
            paid_report_creator=None,
            saju_hash_resolver=None,
            analytics=self._analytics,
            user_demographics=self._user_demographics,
            log_tag="COUPON",
            method="coupon",  # 무료 쿠폰 결제 — 분석 구분용
            background_composer=self._background_composer,  # 합성은 백그라운드(응답 비대기)
            account_id=account_id,  # 로그인 시 보관함 귀속
            device_id=device_id,  # Amplitude FE 유저 연결
            session_id=session_id,
        )
        return saved.order_id
