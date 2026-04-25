from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base


class SurveyORM(Base):
    __tablename__ = "surveys"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    survey_version: Mapped[str] = mapped_column(String(16), nullable=False)
    step1_slugs: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    step2_slugs: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    step3_text: Mapped[str | None] = mapped_column(Text, nullable=True)
