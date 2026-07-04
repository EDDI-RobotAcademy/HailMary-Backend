from pydantic import BaseModel, Field

from app.domains.chat.domain.value_object.chat_enums import ChatCharacter, ChatMode


class OpenRoomRequest(BaseModel):
    character_id: ChatCharacter


class SendRoomMessageRequest(BaseModel):
    """방 기준 전송 — 이력은 서버가 권위라 history 필드 없음 (P1 무상태 요청과의 차이)."""

    mode: ChatMode = ChatMode.CASUAL
    content: str = Field(min_length=1, max_length=2000)
