from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.domains.payment.domain.value_object.payment_status import (
    CharacterCode,
    PaymentMethod,
    PaymentStatus,
)
from app.infrastructure.database.session import Base


class PaymentORM(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    payment_key: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    order_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    # 소셜 로그인 계정 귀속 (HM-BE-77). NULL = 비로그인 결제.
    # 로그인 시 인증 이메일 매칭 backfill로 채워지거나, 로그인 상태 결제 시 즉시 연결.
    account_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("accounts.id"), nullable=True, index=True
    )
    character: Mapped[CharacterCode] = mapped_column(
        Enum(CharacterCode, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    customer_email: Mapped[str] = mapped_column(String(254), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    method: Mapped[PaymentMethod | None] = mapped_column(
        Enum(PaymentMethod, values_callable=lambda e: [x.value for x in e]),
        nullable=True,
    )
    easy_pay_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # ⚠️ method/card_issuer_code/bank_code: Toss 시절 컬럼. 현재 PayApp 플로에선 *미저장*(항상 NULL).
    #   PayApp webhook의 card_name(카드사명)/vbank(은행명)은 Amplitude 이벤트로만 전송됨
    #   (handle_payapp_feedback_usecase). 즉 이 varchar(8) 칸엔 값이 들어오지 않아 길이/1406 위험 없음.
    #   → 컬럼 확장 불필요. 추후 실제 DB 저장을 배선할 때 비로소 길이(한글 이름 8자 초과) 재검토.
    card_issuer_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    bank_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # 2026-06-05 결과지 메일 확정 후 발송 설계:
    # email_confirmed_at — FE 이메일 확인 모달 확정 시각 (확정 즉시 발송 트리거)
    # result_email_sent_at — 결과지 링크 메일 발송 시각 (NULL=미발송, 스위퍼가 폴백 발송)
    email_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    result_email_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Amplitude 식별자 (결제 요청 시점 FE 값). webhook payment_completed 발화 시 사용.
    # session_id는 epoch ms — int32 초과하므로 BigInteger. NULL=미전달(구버전 FE/직접 호출).
    device_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
