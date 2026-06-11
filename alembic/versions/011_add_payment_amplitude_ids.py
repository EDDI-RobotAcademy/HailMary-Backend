"""add amplitude device_id/session_id to payments

payment_completed(BE webhook 발화)가 FE 유저와 식별 분리되던 문제의 해결:
결제 요청 시점의 Amplitude device_id/session_id를 Payment에 보관했다가
webhook 발화에 그대로 싣는다. 기존 row는 NULL(소급 불가 — 구버전 FE 주문).

Revision ID: 011_add_payment_amplitude_ids
Revises: 010_add_kkebi_results
Create Date: 2026-06-11 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "011_add_payment_amplitude_ids"
down_revision: str | Sequence[str] | None = "010_add_kkebi_results"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("device_id", sa.String(length=64), nullable=True),
    )
    # Amplitude session_id는 epoch ms — int32 초과하므로 BigInteger.
    op.add_column(
        "payments",
        sa.Column("session_id", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("payments", "session_id")
    op.drop_column("payments", "device_id")
