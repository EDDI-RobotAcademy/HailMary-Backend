"""속마음(💭:) 스트림 분리 — 마커 유/무/청크 경계 쪼개짐 케이스."""

from collections.abc import AsyncIterator

from app.domains.chat.domain.service.stream_splitter import split_inner_thought


async def _chunks(*parts: str) -> AsyncIterator[str]:
    for p in parts:
        yield p


async def _collect(*parts: str) -> list[tuple[str, str]]:
    return [item async for item in split_inner_thought(_chunks(*parts))]


async def test_no_marker_passes_all_as_delta() -> None:
    out = await _collect("안녕", "하세요")
    assert out == [("delta", "안녕"), ("delta", "하세요")]


async def test_marker_splits_speech_and_thought() -> None:
    out = await _collect("용건만 말해.\n💭:안색이 왜 이래.")
    assert out == [
        ("delta", "용건만 말해."),
        ("inner_thought", "안색이 왜 이래."),
    ]


async def test_marker_split_across_chunks() -> None:
    # "💭"와 ":"가 다른 청크로 쪼개져 도착
    out = await _collect("그래서?", "\n💭", ":", "신경 쓰이게.")
    deltas = [t for k, t in out if k == "delta"]
    thoughts = [t for k, t in out if k == "inner_thought"]
    assert "".join(deltas) == "그래서?"
    assert thoughts == ["신경 쓰이게."]


async def test_thought_spans_multiple_chunks_and_quotes_stripped() -> None:
    out = await _collect("됐고.\n💭:'이 녀석 ", "또 혼자 끙끙대네.'")
    assert out[-1] == ("inner_thought", "이 녀석 또 혼자 끙끙대네.")


async def test_marker_only_no_speech() -> None:
    out = await _collect("💭:할 말 없음.")
    assert out == [("inner_thought", "할 말 없음.")]


async def test_trailing_partial_marker_flushed_when_stream_ends() -> None:
    # 마지막 청크가 "💭"로 끝나고 스트림 종료 — 보류분을 delta로 플러시
    out = await _collect("끝문장💭")
    assert out == [("delta", "끝문장"), ("delta", "💭")]
