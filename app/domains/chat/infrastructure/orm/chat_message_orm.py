from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.session import Base


class ChatMessageORM(Base):
    __tablename__ = "chat_messages"
    # 히스토리 윈도 조회용 복합 인덱스 (conversation_id, id)
    __table_args__ = (Index("ix_chat_messages_conversation_id_id", "conversation_id", "id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversations.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user | character
    msg_type: Mapped[str] = mapped_column(String(8), nullable=False)  # text | saju
    mode: Mapped[str] = mapped_column(String(8), nullable=False)  # casual | saju
    content: Mapped[str] = mapped_column(Text, nullable=False)
    saju_block: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, server_default=func.now()
    )
