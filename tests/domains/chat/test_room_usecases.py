"""방 CRUD + 방 기준 스트리밍 유스케이스 — fake 포트 기반 (DB/네트워크 없음)."""

from collections.abc import AsyncIterator
from datetime import datetime

import pytest

from app.domains.chat.application.request.room_requests import (
    OpenRoomRequest,
    SendRoomMessageRequest,
)
from app.domains.chat.application.usecase.room_usecases import (
    ListChatMessagesUseCase,
    OpenChatRoomUseCase,
)
from app.domains.chat.application.usecase.stream_room_chat_usecase import (
    StreamRoomChatUseCase,
)
from app.domains.chat.domain.entity.chat_message import ChatMessage
from app.domains.chat.domain.entity.conversation import Conversation
from app.domains.chat.domain.port.chat_client_port import ChatClientError
from app.domains.chat.domain.port.chat_turn_store_port import TurnBegin
from app.domains.chat.domain.port.conversation_repository_port import (
    ConversationNotFoundError,
    RoomSummary,
)
from app.domains.chat.domain.value_object.chat_enums import ChatCharacter, ChatMode
from app.domains.chat.domain.value_object.chat_turn import ChatTurn


class FakeConversationRepo:
    """인메모리 fake — ConversationRepositoryPort 구조 구현."""

    def __init__(self) -> None:
        self.conversations: dict[int, Conversation] = {}
        self.messages: dict[int, list[ChatMessage]] = {}
        self._next_id = 1

    async def list_rooms(self, *, account_id: int) -> list[RoomSummary]:
        out: list[RoomSummary] = []
        for conv in self.conversations.values():
            if conv.account_id != account_id:
                continue
            msgs = self.messages.get(conv.id or 0, [])
            out.append(
                RoomSummary(
                    conversation_id=conv.id or 0,
                    character=conv.character,
                    last_message=msgs[-1].content if msgs else "",
                    last_message_at=conv.last_message_at,
                )
            )
        return out

    async def get_or_create(
        self, *, account_id: int, character: ChatCharacter, greeting: str
    ) -> tuple[Conversation, bool]:
        for conv in self.conversations.values():
            if conv.account_id == account_id and conv.character == character:
                return conv, False
        conv = Conversation(
            id=self._next_id, account_id=account_id, character=character,
            created_at=datetime(2026, 7, 4),
        )
        self.conversations[self._next_id] = conv
        self.messages[self._next_id] = [
            ChatMessage(
                id=1, conversation_id=self._next_id, role="character",
                msg_type="text", mode=ChatMode.CASUAL, content=greeting,
            )
        ]
        self._next_id += 1
        return conv, True

    async def get_owned(self, *, conversation_id: int, account_id: int) -> Conversation:
        conv = self.conversations.get(conversation_id)
        if conv is None or conv.account_id != account_id:
            raise ConversationNotFoundError("not found")
        return conv

    async def list_messages(
        self, *, conversation_id: int, before_id: int | None, limit: int
    ) -> list[ChatMessage]:
        msgs = self.messages.get(conversation_id, [])
        if before_id is not None:
            msgs = [m for m in msgs if (m.id or 0) < before_id]
        return msgs[-limit:]


class FakeTurnStore:
    def __init__(self, *, character: ChatCharacter, history: list[ChatMessage]) -> None:
        self._character = character
        self._history = history
        self.begin_calls: list[dict[str, object]] = []
        self.completed: list[dict[str, object]] = []

    async def begin_turn(
        self, *, conversation_id: int, account_id: int, content: str,
        mode: ChatMode, history_window: int,
    ) -> TurnBegin:
        if conversation_id == 999:
            raise ConversationNotFoundError("not found")
        self.begin_calls.append({"conversation_id": conversation_id, "content": content})
        return TurnBegin(character=self._character, user_message_id=10, history=self._history)

    async def complete_turn(
        self, *, conversation_id: int, content: str, mode: ChatMode
    ) -> int:
        self.completed.append({"conversation_id": conversation_id, "content": content})
        return 11


