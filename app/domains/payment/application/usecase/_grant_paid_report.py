"""무료 발급(결제 우회) 공용 헬퍼.

dev bypass(staging/local)와 무료 쿠폰 리뎀션(prod) 모두 동일하게:
  Payment(status=DONE) 생성 → repo.save → PaidReport 합성 트리거 → Amplitude
를 수행한다. PayApp 정상 결제(webhook)와 달리 결제대행을 거치지 않는 경로의 공통부.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

from app.domains.payment.application.payment_ports import (
    PaidReportCreatorPort,
    SajuHashResolverPort,
    UserDemographicsPort,
    safe_track_payment_completed,
)
from app.domains.payment.domain.entity.payment import Payment
from app.domains.payment.domain.port.analytics_port import AnalyticsPort
from app.domains.payment.domain.port.payment_repository_port import (
    PaymentRepositoryPort,
)
from app.domains.payment.domain.value_object.payment_status import (
    CharacterCode,
    PaymentStatus,
)

logger = logging.getLogger(__name__)

# 백그라운드 합성 task 참조 보관 — Python 3.12+ fire-and-forget task는 참조를 안 잡으면
# GC 되어 실행 자체가 안 됨(메모리: asyncio task GC 가드). done 시 set에서 제거.
_BG_COMPOSE_TASKS: set[asyncio.Task[None]] = set()


def _spawn_background(coro: Coroutine[Any, Any, None]) -> None:
    task = asyncio.create_task(coro)
    _BG_COMPOSE_TASKS.add(task)
    task.add_done_callback(_BG_COMPOSE_TASKS.discard)


async def grant_paid_report(
    *,
    repo: PaymentRepositoryPort,
    user_id: int,
    character: CharacterCode,
    customer_email: str,
    amount: int,
    order_id: str,
    payment_key: str,
    paid_report_creator: PaidReportCreatorPort | None,
    saju_hash_resolver: SajuHashResolverPort | None,
    analytics: AnalyticsPort | None,
    user_demographics: UserDemographicsPort | None,
    log_tag: str,
    method: str | None = None,
    background_composer: Callable[..., Coroutine[Any, Any, None]] | None = None,
    account_id: int | None = None,
    device_id: str | None = None,
    session_id: int | None = None,
) -> Payment:
    """DONE 결제를 생성하고 유료 결과지 합성을 트리거한다. 저장된 Payment 반환.

    합성 모드:
    - `background_composer` 주어지면 → 결제 생성 후 합성을 **백그라운드 task**로 스폰하고
      즉시 반환(쿠폰 redeem — 도윤 AI 합성 대기를 응답에서 떼어내 결과 로딩 화면이 흡수).
    - None 이면 → 기존대로 `paid_report_creator.execute` 를 **inline await**(dev bypass).
    """
    now = datetime.now(UTC)
    payment = Payment.from_approval(
        payment_key=payment_key,
        order_id=order_id,
        user_id=user_id,
        character=character,
        amount=amount,
        status=PaymentStatus.DONE,
        customer_email=customer_email,
        approved_at=now,
        account_id=account_id,  # 로그인 시 계정 귀속 → 보관함 노출 (HM-BE-80)
        device_id=device_id,  # Amplitude FE 유저 연결 — payment_completed 발화에 사용
        session_id=session_id,
    )
    saved = await repo.save(payment)
    logger.warning(
        "[%s] payment created order=%s user=%s amount=%s",
        log_tag,
        saved.order_id,
        saved.user_id,
        saved.amount,
    )

    # PaidReport 합성 트리거. 실패해도 결제는 유지(graceful).
    if background_composer is not None:
        # 백그라운드 합성 — 응답을 막지 않음. 합성은 자기 DB 세션을 여는 composer 안에서 수행.
        _spawn_background(
            background_composer(
                order_id=saved.order_id,
                user_id=saved.user_id,
                customer_email=saved.customer_email,
                expires_at=saved.expires_at,
                character=saved.character.value,
            )
        )
    elif paid_report_creator is not None:
        # inline 합성 (dev bypass) — 실 결제 플로와 동일하게 응답 전 await.
        saju_hash: str | None = None
        if saju_hash_resolver is not None:
            saju_hash = await saju_hash_resolver.resolve(saved.user_id)
        try:
            await paid_report_creator.execute(
                order_id=saved.order_id,
                saju_hash=saju_hash or saved.order_id,
                user_id=saved.user_id,
                customer_email=saved.customer_email,
                expires_at=saved.expires_at,
                character=saved.character.value,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("[%s] paid_report_creator failed: %s", log_tag, e)

    # Amplitude 트래킹 — await로 확실 전송. (HMDA-42: create_task fire-and-forget 은
    # 응답 후 GC 되어 payment_completed 가 간헐 유실됨. safe_* 래퍼가 예외를 삼키므로
    # await 해도 응답을 막지 않는다.)
    if analytics is not None:
        gender: str | None = None
        birth_year: int | None = None
        if user_demographics is not None:
            try:
                gender = await user_demographics.find_gender_by_user_id(saved.user_id)
                birth_year = await user_demographics.find_birth_year_by_user_id(
                    saved.user_id
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("[%s] user_demographics failed: %s", log_tag, e)
        await safe_track_payment_completed(
            analytics=analytics,
            user_id=saved.user_id,
            device_id=saved.device_id,
            session_id=saved.session_id,
            order_id=saved.order_id,
            character=saved.character.value,
            amount=saved.amount,
            method=method,
            easy_pay_provider=None,
            card_issuer_code=None,
            bank_code=None,
            approved_at=saved.approved_at,
            gender=gender,
            birth_year=birth_year,
        )

    return saved
