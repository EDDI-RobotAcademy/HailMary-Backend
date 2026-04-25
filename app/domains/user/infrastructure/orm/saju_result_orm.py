from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base


class SajuResultORM(Base):
    __tablename__ = "saju_results"
    __table_args__ = (UniqueConstraint("user_id", name="uq_saju_results_user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    fortuneteller_request: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    fortuneteller_response: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
