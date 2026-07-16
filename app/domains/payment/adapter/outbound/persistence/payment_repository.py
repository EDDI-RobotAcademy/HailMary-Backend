from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.payment.domain.entity.payment import Payment
from app.domains.payment.domain.port.payment_repository_port import (
    DuplicatePaymentError,
    PaymentRepositoryPort,
)
from app.domains.payment.domain.value_object.payment_status import PaymentStatus
from app.domains.payment.infrastructure.mapper.payment_mapper import PaymentMapper
from app.domains.payment.infrastructure.orm.payment_orm import PaymentORM


class PaymentRepository(PaymentRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, payment: Payment) -> Payment:
        orm = PaymentMapper.to_orm(payment)
        # SAVEPOINT로 감싼다 — order_id UNIQUE 충돌(FE 결제완료 호출 + 포트원 웹훅 동시
        # 발급 레이스) 시 nested만 롤백되고 바깥 요청 트랜잭션은 살아남아
        # UseCase가 idempotent(이미 발급됨) 처리할 수 있다. (account_repository 패턴 동일)
        try:
            async with self._session.begin_nested():
                self._session.add(orm)
                await self._session.flush()
        except IntegrityError as e:
            # order_id UNIQUE 충돌(FE 결제완료 + 웹훅 동시 발급)만 도메인 예외로 번역.
            # 그 외 무결성 위반(FK/NOT NULL 등)은 원본 그대로 전파 — 거짓 PAID 방지.
            if "ix_payments_order_id" in str(e):
                raise DuplicatePaymentError(
                    f"이미 존재하는 결제 (order_id={payment.order_id})"
                ) from e
            raise
        return PaymentMapper.to_entity(orm)

    async def find_by_order_id(self, order_id: str) -> Payment | None:
        result = await self._session.execute(
            select(PaymentORM).where(PaymentORM.order_id == order_id),
        )
        orm = result.scalar_one_or_none()
        return PaymentMapper.to_entity(orm) if orm else None

    async def find_by_payment_key(self, payment_key: str) -> Payment | None:
        result = await self._session.execute(
            select(PaymentORM).where(PaymentORM.payment_key == payment_key),
        )
        orm = result.scalar_one_or_none()
        return PaymentMapper.to_entity(orm) if orm else None

    async def update_status(
        self,
        *,
        order_id: str,
        status: PaymentStatus,
        approved_at: datetime | None = None,
    ) -> Payment | None:
        result = await self._session.execute(
            select(PaymentORM).where(PaymentORM.order_id == order_id),
        )
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        orm.status = status
        if approved_at is not None:
            orm.approved_at = approved_at
        await self._session.flush()
        return PaymentMapper.to_entity(orm)

    async def update_customer_email(
        self,
        *,
        order_id: str,
        new_email: str,
    ) -> Payment | None:
        result = await self._session.execute(
            select(PaymentORM).where(PaymentORM.order_id == order_id),
        )
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        orm.customer_email = new_email
        await self._session.flush()
        return PaymentMapper.to_entity(orm)

    async def confirm_email(
        self,
        *,
        order_id: str,
        email: str,
    ) -> tuple[Payment, bool] | None:
        result = await self._session.execute(
            select(PaymentORM).where(PaymentORM.order_id == order_id),
        )
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        changed = orm.customer_email != email
        if changed:
            orm.customer_email = email
        orm.email_confirmed_at = datetime.now(UTC)
        await self._session.flush()
        return PaymentMapper.to_entity(orm), changed

    async def mark_result_email_sent(self, *, order_id: str) -> None:
        result = await self._session.execute(
            select(PaymentORM).where(PaymentORM.order_id == order_id),
        )
        orm = result.scalar_one_or_none()
        if orm is None:
            return
        orm.result_email_sent_at = datetime.now(UTC)
        await self._session.flush()

    async def find_email_unsent_done(
        self,
        *,
        unconfirmed_grace_seconds: int,
        limit: int = 20,
    ) -> list[Payment]:
        cutoff = datetime.now(UTC) - timedelta(seconds=unconfirmed_grace_seconds)
        result = await self._session.execute(
            select(PaymentORM)
            .where(
                PaymentORM.status == PaymentStatus.DONE,
                PaymentORM.result_email_sent_at.is_(None),
                or_(
                    PaymentORM.email_confirmed_at.is_not(None),
                    PaymentORM.approved_at < cutoff,
                ),
            )
            .order_by(PaymentORM.approved_at)
            .limit(limit),
        )
        return [PaymentMapper.to_entity(o) for o in result.scalars().all()]
