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
    def __init__(
        self,
        *,
        character: ChatCharacter,
        history: list[ChatMessage],
        saju_raw: dict[str, object] | None = None,
    ) -> None:
        self._character = character
        self._history = history
        self._saju_raw = saju_raw
        self.begin_calls: list[dict[str, object]] = []
        self.completed: list[dict[str, object]] = []

    async def begin_turn(
        self, *, conversation_id: int, account_id: int, content: str,
        mode: ChatMode, history_window: int,
    ) -> TurnBegin:
        if conversation_id == 999:
            raise ConversationNotFoundError("not found")
        self.begin_calls.append({"conversation_id": conversation_id, "content": content})
        return TurnBegin(
            character=self._character, user_message_id=10,
            history=self._history, saju_raw=self._saju_raw,
        )

    async def complete_turn(
        self, *, conversation_id: int, content: str, mode: ChatMode,
        msg_type: str = "text", saju_block: dict[str, object] | None = None,
    ) -> int:
        self.completed.append({
            "conversation_id": conversation_id, "content": content,
            "msg_type": msg_type, "saju_block": saju_block,
        })
        return 11


class FakeChatClient:
    def __init__(
        self,
        chunks: list[str],
        fail_after: int | None = None,
        saju_block: dict[str, object] | None = None,
        saju_fails: bool = False,
    ) -> None:
        self._chunks = chunks
        self._fail_after = fail_after
        self._saju_block = saju_block
        self._saju_fails = saju_fails
        self.captured_turns: list[ChatTurn] | None = None
        self.saju_calls = 0

    async def stream_chat(
        self, *, system_prompt: str, turns: list[ChatTurn],
        max_tokens: int, temperature: float,
    ) -> AsyncIterator[str]:
        self.captured_turns = turns
        for i, chunk in enumerate(self._chunks):
            if self._fail_after is not None and i >= self._fail_after:
                raise ChatClientError("boom")
            yield chunk

    async def generate_saju_block(
        self, *, system_prompt: str, turns: list[ChatTurn],
        tool: dict[str, object], tool_name: str,
        max_tokens: int, temperature: float,
    ) -> dict[str, object]:
        self.saju_calls += 1
        self.captured_turns = turns
        if self._saju_fails:
            raise ChatClientError("saju boom")
        assert self._saju_block is not None
        return self._saju_block


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
    assert store.completed == [{
        "conversation_id": 5, "content": "그래서?",
        "msg_type": "text", "saju_block": None,
    }]
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


async def test_casual_strips_info_tail_from_persisted_content() -> None:
    # 캐주얼 응답 끝 INFO tail(<<<INFO>>> 이후)은 상태창 전용 → 저장 본문에서 제외 (HM-BE-97)
    store = FakeTurnStore(character=ChatCharacter.YEONU, history=[])
    client = FakeChatClient(["딱 보면 알아. ", '\n\n<<<INFO>>>\n{"place":"촛불 밝힌 상담실"}'])
    usecase = _stream_usecase(client, store)
    req = SendRoomMessageRequest(mode=ChatMode.CASUAL, content="안녕.")

    begin = await usecase.begin(room_id=5, account_id=1, request=req)
    events = [ev async for ev in usecase.stream(room_id=5, begin=begin, request=req)]

    # delta는 tail 포함해 그대로 흘러가고(FE가 분리), 저장 content만 tail 제외
    assert [e.event for e in events] == ["start", "delta", "delta", "done"]
    saved = store.completed[0]["content"]
    assert "<<<INFO>>>" not in saved
    assert saved == "딱 보면 알아."


async def test_saju_mode_with_profile_emits_structured_block() -> None:
    block = {
        "kind": "yeonu",
        "scene": "달빛 아래 붉은 실이 보여.",
        "evidence": [{"hanja": "丙火(병화)", "element": "화(火)", "note": "정열의 기운"}],
        "advice": "먼저 다가가도 좋아.",
    }
    store = FakeTurnStore(
        character=ChatCharacter.YEONU, history=[], saju_raw={"day": {"stem": "병"}}
    )
    client = FakeChatClient([], saju_block=block)
    usecase = _stream_usecase(client, store)
    req = SendRoomMessageRequest(mode=ChatMode.SAJU, content="내 연애운 봐줘.")

    begin = await usecase.begin(room_id=5, account_id=1, request=req)
    events = [ev async for ev in usecase.stream(room_id=5, begin=begin, request=req)]

    assert [e.event for e in events] == ["start", "saju_block", "done"]
    assert client.saju_calls == 1
    assert events[1].data["block"] == block
    assert events[-1].data["stop_reason"] == "tool_use"
    # 리드 텍스트(scene) + 구조화 블록 영속화
    assert store.completed == [{
        "conversation_id": 5, "content": "달빛 아래 붉은 실이 보여.",
        "msg_type": "saju", "saju_block": block,
    }]


async def test_saju_mode_without_profile_falls_back_to_text() -> None:
    store = FakeTurnStore(character=ChatCharacter.YEONU, history=[], saju_raw=None)
    client = FakeChatClient(["생년월일", "부터 알려줘"], saju_block={"kind": "yeonu"})
    usecase = _stream_usecase(client, store)
    req = SendRoomMessageRequest(mode=ChatMode.SAJU, content="사주 봐줘.")

    begin = await usecase.begin(room_id=5, account_id=1, request=req)
    events = [ev async for ev in usecase.stream(room_id=5, begin=begin, request=req)]

    assert [e.event for e in events] == ["start", "delta", "delta", "done"]
    assert client.saju_calls == 0  # 프로필 없으면 구조화 블록 미호출
    assert store.completed[0]["msg_type"] == "text"


async def test_saju_block_error_skips_persistence() -> None:
    store = FakeTurnStore(
        character=ChatCharacter.DOYOON, history=[], saju_raw={"day": {"stem": "경"}}
    )
    client = FakeChatClient([], saju_fails=True)
    usecase = _stream_usecase(client, store)
    req = SendRoomMessageRequest(mode=ChatMode.SAJU, content="사주 분석해줘.")

    begin = await usecase.begin(room_id=5, account_id=1, request=req)
    events = [ev async for ev in usecase.stream(room_id=5, begin=begin, request=req)]

    assert [e.event for e in events] == ["start", "error"]
    assert store.completed == []
