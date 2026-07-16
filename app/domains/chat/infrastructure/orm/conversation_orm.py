from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base


class ConversationORM(Base):
    __tablename__ = "conversations"
    # 계정×캐릭터당 방 1개 (친구목록 모델, CHAT_SSOT.md DB 스키마)
    __table_args__ = (
        UniqueConstraint("account_id", "character_id", name="uq_conversations_account_character"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("accounts.id"), nullable=False, index=True
    )
    # sa.Enum 대신 String — 신규 캐릭터 5종 예정이라 enum ALTER 마이그레이션 회피.
    # 값 검증은 도메인 ChatCharacter enum이 담당.
    character_id: Mapped[str] = mapped_column(String(16), nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, server_default=func.now()
    )
