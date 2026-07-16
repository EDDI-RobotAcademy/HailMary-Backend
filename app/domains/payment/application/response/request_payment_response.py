from pydantic import BaseModel, ConfigDict, Field


class RequestPaymentResponse(BaseModel):
    """BE → FE. FE는 payurl로 리다이렉트하면 됨."""

    model_config = ConfigDict(populate_by_name=True)

    order_id: str = Field(alias="orderId")
    # 테스트 계정 무료 발급 시 빈 문자열 — FE는 free_granted로 PayApp 스킵 판정.
    payurl: str
    free_granted: bool = Field(default=False, alias="freeGranted")
