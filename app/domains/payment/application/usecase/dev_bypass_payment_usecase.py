"""staging/local 전용 결제 패스 UseCase.

PayApp 결제 단계를 건너뛰고 즉시 payment 레코드를 DONE 상태로 생성 +
PaidReport 합성 트리거. QA 시 결제 단계를 매번 실행하지 않기 위함.

⚠️ `app_env == "prod"` 에서는 router에서 등록 자체를 안 함 (main.py 분기).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from app.domains.payment.application.payment_ports import (
    PaidReportCreatorPort,
    SajuHashResolverPort,
    UserDemographicsPort,
    UserLookupPort,
    safe_track_payment_completed,
)
from app.domains.payment.domain.entity.payment import Payment
from app.domains.payment.domain.port.analytics_port import AnalyticsPort
from app.domains.payment.domain.port.payment_repository_port import (
    PaymentRepositoryPort,
)
from app.domains.payment.domain.value_object.character_price import (
    get_character_price,
)
from app.domains.payment.domain.value_object.payment_status import (
    CharacterCode,
    PaymentStatus,
)

logger = logging.getLogger(__name__)


class DevBypassPaymentUseCase:
    def __init__(
        self,
        *,
        repo: PaymentRepositoryPort,
        user_lookup: UserLookupPort,
        paid_report_creator: PaidReportCreatorPort | None = None,
        saju_hash_resolver: SajuHashResolverPort | None = None,
        analytics: AnalyticsPort | None = None,
        user_demographics: UserDemographicsPort | None = None,
    ) -> None:
        self._repo = repo
        self._user_lookup = user_lookup
        self._paid_report_creator = paid_report_creator
        self._saju_hash_resolver = saju_hash_resolver
        self._analytics = analytics
        self._user_demographics = user_demographics

    async def execute(
        self,
        *,
        session_token: str,
        character: CharacterCode,
        customer_email: str,
    ) -> str:
        """결제 통과 처리. 응답: orderId (FE가 /saju/paid/{orderId}/loading 로 이동)."""
        user_id = await self._user_lookup.find_user_id_by_session_token(session_token)
        if user_id is None:
            raise ValueError("세션이 만료되었거나 잘못된 토큰입니다.")

        order_id = f"bypass_{uuid.uuid4().hex}"
        amount = get_character_price(character)
        now = datetime.now(UTC)

        payment = Payment.from_approval(
            payment_key=f"dev-bypass-{order_id}",
            order_id=order_id,
            user_id=user_id,
            character=character,
            amount=amount,
            status=PaymentStatus.DONE,
            customer_email=customer_email,
            approved_at=now,
        )
        saved = await self._repo.save(payment)
        logger.warning(
            "[DEV BYPASS] payment created order=%s user=%s amount=%s — production 모드에서는 노출되면 안 됨",
            saved.order_id,
            saved.user_id,
            saved.amount,
        )

        # PaidReport 합성 트리거 (실 결제 플로와 동일)
        if self._paid_report_creator is not None:
            saju_hash: str | None = None
            if self._saju_hash_resolver is not None:
                saju_hash = await self._saju_hash_resolver.resolve(saved.user_id)
            try:
                await self._paid_report_creator.execute(
                    order_id=saved.order_id,
                    saju_hash=saju_hash or saved.order_id,
                    user_id=saved.user_id,
                    customer_email=saved.customer_email,
                    expires_at=saved.expires_at,
                    character=saved.character.value,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("[DEV BYPASS] paid_report_creator failed: %s", e)

        # Amplitude 트래킹 (테스트 분석용)
        if self._analytics is not None:
            gender: str | None = None
            birth_year: int | None = None
            if self._user_demographics is not None:
                try:
                    gender = await self._user_demographics.find_gender_by_user_id(
                        saved.user_id
                    )
                    birth_year = (
                        await self._user_demographics.find_birth_year_by_user_id(
                            saved.user_id
                        )
                    )
                except Exception as e:  # noqa: BLE001
                    logger.warning("[DEV BYPASS] user_demographics failed: %s", e)
            # await로 확실 전송 (webhook usecase와 동일 — fire-and-forget GC 유실 방지).
            await safe_track_payment_completed(
                analytics=self._analytics,
                user_id=saved.user_id,
                device_id=None,
                session_id=None,
                order_id=saved.order_id,
                character=saved.character.value,
                amount=saved.amount,
                method="dev_bypass",  # 실 결제수단 없음 — 테스트 구분용
                easy_pay_provider=None,
                card_issuer_code=None,
                bank_code=None,
                approved_at=saved.approved_at,
                gender=gender,
                birth_year=birth_year,
            )

        return saved.order_id
