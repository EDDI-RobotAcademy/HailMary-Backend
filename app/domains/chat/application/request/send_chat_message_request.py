from typing import Literal

from pydantic import BaseModel, Field

from app.domains.chat.domain.value_object.chat_enums import ChatCharacter, ChatMode


class ChatHistoryItem(BaseModel):
    """클라이언트가 보내는 직전 대화 이력 1턴 (Phase 1 무상태 한정).

    role은 프로토타입 도메인 모델(user|character) 그대로 —
    Anthropic 규격(assistant) 매핑은 usecase에서 한다.
    Phase 2(영속화)부터 서버 저장 이력이 권위가 되고 이 필드는 무시된다.
    """

    role: Literal["user", "character"]
    content: str = Field(min_length=1, max_length=4000)


class SendChatMessageRequest(BaseModel):
    character_id: ChatCharacter
    mode: ChatMode = ChatMode.CASUAL
    content: str = Field(min_length=1, max_length=2000)
    history: list[ChatHistoryItem] = Field(default_factory=list, max_length=100)
