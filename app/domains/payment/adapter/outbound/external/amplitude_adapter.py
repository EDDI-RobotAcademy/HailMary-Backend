"""AnalyticsPort 의 Amplitude 구현체.

payment 도메인의 결제 완료 신호를 Amplitude HTTP API V2 페이로드로 변환해 전송한다.

PII 정책 (절대 변경 금지):
- event_properties 는 화이트리스트 키만 허용.
- customer_email / 이름 / 전화번호 / 생년월일(전체)은 절대 포함 금지.
- 단, 출생 '연도'(birth_year)·성별(gender)은 분석용 인구통계로 허용 (연도만, 월·일·시각 금지).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.payment.domain.port.analytics_port import AnalyticsPort
from app.infrastructure.external.amplitude.client import AmplitudeClient


class AmplitudeAnalyticsAdapter(AnalyticsPort):
    def __init__(self, *, client: AmplitudeClient, environment: str) -> None:
        self._client = client
        self._environment = environment

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
    ) -> None:
        event: dict[str, Any] = {
            "event_type": "payment_completed",
            "event_properties": {
                "character_id": character,
                "order_id": order_id,
                "amount": amount,
                "payment_method": method,
                "easy_pay_provider": easy_pay_provider,
                "card_issuer_code": card_issuer_code,
                "bank_code": bank_code,
                "paid_at": approved_at.isoformat(),
                "environment": self._environment,
                "gender": gender,
                "birth_year": birth_year,
                # DB 조인 키 — 식별자(user_id)가 아니라 이벤트 속성으로만 보존.
                "user_db_id": user_id,
            },
            "time": int(approved_at.timestamp() * 1000),
            "insert_id": f"payment_completed-{order_id}",
        }
        # 결제자 인구통계를 user_properties 로도 직접 set (gender/birth_year 조인 보강).
        user_props = {
            k: v
            for k, v in (("gender", gender), ("birth_year", birth_year))
            if v is not None
        }
        if user_props:
            event["user_properties"] = {"$set": user_props}
        # 식별 정책 (HMDA-46 후속): device_id가 있으면 user_id를 싣지 않는다.
        # DB users.id는 사주 제출마다 새로 생겨 사람 단위 고정값이 아니므로, Amplitude
        # user_id로 쓰면(user_607/user_609...) 같은 device의 FE 흐름과 별개 유저로 분리된다.
        # device_id 단독 전송 → Amplitude가 해당 device의 기존 유저로 머지(흐름 유지).
        # device_id 없는 구버전 주문만 user_{N} 폴백 (V2 API는 둘 중 하나 필수).
        if device_id:
            event["device_id"] = device_id
        else:
            event["user_id"] = f"user_{user_id}"
        if session_id is not None:
            event["session_id"] = session_id

        await self._client.send_event(event)

    async def track_payment_amount_mismatch(
        self,
        *,
        user_id: int,
        order_id: str,
        character: str,
        intended_amount: int,
        received_amount: int,
    ) -> None:
        event: dict[str, Any] = {
            "event_type": "payment_amount_mismatch",
            "user_id": f"user_{user_id}",  # V2 API는 user_id/device_id 중 하나 필수
            "event_properties": {
                "character_id": character,
                "order_id": order_id,
                "intended_amount": intended_amount,
                "received_amount": received_amount,
                "environment": self._environment,
            },
            # 시각 정보 없음 → insert_id 만 멱등키로. (Amplitude가 time 자동 부여)
            "insert_id": f"payment_amount_mismatch-{order_id}-{received_amount}",
        }
        await self._client.send_event(event)
