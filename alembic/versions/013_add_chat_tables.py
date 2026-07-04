"""도화선 2.0 캐릭터 챗 영속화 (HM-BE-88) — conversations + chat_messages

conversations: 계정×캐릭터당 방 1개 (UNIQUE). character_id는 String(16) —
신규 캐릭터 5종 예정이라 enum ALTER 회피, 값 검증은 도메인 enum.
chat_messages: 대화 이력 (saju_block JSON은 Phase 3 구조화 블록 자리).

Revision ID: 013_add_chat_tables
Revises: 012_add_test_provider
Create Date: 2026-07-04

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "013_add_chat_tables"
down_revision: str | Sequence[str] | None = "012_add_test_provider"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.String(length=16), nullable=False),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name="fk_conversations_account_id"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "character_id", name="uq_conversations_account_character"),
    )
    op.create_index("ix_conversations_account_id", "conversations", ["account_id"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("msg_type", sa.String(length=8), nullable=False),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("saju_block", sa.JSON(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], name="fk_chat_messages_conversation_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_chat_messages_conversation_id_id", "chat_messages", ["conversation_id", "id"]
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_conversation_id_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_conversations_account_id", table_name="conversations")
    op.drop_table("conversations")
