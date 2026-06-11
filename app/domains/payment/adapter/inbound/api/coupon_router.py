from fastapi import APIRouter, Depends, HTTPException, status

from app.domains.auth.adapter.inbound.api.auth_router import get_optional_account_id
from app.domains.payment.application.request.redeem_coupon_request import (
    RedeemCouponRequest,
)
from app.domains.payment.application.request.validate_coupon_request import (
    ValidateCouponRequest,
)
from app.domains.payment.application.response.validate_coupon_response import (
    ValidateCouponResponse,
)
from app.domains.payment.application.usecase.redeem_coupon_usecase import (
    CouponNotRedeemableError,
    RedeemCouponUseCase,
)
from app.domains.payment.application.usecase.validate_coupon_usecase import (
    ValidateCouponUseCase,
)

router = APIRouter(prefix="/api/coupons", tags=["coupons"])


# main.py에서 dependency_overrides로 교체된다.
def get_validate_coupon_usecase() -> ValidateCouponUseCase:
    raise NotImplementedError


def get_redeem_coupon_usecase() -> RedeemCouponUseCase:
    raise NotImplementedError


@router.post("/validate", response_model=ValidateCouponResponse)
async def validate_coupon(
    body: ValidateCouponRequest,
    usecase: ValidateCouponUseCase = Depends(get_validate_coupon_usecase),
) -> ValidateCouponResponse:
    """쿠폰 "적용" — 코드 유효성만 확인. 읽기 전용."""
    return await usecase.execute(code=body.code)


@router.post("/redeem", status_code=status.HTTP_201_CREATED)
async def redeem_coupon(
    body: RedeemCouponRequest,
    account_id: int | None = Depends(get_optional_account_id),
    usecase: RedeemCouponUseCase = Depends(get_redeem_coupon_usecase),
) -> dict[str, str]:
    """쿠폰 "무료로 받기" — 소진 + 무료 결과지 발급. FE는 orderId로 결과 폴링 진입."""
    try:
        order_id = await usecase.execute(
            session_token=body.session_token,
            character=body.character,
            customer_email=body.customer_email,
            code=body.code,
            account_id=account_id,
            device_id=body.device_id,
            session_id=body.session_id,
        )
    except CouponNotRedeemableError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    return {"orderId": order_id}
