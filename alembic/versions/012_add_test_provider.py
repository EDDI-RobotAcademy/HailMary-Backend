"""add 'test' value to accounts.provider enum (카드사 심사용 테스트 계정)

카드사 심사용 단일 공유 테스트 계정은 OAuth가 아니라 /api/auth/test-login 으로
provider='test' 계정을 발급한다. accounts.provider 가 native ENUM('kakao','google')
이므로 'test' 값을 끝에 추가(MySQL은 빠른 메타변경 — 테이블 재빌드 없음).

Revision ID: 012_add_test_provider
Revises: 011_add_payment_amplitude_ids
Create Date: 2026-06-10 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "012_add_test_provider"
down_revision: str | Sequence[str] | None = "011_add_payment_amplitude_ids"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "accounts",
        "provider",
        existing_type=sa.Enum("kakao", "google", name="provider"),
        type_=sa.Enum("kakao", "google", "test", name="provider"),
        existing_nullable=False,
    )


def downgrade() -> None:
    # 'test' 계정 row가 남아있으면 실패할 수 있음 — 롤백 전 provider='test' 정리 필요.
    op.alter_column(
        "accounts",
        "provider",
        existing_type=sa.Enum("kakao", "google", "test", name="provider"),
        type_=sa.Enum("kakao", "google", name="provider"),
        existing_nullable=False,
    )
