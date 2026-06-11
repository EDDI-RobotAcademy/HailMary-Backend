from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse, RedirectResponse

from app.domains.auth.adapter.inbound.api.auth_router import get_optional_account_id
from app.domains.payment.application.request.dev_bypass_request import (
    DevBypassRequest,
)
from app.domains.payment.application.request.request_payment_request import (
    RequestPaymentRequest,
)
from app.domains.payment.application.request.update_email_request import (
    UpdateEmailRequest,
)
from app.domains.payment.application.response.payment_status_response import (
    PaymentStatusResponse,
)
from app.domains.payment.application.response.request_payment_response import (
    RequestPaymentResponse,
)
from app.domains.payment.application.usecase.dev_bypass_payment_usecase import (
    DevBypassPaymentUseCase,
)
from app.domains.payment.application.usecase.get_payment_status_usecase import (
    GetPaymentStatusUseCase,
)
from app.domains.payment.application.usecase.handle_payapp_feedback_usecase import (
    HandlePayAppFeedbackUseCase,
)
from app.domains.payment.application.usecase.request_payment_usecase import (
    RequestPaymentUseCase,
)
from app.domains.payment.application.usecase.update_email_and_resend_usecase import (
    UpdateEmailAndResendUseCase,
)
from app.domains.payment.domain.port.payapp_payment_port import PayAppGatewayError

router = APIRouter(prefix="/api/payments", tags=["payments"])


# main.py에서 dependency_overrides로 교체된다.
def get_request_payment_usecase() -> RequestPaymentUseCase:
    raise NotImplementedError


def get_handle_feedback_usecase() -> HandlePayAppFeedbackUseCase:
    raise NotImplementedError


def get_payment_status_usecase() -> GetPaymentStatusUseCase:
    raise NotImplementedError


def get_update_email_usecase() -> UpdateEmailAndResendUseCase:
    raise NotImplementedError


def get_dev_bypass_usecase() -> DevBypassPaymentUseCase:
    raise NotImplementedError


@router.post(
    "/request",
    response_model=RequestPaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_payment(
    body: RequestPaymentRequest,
    account_id: int | None = Depends(get_optional_account_id),
    usecase: RequestPaymentUseCase = Depends(get_request_payment_usecase),
) -> RequestPaymentResponse:
    """PayApp 결제 요청. 응답의 payurl로 FE가 리다이렉트.

    로그인 상태면 account_id로 결제를 계정에 귀속(보관함). 비로그인이면 None.
    """
    try:
        return await usecase.execute(body, account_id)
    except PayAppGatewayError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": e.code or "PAYAPP_GATEWAY_ERROR", "message": str(e)},
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


def get_frontend_base_url() -> str:
    """main.py에서 dependency_overrides로 settings.frontend_base_url 주입."""
    raise NotImplementedError


@router.post("/return")
async def payapp_return(
    request: Request,
    frontend_base_url: str = Depends(get_frontend_base_url),
) -> RedirectResponse:
    """PayApp `skip_cstpage=y` 시 returnurl로 POST 호출됨 — S3는 POST 못 받으므로
    BE가 받아서 FE `/checkout/success/` 로 303 redirect (POST → GET 우회).

    2026-06-05 prod 실결제 사고 hotfix: FE가 sessionStorage(checkoutPending)에만
    의존하면 카드사 인증 복귀가 새 브라우저 컨텍스트로 떨어질 때 세션이 유실돼
    "결제 세션 정보 없음"이 떴음. payrequest에 var1=order_id를 보내두었고 PayApp이
    returnurl POST form에 동봉하므로, 이를 ?order_id= 쿼리로 FE에 전달한다.
    FE는 URL 쿼리 우선 → sessionStorage → localStorage 순으로 복구.
    (결제 기록 자체는 webhook `/feedback`에서 처리 — 여기는 표시용 식별자만.)
    """
    order_id = ""
    try:
        form = await request.form()
        order_id = str(form.get("var1") or "")
    except Exception:  # noqa: BLE001 — form 파싱 실패해도 redirect는 유지 (기존 동작)
        order_id = ""
    target = f"{frontend_base_url.rstrip('/')}/checkout/success/"
    if order_id:
        target = f"{target}?order_id={quote(order_id)}"
    return RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)


@router.post(
    "/feedback",
    response_class=PlainTextResponse,
)
async def payapp_feedback(
    request: Request,
    usecase: HandlePayAppFeedbackUseCase = Depends(get_handle_feedback_usecase),
) -> PlainTextResponse:
    """PayApp webhook 수신. 항상 'SUCCESS' 응답 (재시도 방지 위해 처리 실패도 SUCCESS).

    실패는 내부 로그만 남기고 사용자/PayApp에게는 SUCCESS 반환 — 잘못된 webhook은
    재시도해도 결과 동일하므로 재시도 의미 없음.
    """
    form = await request.form()
    form_dict = {k: v for k, v in form.items() if isinstance(v, str)}
    await usecase.execute(form_dict)
    return PlainTextResponse("SUCCESS", status_code=200)


@router.post("/update-email", status_code=status.HTTP_200_OK)
async def update_email(
    body: UpdateEmailRequest,
    usecase: UpdateEmailAndResendUseCase = Depends(get_update_email_usecase),
) -> dict[str, str]:
    """결제 완료 후 사용자가 결과지 받을 이메일을 수정한 경우.

    Payment.customer_email 업데이트 + 이미 합성된 PaidReport 있으면 새 주소로 메일 재발송.
    """
    try:
        await usecase.execute(order_id=body.order_id, new_email=body.new_email)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    return {"status": "updated"}


@router.get(
    "/status",
    response_model=PaymentStatusResponse,
)
async def get_payment_status(
    order_id: str,
    usecase: GetPaymentStatusUseCase = Depends(get_payment_status_usecase),
) -> PaymentStatusResponse:
    """FE polling: PayApp returnurl 도착 후 결제완료 webhook 처리 확인."""
    result = await usecase.execute(order_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="결제 정보를 찾을 수 없습니다.",
        )
    return result


# ⚠️ staging/local 전용 — main.py에서 app_env != "prod" 일 때만 include.
# 결제 단계를 건너뛰고 즉시 DONE 상태로 진입. QA 시 매번 실 결제 안 하기 위함.
dev_router = APIRouter(prefix="/api/payments/dev", tags=["payments-dev"])


@dev_router.post("/bypass", status_code=status.HTTP_201_CREATED)
async def dev_bypass_payment(
    body: DevBypassRequest,
    account_id: int | None = Depends(get_optional_account_id),
    usecase: DevBypassPaymentUseCase = Depends(get_dev_bypass_usecase),
) -> dict[str, str]:
    """결제 통과 처리. FE는 응답의 orderId로 /saju/paid/{orderId}/loading 진입."""
    try:
        order_id = await usecase.execute(
            session_token=body.session_token,
            character=body.character,
            customer_email=body.customer_email,
            account_id=account_id,
            device_id=body.device_id,
            session_id=body.session_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    return {"orderId": order_id}
