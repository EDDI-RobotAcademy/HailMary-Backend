from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.domains.chat.domain.entity.chat_message import ChatMessage


class ChatMessageResponse(BaseModel):
    id: int
    role: str  # user | character
    type: str  # text | saju
    mode: str  # casual | saju
    content: str
    saju_block: dict[str, Any] | None = None
    created_at: datetime | None = None

    @staticmethod
    def from_entity(m: ChatMessage) -> "ChatMessageResponse":
        return ChatMessageResponse(
            id=m.id or 0,
            role=m.role,
            type=m.msg_type,
            mode=m.mode.value,
            content=m.content,
            saju_block=m.saju_block,
            created_at=m.created_at,
        )


class RoomSummaryResponse(BaseModel):
    room_id: int
    character_id: str
    last_message: str
    last_message_at: datetime | None = None


class ChatRoomsResponse(BaseModel):
    rooms: list[RoomSummaryResponse]


class OpenRoomResponse(BaseModel):
    room_id: int
    character_id: str
    created: bool
    messages: list[ChatMessageResponse]


class MessagesPageResponse(BaseModel):
    messages: list[ChatMessageResponse]  # 오름차순. 추가 페이지는 before_id=첫 메시지 id로 재요청
