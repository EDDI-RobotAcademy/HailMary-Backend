"""채팅 사주 프로필 (HM-BE-89) — chat_saju_profiles

계정당 1건. 생년월일시 입력 + FortuneTeller 결과(JSON). chat 도메인 소유.
1.0 saju_results(user_id 기준)와 별개 — 재사용은 컷오버(P9)로 미룸.

Revision ID: 014_add_chat_saju_profiles
Revises: 013_add_chat_tables
Create Date: 2026-07-06

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "014_add_chat_saju_profiles"
down_revision: str | Sequence[str] | None = "013_add_chat_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_saju_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("birth_date", sa.String(length=10), nullable=False),  # YYYY-MM-DD
        sa.Column("birth_time", sa.String(length=5), nullable=True),    # HH:MM
        sa.Column("birth_time_unknown", sa.Boolean(), nullable=False),
        sa.Column("calendar", sa.String(length=8), nullable=False),     # solar|lunar
        sa.Column("gender", sa.String(length=8), nullable=False),       # male|female
        sa.Column("saju_raw", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name="fk_chat_saju_profiles_account_id"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", name="uq_chat_saju_profiles_account"),
    )


def downgrade() -> None:
    op.drop_table("chat_saju_profiles")
