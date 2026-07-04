from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domains.chat.domain.entity.chat_message import ChatMessage
from app.domains.chat.domain.entity.conversation import Conversation
from app.domains.chat.domain.value_object.chat_enums import ChatCharacter


class ConversationNotFoundError(Exception):
    """방이 없거나 소유자가 아님 — 라우터에서 404로 변환."""


@dataclass(frozen=True)
class RoomSummary:
    """대화방 리스트 행 (마지막 메시지 미리보기 포함)."""

    conversation_id: int
    character: ChatCharacter
    last_message: str
    last_message_at: datetime | None


class ConversationRepositoryPort(Protocol):
    """대화방/메시지 조회·생성 — 요청 세션 기반 (main.py `_get_session`)."""

    async def list_rooms(self, *, account_id: int) -> list[RoomSummary]: ...

    async def get_or_create(
        self, *, account_id: int, character: ChatCharacter, greeting: str
    ) -> tuple[Conversation, bool]:
        """방 get-or-create. 신규 생성 시 greeting을 character 메시지로 시드(LLM 0).

        returns (conversation, created)
        """
        ...

    async def get_owned(
        self, *, conversation_id: int, account_id: int
    ) -> Conversation:
        """소유 검증 포함 조회 — 없거나 남의 방이면 ConversationNotFoundError."""
        ...

    async def list_messages(
        self, *, conversation_id: int, before_id: int | None, limit: int
    ) -> list[ChatMessage]:
        """과거 방향 페이지네이션 (id < before_id, 최신순 limit개 → 오름차순 반환)."""
        ...
