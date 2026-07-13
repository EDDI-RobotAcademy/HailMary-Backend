from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base


class SajuProfileORM(Base):
    __tablename__ = "chat_saju_profiles"
    __table_args__ = (
        UniqueConstraint("account_id", name="uq_chat_saju_profiles_account"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("accounts.id"), nullable=False, index=True
    )
    birth_date: Mapped[str] = mapped_column(String(10), nullable=False)
    birth_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    birth_time_unknown: Mapped[bool] = mapped_column(Boolean, nullable=False)
    calendar: Mapped[str] = mapped_column(String(8), nullable=False)
    gender: Mapped[str] = mapped_column(String(8), nullable=False)
    saju_raw: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
