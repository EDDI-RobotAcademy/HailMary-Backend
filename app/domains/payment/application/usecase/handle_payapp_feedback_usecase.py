"""PayApp webhook(feedbackurl) 처리 UseCase.

PayApp → BE 호출. linkkey/linkval/price 검증 후 pay_state 별로 payment 상태 갱신.
결제완료(pay_state=4) 시 PaidReport 합성 + Amplitude 트래킹(payment_completed).
- pay_type 으로 결제수단(카드/카카오페이/페이코/애플페이/계좌이체 등)을 사후 식별.
- gender/birth_year(연령대)를 인구통계 속성으로 동봉.
금액 변조 의심(price ≠ DB amount) 시 payment_amount_mismatch 발화.
멱등성: 같은 (order_id, pay_state) 중복 처리 방지.

⚠️ Amplitude 발화는 반드시 await (구버전 asyncio.create_task는 webhook 응답 후
GC되어 payment_completed가 간헐 유실됨). safe_* 래퍼가 예외를 swallow하므로
await해도 PayApp 응답("SUCCESS")을 막지 않는다. → payment_completed = 신뢰 가능한 단일 진실원.
응답은 반드시 텍스트 "SUCCESS" (HTTP 200) — checkretry=y 라 SUCCESS 아니면 PayApp이 10회 재시도.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from app.domains.payment.application.payment_ports import (
    PaidReportCreatorPort,
    SajuHashResolverPort,
    UserDemographicsPort,
    safe_track_payment_amount_mismatch,
    safe_track_payment_completed,
)
from app.domains.payment.application.usecase._grant_paid_report import (
    _spawn_background,
)
from app.domains.payment.domain.port.analytics_port import AnalyticsPort
from app.domains.payment.domain.port.payment_repository_port import (
    PaymentRepositoryPort,
)
from app.domains.payment.domain.value_object.payment_status import PaymentStatus

logger = logging.getLogger(__name__)

# PayApp pay_state 코드 → 우리 PaymentStatus 매핑
_PAY_STATE_TO_STATUS: dict[str, PaymentStatus] = {
    "1": PaymentStatus.READY,
    "4": PaymentStatus.DONE,
    "8": PaymentStatus.ABORTED,
    "32": PaymentStatus.ABORTED,
    "9": PaymentStatus.CANCELED,
    "64": PaymentStatus.CANCELED,
    "10": PaymentStatus.WAITING_FOR_DEPOSIT,
    "70": PaymentStatus.PARTIAL_CANCELED,
    "71": PaymentStatus.PARTIAL_CANCELED,
}

# PayApp pay_type 정수 코드 → 사람이 읽는 결제수단 문자열.
# 사용자가 PayApp 외부 페이지(이미지3)에서 고른 결제수단의 '결과'를 사후적으로 식별.
# (외부 페이지 클릭 자체는 트래킹 불가하나 webhook이 선택 결과를 돌려줌)
_PAY_TYPE_TO_METHOD: dict[str, str] = {
    "1": "card",        # 신용/체크카드
    "2": "phone",       # 휴대폰결제
    "4": "face",        # 대면결제
    "6": "transfer",    # 계좌이체
    "7": "vbank",       # 가상계좌
    "15": "kakaopay",
    "16": "naverpay",
    "17": "recurring",  # 정기결제
    "21": "smilepay",
    "22": "wechat",
    "23": "applepay",
    "24": "myaccount",
    "25": "tosspay",
    # ⚠️ 26 미검증: PayApp 공식 webhook pay_type 표(04-webhook.md)는 25(토스페이)에서 끝 — 26/payco 없음.
    #   페이코는 결제수단으론 지원되나(payrequest openpaytype) 결과 pay_type 코드가 명세에 없음.
    #   카드 기반이라 pay_type=1(card)로 올 가능성 → 그 경우 이 매핑은 안 잡힘. 실 결제 payload로 확정 필요.
    "26": "payco",
}
# 간편결제로 분류되는 pay_type → easy_pay_provider 로도 기록.
_EASY_PAY_METHODS = {
    "kakaopay",
    "naverpay",
    "smilepay",
    "applepay",
    "tosspay",
    "payco",
    "wechat",
}


class FeedbackResult:
    """webhook 처리 결과. router는 모두 "SUCCESS" 텍스트로 응답."""

    def __init__(self, *, ok: bool, reason: str = "") -> None:
        self.ok = ok
        self.reason = reason


class HandlePayAppFeedbackUseCase:
    def __init__(
        self,
        *,
        repo: PaymentRepositoryPort,
        expected_linkkey: str,
        expected_linkval: str,
        background_composer: Callable[..., Coroutine[Any, Any, None]] | None = None,
        paid_report_creator: PaidReportCreatorPort | None = None,
        saju_hash_resolver: SajuHashResolverPort | None = None,
        analytics: AnalyticsPort | None = None,
        user_demographics: UserDemographicsPort | None = None,
    ) -> None:
        self._repo = repo
        self._expected_linkkey = expected_linkkey
        self._expected_linkval = expected_linkval
        self._background_composer = background_composer
        self._paid_report_creator = paid_report_creator
        self._saju_hash_resolver = saju_hash_resolver
        self._analytics = analytics
        self._user_demographics = user_demographics

    async def execute(self, form: dict[str, Any]) -> FeedbackResult:
        # 1. 인증 검증
        if form.get("linkkey") != self._expected_linkkey:
            logger.warning("PayApp feedback linkkey mismatch")
            return FeedbackResult(ok=False, reason="linkkey_mismatch")
        if form.get("linkval") != self._expected_linkval:
            logger.warning("PayApp feedback linkval mismatch")
            return FeedbackResult(ok=False, reason="linkval_mismatch")

        order_id = form.get("var1")
        mul_no = form.get("mul_no")
        pay_state = form.get("pay_state")
        price_str = form.get("price")

        if not order_id or not pay_state:
            logger.warning(
                "PayApp feedback missing required fields (order_id=%s, pay_state=%s)",
                order_id,
                pay_state,
            )
            return FeedbackResult(ok=False, reason="missing_fields")

        # 2. payment 조회 + 금액 검증
        payment = await self._repo.find_by_order_id(order_id)
        if payment is None:
            logger.warning("PayApp feedback unknown order_id=%s", order_id)
            return FeedbackResult(ok=False, reason="unknown_order")

        # PayApp price는 string. payment.amount는 int. 비교 위해 변환.
        try:
            received_amount = int(str(price_str))
        except (ValueError, TypeError):
            logger.warning("PayApp feedback invalid price=%s", price_str)
            return FeedbackResult(ok=False, reason="invalid_price")
        if received_amount != payment.amount:
            logger.warning(
                "PayApp feedback amount mismatch: db=%s, payapp=%s",
                payment.amount,
                received_amount,
            )
            # 금액 변조 의심 1차 방어선 — Amplitude 발화.
            # await로 확실 전송(응답 전 완료). safe_* 래퍼가 모든 예외를 swallow하므로
            # Amplitude 장애가 webhook 응답을 막지 않음.
            if self._analytics is not None:
                await safe_track_payment_amount_mismatch(
                    analytics=self._analytics,
                    user_id=payment.user_id,
                    order_id=payment.order_id,
                    character=payment.character.value,
                    intended_amount=payment.amount,
                    received_amount=received_amount,
                )
            return FeedbackResult(ok=False, reason="amount_mismatch")

        # 3. pay_state 매핑
        new_status = _PAY_STATE_TO_STATUS.get(str(pay_state))
        if new_status is None:
            logger.warning("PayApp feedback unknown pay_state=%s", pay_state)
            # 알 수 없는 상태도 SUCCESS 응답 — 재시도 방지
            return FeedbackResult(ok=True, reason="unknown_pay_state_ignored")

        # 4. 멱등성 — 이미 같은 상태면 skip (PayApp가 재시도해도 안전)
        if payment.status == new_status:
            return FeedbackResult(ok=True, reason="duplicate_skipped")

        # 5. 상태 갱신
        approved_at: datetime | None = None
        if new_status == PaymentStatus.DONE:
            approved_at = _parse_pay_date(form.get("pay_date")) or datetime.now(UTC)
        updated = await self._repo.update_status(
            order_id=order_id,
            status=new_status,
            approved_at=approved_at,
        )
        if updated is None:
            return FeedbackResult(ok=False, reason="update_failed")

        # 6. 결제완료 시 후속 처리 (AI 합성 + Amplitude)
        if new_status == PaymentStatus.DONE:
            await self._trigger_post_payment(
                updated,
                mul_no=str(mul_no or ""),
                pay_type=form.get("pay_type"),
                card_name=form.get("card_name"),
                vbank=form.get("vbank"),
            )

        return FeedbackResult(ok=True, reason=f"status_{new_status.value}")

    async def _trigger_post_payment(
        self,
        payment: Any,
        *,
        mul_no: str,
        pay_type: Any = None,
        card_name: Any = None,
        vbank: Any = None,
    ) -> None:
        # PaidReport 합성 트리거 — 백그라운드(자기 DB 세션)로 분리.
        # inline await면 합성이 끝날 때까지 webhook 트랜잭션 커밋이 지연돼 ① DONE이 늦게 보여
        # 이메일 팝업/결과 로딩(이탈방지 몰입 콘텐츠)이 마스킹할 시간 없이 합성이 먼저 끝나버리고
        # ② 응답 지연으로 checkretry 재시도→중복 합성 위험. 쿠폰 경로와 동일한 background_composer 사용.
        if self._background_composer is not None:
            _spawn_background(
                self._background_composer(
                    order_id=payment.order_id,
                    user_id=payment.user_id,
                    customer_email=payment.customer_email,
                    expires_at=payment.expires_at,
                    character=payment.character.value,
                )
            )
        elif self._paid_report_creator is not None:
            # fallback: composer 미주입 구성(테스트 등)에서는 기존대로 inline.
            saju_hash: str | None = None
            if self._saju_hash_resolver is not None:
                saju_hash = await self._saju_hash_resolver.resolve(payment.user_id)
            try:
                await self._paid_report_creator.execute(
                    order_id=payment.order_id,
                    saju_hash=saju_hash or payment.order_id,
                    user_id=payment.user_id,
                    customer_email=payment.customer_email,
                    expires_at=payment.expires_at,
                    character=payment.character.value,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("paid_report_creator failed: %s", e)

        # Amplitude 트래킹. device_id/session_id는 결제 요청 시점에 FE가 보내 Payment에
        # 저장해둔 값 — 이걸 실어야 payment_completed가 FE 유저 흐름과 이어진다.
        # (NULL이면 구버전 FE 주문 — user_id 단독 발화로 폴백.)
        if self._analytics is not None:
            gender: str | None = None
            birth_year: int | None = None
            if self._user_demographics is not None:
                try:
                    gender = await self._user_demographics.find_gender_by_user_id(
                        payment.user_id
                    )
                    birth_year = (
                        await self._user_demographics.find_birth_year_by_user_id(
                            payment.user_id
                        )
                    )
                except Exception as e:  # noqa: BLE001
                    logger.warning("user_demographics failed: %s", e)

            # PayApp webhook의 pay_type → 결제수단 식별 (이미지3 선택 결과를 사후 기록).
            method = _PAY_TYPE_TO_METHOD.get(str(pay_type)) if pay_type else None
            easy_pay_provider = method if method in _EASY_PAY_METHODS else None
            # 카드결제면 카드사, 가상계좌면 은행 정보 (PayApp이 줄 때만).
            card_issuer_code = str(card_name) if (method == "card" and card_name) else None
            bank_code = str(vbank) if (method == "vbank" and vbank) else None

            # ⚠️ await로 확실 전송 — 구버전은 asyncio.create_task(fire-and-forget)였으나,
            # 이벤트 루프가 task를 약한 참조로만 보유 → webhook 응답 후 GC되어
            # payment_completed가 "잡힐 때도 안 잡힐 때도" 있던 근본 원인이었음.
            # safe_* 래퍼가 모든 예외를 swallow하므로 await해도 결제 응답을 막지 않음.
            await safe_track_payment_completed(
                analytics=self._analytics,
                user_id=payment.user_id,
                device_id=payment.device_id,
                session_id=payment.session_id,
                order_id=payment.order_id,
                character=payment.character.value,
                amount=payment.amount,
                method=method,
                easy_pay_provider=easy_pay_provider,
                card_issuer_code=card_issuer_code,
                bank_code=bank_code,
                approved_at=payment.approved_at,
                gender=gender,
                birth_year=birth_year,
            )


# PayApp pay_date 는 KST 벽시계 — 라벨만 UTC 로 바꾸면 approved_at 이 9시간 미래가 되어
# 이메일 폴백 스위퍼의 grace 비교(approved_at < now-5분)가 9시간 밀린다. (CS #1, HM-BE-81)
_KST = timezone(timedelta(hours=9))


def _parse_pay_date(value: Any) -> datetime | None:
    """PayApp pay_date 형식: 'YYYY-MM-DD HH:MM:SS' (KST). KST로 해석 후 UTC 변환 저장."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return (
            datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            .replace(tzinfo=_KST)
            .astimezone(UTC)
        )
    except ValueError:
        return None
