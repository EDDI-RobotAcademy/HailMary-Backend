from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.domains.auth.adapter.inbound.api.auth_router import (
    get_current_account_id,
    get_optional_account_id,
)
from app.domains.chat.adapter.inbound.api.sse import format_sse
from app.domains.chat.application.request.room_requests import (
    OpenRoomRequest,
    SendRoomMessageRequest,
)
from app.domains.chat.application.request.saju_profile_request import (
    SaveSajuProfileRequest,
)
from app.domains.chat.application.request.send_chat_message_request import (
    SendChatMessageRequest,
)
from app.domains.chat.application.response.room_responses import (
    ChatRoomsResponse,
    MessagesPageResponse,
    OpenRoomResponse,
)
from app.domains.chat.application.response.saju_profile_response import (
    SajuProfileResponse,
)
from app.domains.chat.application.usecase.room_usecases import (
    ListChatMessagesUseCase,
    ListChatRoomsUseCase,
    OpenChatRoomUseCase,
)
from app.domains.chat.application.usecase.saju_profile_usecase import (
    GetSajuProfileUseCase,
    SaveSajuProfileUseCase,
)
from app.domains.chat.application.usecase.stream_chat_usecase import StreamChatUseCase
from app.domains.chat.application.usecase.stream_room_chat_usecase import (
    StreamRoomChatUseCase,
)
from app.domains.chat.domain.port.conversation_repository_port import (
    ConversationNotFoundError,
)

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


def get_list_chat_rooms_usecase() -> ListChatRoomsUseCase:
    raise NotImplementedError


def get_open_chat_room_usecase() -> OpenChatRoomUseCase:
    raise NotImplementedError


def get_list_chat_messages_usecase() -> ListChatMessagesUseCase:
    raise NotImplementedError


def get_stream_room_chat_usecase() -> StreamRoomChatUseCase:
    raise NotImplementedError


def get_saju_profile_usecase() -> GetSajuProfileUseCase:
    raise NotImplementedError


def get_save_saju_profile_usecase() -> SaveSajuProfileUseCase:
    raise NotImplementedError


@router.get("/profile", response_model=SajuProfileResponse)
async def get_saju_profile(
    account_id: int = Depends(get_current_account_id),
    usecase: GetSajuProfileUseCase = Depends(get_saju_profile_usecase),
) -> SajuProfileResponse:
    """내 사주 요약 (일간·오행). 미보유 시 has_profile=false → FE가 확인 모달 출현."""
    return await usecase.execute(account_id)


@router.post("/profile", response_model=SajuProfileResponse)
async def save_saju_profile(
    body: SaveSajuProfileRequest,
    account_id: int = Depends(get_current_account_id),
    usecase: SaveSajuProfileUseCase = Depends(get_save_saju_profile_usecase),
) -> SajuProfileResponse:
    """생년월일시 확정 → 사주 계산(캐시/FortuneTeller) → 저장 → 요약 반환."""
    return await usecase.execute(account_id, body)


@router.get("/rooms", response_model=ChatRoomsResponse)
async def list_rooms(
    account_id: int = Depends(get_current_account_id),
    usecase: ListChatRoomsUseCase = Depends(get_list_chat_rooms_usecase),
) -> ChatRoomsResponse:
    """내 대화방 목록 (최근 대화순, 마지막 메시지 미리보기)."""
    return await usecase.execute(account_id)


@router.post("/rooms", response_model=OpenRoomResponse)
async def open_room(
    body: OpenRoomRequest,
    account_id: int = Depends(get_current_account_id),
    usecase: OpenChatRoomUseCase = Depends(get_open_chat_room_usecase),
) -> OpenRoomResponse:
    """캐릭터별 방 get-or-create — 신규 생성 시 페르소나 인사 시드(LLM 0) + 최근 메시지 반환."""
    return await usecase.execute(account_id, body)


@router.get("/rooms/{room_id}/messages", response_model=MessagesPageResponse)
async def list_messages(
    room_id: int,
    before_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    account_id: int = Depends(get_current_account_id),
    usecase: ListChatMessagesUseCase = Depends(get_list_chat_messages_usecase),
) -> MessagesPageResponse:
    """과거 방향 페이지네이션 — 다음 페이지는 before_id=응답 첫 메시지 id."""
    try:
        return await usecase.execute(account_id, room_id, before_id, limit)
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/rooms/{room_id}/messages")
async def send_room_message(
    room_id: int,
    body: SendRoomMessageRequest,
    account_id: int = Depends(get_current_account_id),
    usecase: StreamRoomChatUseCase = Depends(get_stream_room_chat_usecase),
) -> StreamingResponse:
    """방 기준 1턴 전송 — SSE 스트리밍 + 영속화 (CHAT_SSOT.md SSE 계약).

    스트림 시작 전 오류는 일반 상태코드(404 등). Phase 4에서 402(코인 부족)가 여기 추가.
    """
    try:
        begin = await usecase.begin(room_id=room_id, account_id=account_id, request=body)
    except ConversationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    async def event_stream() -> AsyncIterator[str]:
        async for ev in usecase.stream(room_id=room_id, begin=begin, request=body):
            yield format_sse(ev.event, ev.data)

    return StreamingResponse(
        event_stream(), media_type="text/event-stream", headers=_SSE_HEADERS
    )


@router.post("/messages")
async def send_chat_message(
    body: SendChatMessageRequest,
    account_id: int | None = Depends(get_optional_account_id),
    usecase: StreamChatUseCase = Depends(get_stream_chat_usecase),
) -> StreamingResponse:
    """[deprecated·dev] 무상태 1턴 SSE — 프로토타입 로컬 데모 전용 (P1 산물).

    영속화 없음·비로그인 허용. P5(FE 병합, 로그인 UI 확보) 후 제거 예정 —
    그때까지 프로토타입 폴더의 chatApi가 이 엔드포인트를 사용.
    """

    async def event_stream() -> AsyncIterator[str]:
        async for ev in usecase.execute(body, account_id):
            yield format_sse(ev.event, ev.data)

    return StreamingResponse(
        event_stream(), media_type="text/event-stream", headers=_SSE_HEADERS
    )
