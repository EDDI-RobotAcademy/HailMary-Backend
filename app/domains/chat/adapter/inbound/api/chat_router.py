from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.domains.auth.adapter.inbound.api.auth_router import get_optional_account_id
from app.domains.chat.adapter.inbound.api.sse import format_sse
from app.domains.chat.application.request.send_chat_message_request import (
    SendChatMessageRequest,
)
from app.domains.chat.application.usecase.stream_chat_usecase import StreamChatUseCase

router = APIRouter(prefix="/api/chat", tags=["chat"])

# nginx/프록시 버퍼링 무력화 — 스트리밍이 통짜로 도착하면 이 헤더/EC2 nginx 설정부터 의심
# (CHAT_SSOT.md 리스크 표 참조).
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}


# main.py에서 app.dependency_overrides로 교체된다.
def get_stream_chat_usecase() -> StreamChatUseCase:
    raise NotImplementedError


@router.post("/messages")
async def send_chat_message(
    body: SendChatMessageRequest,
    account_id: int | None = Depends(get_optional_account_id),
    usecase: StreamChatUseCase = Depends(get_stream_chat_usecase),
) -> StreamingResponse:
    """캐릭터 챗 1턴 — SSE 스트리밍 (Phase 1 무상태 임시 엔드포인트).

    Phase 2에서 POST /api/chat/rooms/{id}/messages 로 이전 + 로그인 필수(get_current_account_id)
    전환 예정. Phase 1은 localhost 데모 편의로 비로그인 허용.
    """

    async def event_stream() -> AsyncIterator[str]:
        async for ev in usecase.execute(body, account_id):
            yield format_sse(ev.event, ev.data)

    return StreamingResponse(
        event_stream(), media_type="text/event-stream", headers=_SSE_HEADERS
    )
