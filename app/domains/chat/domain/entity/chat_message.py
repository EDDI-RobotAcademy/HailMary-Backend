from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.domains.chat.domain.value_object.chat_enums import ChatMode


@dataclass
class ChatMessage:
    """대화 메시지 1건. role: 'user' | 'character' (프로토타입 도메인 모델과 동일 어휘)."""

    conversation_id: int
    role: str
    msg_type: str  # 'text' | 'saju'
    mode: ChatMode
    content: str
    saju_block: dict[str, Any] | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    created_at: datetime | None = None
    id: int | None = None
