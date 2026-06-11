"""staging/local 전용 결제 패스 UseCase.

PayApp 결제 단계를 건너뛰고 즉시 payment 레코드를 DONE 상태로 생성 +
PaidReport 합성 트리거. QA 시 결제 단계를 매번 실행하지 않기 위함.

⚠️ `app_env == "prod"` 에서는 router에서 등록 자체를 안 함 (main.py 분기).

발급/합성 공통부는 `_grant_paid_report.grant_paid_report` 와 공유한다
(무료 쿠폰 리뎀션과 동일 동작 — env 가드 대신 코드 가드인 점만 다름).
"""

from __future__ import annotations

import logging
import uuid

from app.domains.payment.application.payment_ports import (
    PaidReportCreatorPort,
    SajuHashResolverPort,
    UserDemographicsPort,
    UserLookupPort,
)
from app.domains.payment.application.usecase._grant_paid_report import (
    grant_paid_report,
)
from app.domains.payment.domain.port.analytics_port import AnalyticsPort
from app.domains.payment.domain.port.payment_repository_port import (
    PaymentRepositoryPort,
)
from app.domains.payment.domain.value_object.character_price import (
    get_character_price,
)
from app.domains.payment.domain.value_object.payment_status import CharacterCode

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
        account_id: int | None = None,
        device_id: str | None = None,
        session_id: int | None = None,
    ) -> str:
        """결제 통과 처리. 응답: orderId (FE가 /saju/paid/{orderId}/loading 로 이동)."""
        user_id = await self._user_lookup.find_user_id_by_session_token(session_token)
        if user_id is None:
            raise ValueError("세션이 만료되었거나 잘못된 토큰입니다.")

        order_id = f"bypass_{uuid.uuid4().hex}"
        saved = await grant_paid_report(
            repo=self._repo,
            user_id=user_id,
            character=character,
            customer_email=customer_email,
            amount=get_character_price(character),
            order_id=order_id,
            payment_key=f"dev-bypass-{order_id}",
            paid_report_creator=self._paid_report_creator,
            saju_hash_resolver=self._saju_hash_resolver,
            analytics=self._analytics,
            user_demographics=self._user_demographics,
            log_tag="DEV BYPASS",
            method="dev_bypass",  # 실 결제수단 없음 — 테스트 구분용 (HMDA-42)
            account_id=account_id,  # 로그인 시 보관함 귀속
            device_id=device_id,  # Amplitude FE 유저 연결
            session_id=session_id,
        )
        return saved.order_id
