"""포트원(PortOne) V2 결제 라우터 — 카카오페이 결제창 완료 검증 + 웹훅.

main.py에서 portone_enabled=True 일 때만 include_router 됨(미설정 시 엔드포인트 404).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse

from app.domains.auth.adapter.inbound.api.auth_router import get_optional_account_id
from app.domains.payment.application.request.portone_complete_request import (
    PortOneCompleteRequest,
)
from app.domains.payment.application.usecase.complete_portone_payment_usecase import (
    CompletePortOnePaymentUseCase,
    PortOneVerificationError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments/portone", tags=["payments-portone"])


# main.py에서 dependency_overrides로 교체된다.
def get_complete_portone_usecase() -> CompletePortOnePaymentUseCase:
    raise NotImplementedError


@router.post("/complete", status_code=status.HTTP_200_OK)
async def complete_portone_payment(
    body: PortOneCompleteRequest,
    account_id: int | None = Depends(get_optional_account_id),
    usecase: CompletePortOnePaymentUseCase = Depends(get_complete_portone_usecase),
) -> dict[str, str]:
    """FE 결제창 완료(redirect) 후 호출 — 서버에서 결제 재검증 + 유료 결과 발급.

    로그인 상태면 account_id로 결제를 계정에 귀속(보관함). FE는 응답 후 /status 폴링.
    """
    try:
        result = await usecase.complete(body.payment_id, account_id)
    except PortOneVerificationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    return {"status": result, "orderId": body.payment_id}


@router.post("/webhook", response_class=PlainTextResponse)
async def portone_webhook(
    request: Request,
    usecase: CompletePortOnePaymentUseCase = Depends(get_complete_portone_usecase),
) -> PlainTextResponse:
    """포트원 웹훅 수신 — 서명 검증은 UseCase 내부에서. 항상 200(재시도 폭주 방지)."""
    raw = await request.body()
    headers = dict(request.headers.items())
    await usecase.handle_webhook(raw_body=raw.decode("utf-8"), headers=headers)
    return PlainTextResponse("OK", status_code=200)
