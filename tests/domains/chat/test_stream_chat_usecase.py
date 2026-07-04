"""StreamChatUseCase — fake ChatClientPort 기반 (DB/네트워크 없음).

이벤트 시퀀스 계약(CHAT_SSOT.md): start → delta* → done | (start → delta* →) error
"""

from collections.abc import AsyncIterator

from app.domains.chat.application.request.send_chat_message_request import (
    ChatHistoryItem,
    SendChatMessageRequest,
)
from app.domains.chat.application.response.chat_stream_event import ChatStreamEvent
from app.domains.chat.application.usecase.stream_chat_usecase import (
    StreamChatUseCase,
    _normalize_turns,
)
from app.domains.chat.domain.port.chat_client_port import ChatClientError
from app.domains.chat.domain.service.prompt_builder import build_system_prompt
from app.domains.chat.domain.value_object.chat_enums import ChatCharacter, ChatMode
from app.domains.chat.domain.value_object.chat_turn import ChatTurn


class FakeChatClient:
    """청크 시퀀스를 그대로 yield. fail_after=n이면 n개 방출 후 ChatClientError."""

    def __init__(self, chunks: list[str], fail_after: int | None = None) -> None:
        self._chunks = chunks
        self._fail_after = fail_after
        self.captured_system: str | None = None
        self.captured_turns: list[ChatTurn] | None = None

    async def stream_chat(
        self,
        *,
        system_prompt: str,
        turns: list[ChatTurn],
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]:
        self.captured_system = system_prompt
        self.captured_turns = turns
        for i, chunk in enumerate(self._chunks):
            if self._fail_after is not None and i >= self._fail_after:
                raise ChatClientError("boom")
            yield chunk


def _usecase(client: FakeChatClient) -> StreamChatUseCase:
    return StreamChatUseCase(
        chat_client=client, max_tokens=800, history_window=20, temperature=0.85
    )


def _request(**overrides: object) -> SendChatMessageRequest:
    base: dict[str, object] = {
        "character_id": "yeonu",
        "mode": "casual",
        "content": "요즘 잠이 안 와.",
        "history": [],
    }
    base.update(overrides)
    return SendChatMessageRequest.model_validate(base)


async def _collect(usecase: StreamChatUseCase, req: SendChatMessageRequest) -> list[ChatStreamEvent]:
    return [ev async for ev in usecase.execute(req, account_id=None)]


async def test_event_sequence_start_delta_done() -> None:
    client = FakeChatClient(["안", "녕"])
    events = await _collect(_usecase(client), _request())
    assert [e.event for e in events] == ["start", "delta", "delta", "done"]
    assert events[0].data["character_id"] == "yeonu"
    assert events[0].data["message_id"]
    assert [e.data["text"] for e in events if e.event == "delta"] == ["안", "녕"]


async def test_error_mid_stream_emits_error_event_and_stops() -> None:
    client = FakeChatClient(["첫", "둘"], fail_after=1)
    events = await _collect(_usecase(client), _request())
    assert [e.event for e in events] == ["start", "delta", "error"]
    assert events[-1].data["code"] == "UPSTREAM_ERROR"


async def test_system_prompt_contains_persona_and_language_separation() -> None:
    client = FakeChatClient(["ok"])
    await _collect(_usecase(client), _request(character_id="doyoon", mode="saju"))
    assert client.captured_system is not None
    assert "한도윤" in client.captured_system
    assert "절대 금지 표현" in client.captured_system  # 언어 분리 가드
    assert "사주 상담" in client.captured_system  # saju 모드 지시
    # 도윤 금지 = 연우 언어(한자 근거·운명론)
    assert "한자 근거" in client.captured_system


def test_normalize_drops_leading_character_greeting_and_merges() -> None:
    history = [
        ChatHistoryItem(role="character", content="왔어."),  # greet 시드 — 선두 제거
        ChatHistoryItem(role="user", content="안녕"),
        ChatHistoryItem(role="user", content="잘 지냈어?"),  # 연속 user 병합
        ChatHistoryItem(role="character", content="그럭저럭."),
    ]
    turns = _normalize_turns(history, "본론 말할게.")
    assert [t.role for t in turns] == ["user", "assistant", "user"]
    assert turns[0].content == "안녕\n잘 지냈어?"
    assert turns[-1].content == "본론 말할게."


def test_normalize_merges_user_message_into_trailing_user_turn() -> None:
    history = [ChatHistoryItem(role="user", content="있잖아")]
    turns = _normalize_turns(history, "고민 있어.")
    assert len(turns) == 1
    assert turns[0] == ChatTurn(role="user", content="있잖아\n고민 있어.")


def test_prompt_builder_mode_switch() -> None:
    casual = build_system_prompt(ChatCharacter.YEONU, ChatMode.CASUAL)
    saju = build_system_prompt(ChatCharacter.YEONU, ChatMode.SAJU)
    assert "사적 대화" in casual and "사주 상담" not in casual
    assert "사주 상담" in saju and "사적 대화" not in saju
    assert "강연우" in casual
    assert "음독" in casual  # 한자 음독 병기 공통 규칙


async def test_history_window_trims_old_turns() -> None:
    client = FakeChatClient(["ok"])
    usecase = StreamChatUseCase(
        chat_client=client, max_tokens=800, history_window=2, temperature=0.85
    )
    history = [
        {"role": "user", "content": f"m{i}"} if i % 2 == 0 else {"role": "character", "content": f"m{i}"}
        for i in range(10)
    ]
    req = _request(history=history)
    _ = [ev async for ev in usecase.execute(req, account_id=None)]
    assert client.captured_turns is not None
    # window=2 → 최근 2개(m8=user, m9=character)만. 선두 정규화 후 user로 시작해야 함.
    assert client.captured_turns[0].role == "user"
    joined = "".join(t.content for t in client.captured_turns)
    assert "m7" not in joined and "m8" in joined
