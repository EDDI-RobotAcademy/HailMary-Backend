"""대화방 CRUD 유스케이스 3종 — 요청 세션 기반 repository 경유.

스트리밍 턴은 별도 (stream_room_chat_usecase.py — 자체 세션 turn store).
"""

from app.domains.chat.application.request.room_requests import OpenRoomRequest
from app.domains.chat.application.response.room_responses import (
    ChatMessageResponse,
    ChatRoomsResponse,
    MessagesPageResponse,
    OpenRoomResponse,
    RoomSummaryResponse,
)
from app.domains.chat.domain.port.conversation_repository_port import (
    ConversationRepositoryPort,
)
from app.domains.chat.domain.service.persona import PERSONAS

_OPEN_ROOM_MESSAGES = 50


class ListChatRoomsUseCase:
    def __init__(self, *, conversation_repo: ConversationRepositoryPort) -> None:
        self._repo = conversation_repo

    async def execute(self, account_id: int) -> ChatRoomsResponse:
        rooms = await self._repo.list_rooms(account_id=account_id)
        return ChatRoomsResponse(
            rooms=[
                RoomSummaryResponse(
                    room_id=r.conversation_id,
                    character_id=r.character.value,
                    last_message=r.last_message,
                    last_message_at=r.last_message_at,
                )
                for r in rooms
            ]
        )


class OpenChatRoomUseCase:
    """캐릭터별 방 get-or-create. 신규 생성 시 페르소나 greeting 시드(LLM 0)."""

    def __init__(self, *, conversation_repo: ConversationRepositoryPort) -> None:
        self._repo = conversation_repo

    async def execute(self, account_id: int, request: OpenRoomRequest) -> OpenRoomResponse:
        greeting = PERSONAS[request.character_id].greeting
        conv, created = await self._repo.get_or_create(
            account_id=account_id, character=request.character_id, greeting=greeting
        )
        messages = await self._repo.list_messages(
            conversation_id=conv.id or 0, before_id=None, limit=_OPEN_ROOM_MESSAGES
        )
        return OpenRoomResponse(
            room_id=conv.id or 0,
            character_id=conv.character.value,
            created=created,
            messages=[ChatMessageResponse.from_entity(m) for m in messages],
        )


class ListChatMessagesUseCase:
    def __init__(self, *, conversation_repo: ConversationRepositoryPort) -> None:
        self._repo = conversation_repo

    async def execute(
        self, account_id: int, conversation_id: int, before_id: int | None, limit: int
    ) -> MessagesPageResponse:
        # 소유 검증 (아니면 ConversationNotFoundError → 라우터 404)
        await self._repo.get_owned(conversation_id=conversation_id, account_id=account_id)
        messages = await self._repo.list_messages(
            conversation_id=conversation_id, before_id=before_id, limit=limit
        )
        return MessagesPageResponse(
            messages=[ChatMessageResponse.from_entity(m) for m in messages]
        )
