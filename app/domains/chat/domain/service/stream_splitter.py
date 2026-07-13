"""스트림 텍스트에서 속마음(💭:) 분리 — 순수 도메인 서비스.

계약 (prompt_builder.INNER_THOUGHT_MARKER와 동기):
  모델은 응답 마지막 줄에 '💭:속마음' 을 붙인다.
  마커 이전 = 발화(delta로 방출), 마커 이후 = 속마음(스트림 종료 후 1회 방출).
  마커가 없으면 속마음 없이 종료 — 우아한 실패 (inner_thought 이벤트 생략).

마커가 청크 경계에서 쪼개질 수 있으므로("💭" / ":"), 마커의 접두사로 끝나는
꼬리는 방출을 보류(carry)한다.
"""

from collections.abc import AsyncIterator

from app.domains.chat.domain.service.prompt_builder import INNER_THOUGHT_MARKER


def _held_suffix_len(text: str) -> int:
    """text 끝이 ("\\n"+마커) 또는 마커의 진접두사와 일치하면 보류할 길이.

    개행("\\n")도 보류 대상 — 마커는 보통 "\\n💭:" 형태로 도착하므로,
    개행만 먼저 온 청크를 방출해버리면 발화 끝에 개행이 남는다.
    """
    lead = "\n" + INNER_THOUGHT_MARKER
    for k in range(len(lead) - 1, 0, -1):
        if text.endswith(lead[:k]):
            return k
    for k in range(len(INNER_THOUGHT_MARKER) - 1, 0, -1):
        if text.endswith(INNER_THOUGHT_MARKER[:k]):
            return k
    return 0


async def split_inner_thought(
    chunks: AsyncIterator[str],
) -> AsyncIterator[tuple[str, str]]:
    """("delta", 발화조각)* 을 방출하고, 마커 발견 시 마지막에 ("inner_thought", 속마음) 1회.

    업스트림 예외(ChatClientError 등)는 그대로 전파 — 호출측(usecase)이 처리.
    """
    carry = ""
    thought_buf: str | None = None  # None = 아직 마커 미발견

    async for chunk in chunks:
        if thought_buf is not None:
            thought_buf += chunk
            continue
        carry += chunk
        idx = carry.find(INNER_THOUGHT_MARKER)
        if idx != -1:
            speech = carry[:idx].rstrip("\n ")
            if speech:
                yield ("delta", speech)
            thought_buf = carry[idx + len(INNER_THOUGHT_MARKER) :]
            carry = ""
            continue
        hold = _held_suffix_len(carry)
        emit = carry[: len(carry) - hold] if hold else carry
        carry = carry[len(carry) - hold :] if hold else ""
        if emit:
            yield ("delta", emit)

    if thought_buf is not None:
        thought = thought_buf.strip().strip("'\"")
        if thought:
            yield ("inner_thought", thought)
    elif carry:
        yield ("delta", carry)