class FakeChatClient:
    def __init__(self, chunks: list[str], fail_after: int | None = None) -> None:
        self._chunks = chunks
        self._fail_after = fail_after
        self.captured_turns: list[ChatTurn] | None = None

    async def stream_chat(
        self, *, system_prompt: str, turns: list[ChatTurn],
        max_tokens: int, temperature: float,
    ) -> AsyncIterator[str]:
        self.captured_turns = turns
        for i, chunk in enumerate(self._chunks):
            if self._fail_after is not None and i >= self._fail_after:
                raise ChatClientError("boom")
            yield chunk


def _stream_usecase(client: FakeChatClient, store: FakeTurnStore) -> StreamRoomChatUseCase:
    return StreamRoomChatUseCase(
        chat_client=client, turn_store=store,
        max_tokens=800, history_window=20, temperature=0.85,
    )


async def test_open_room_seeds_greeting_once() -> None:
    repo = FakeConversationRepo()
    usecase = OpenChatRoomUseCase(conversation_repo=repo)
    first = await usecase.execute(1, OpenRoomRequest(character_id=ChatCharacter.YEONU))
    assert first.created is True
    assert first.messages[0].role == "character"
    assert first.messages[0].content  # 페르소나 greeting 시드
    second = await usecase.execute(1, OpenRoomRequest(character_id=ChatCharacter.YEONU))
    assert second.created is False
    assert second.room_id == first.room_id


async def test_list_messages_rejects_foreign_room() -> None:
    repo = FakeConversationRepo()
    await OpenChatRoomUseCase(conversation_repo=repo).execute(
        1, OpenRoomRequest(character_id=ChatCharacter.KKEBI)
    )
    usecase = ListChatMessagesUseCase(conversation_repo=repo)
    with pytest.raises(ConversationNotFoundError):
        await usecase.execute(2, 1, None, 50)  # 남의 계정(2)이 방 1 조회


async def test_stream_room_persists_character_message_on_done() -> None:
    history = [
        ChatMessage(id=1, conversation_id=5, role="character", msg_type="text",
                    mode=ChatMode.CASUAL, content="왔어."),
        ChatMessage(id=2, conversation_id=5, role="user", msg_type="text",
                    mode=ChatMode.CASUAL, content="안녕"),
    ]
    store = FakeTurnStore(character=ChatCharacter.YEONU, history=history)
    client = FakeChatClient(["그래", "서?"])
    usecase = _stream_usecase(client, store)
    req = SendRoomMessageRequest(mode=ChatMode.CASUAL, content="고민 있어.")

    begin = await usecase.begin(room_id=5, account_id=1, request=req)
    events = [ev async for ev in usecase.stream(room_id=5, begin=begin, request=req)]

    assert [e.event for e in events] == ["start", "delta", "delta", "done"]
    assert events[0].data["user_message_id"] == 10
    assert events[-1].data["message_id"] == 11
    assert store.completed == [{"conversation_id": 5, "content": "그래서?"}]
    # 이력 정규화: 선두 character(greet) 제거 → user 시작
    assert client.captured_turns is not None
    assert client.captured_turns[0].role == "user"


async def test_stream_room_error_skips_persistence() -> None:
    store = FakeTurnStore(character=ChatCharacter.DOYOON, history=[])
    client = FakeChatClient(["일", "부"], fail_after=1)
    usecase = _stream_usecase(client, store)
    req = SendRoomMessageRequest(mode=ChatMode.SAJU, content="이직 고민이에요.")

    begin = await usecase.begin(room_id=5, account_id=1, request=req)
    events = [ev async for ev in usecase.stream(room_id=5, begin=begin, request=req)]

    assert [e.event for e in events] == ["start", "delta", "error"]
    assert store.completed == []  # 실패 시 캐릭터 메시지 저장 없음 (TBD-D)


async def test_begin_raises_for_missing_room() -> None:
    store = FakeTurnStore(character=ChatCharacter.YEONU, history=[])
    usecase = _stream_usecase(FakeChatClient(["x"]), store)
    with pytest.raises(ConversationNotFoundError):
        await usecase.begin(
            room_id=999, account_id=1,
            request=SendRoomMessageRequest(mode=ChatMode.CASUAL, content="hi"),
        )
