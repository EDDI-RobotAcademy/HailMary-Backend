from dataclasses import dataclass
from datetime import datetime

from app.domains.chat.domain.value_object.chat_enums import ChatCharacter


@dataclass
class Conversation:
    """대화방 — 계정×캐릭터당 1개 (UNIQUE). 친구목록 모델."""

    account_id: int
    character: ChatCharacter
    last_message_at: datetime | None = None
    created_at: datetime | None = None
    id: int | None = None
