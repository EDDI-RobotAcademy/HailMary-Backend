from pydantic import BaseModel, ConfigDict, Field


class PortOneCompleteRequest(BaseModel):
    """포트원 결제창 완료 후 FE가 검증 요청. paymentId 만 받고 나머지는 서버가 조회/검증."""

    model_config = ConfigDict(populate_by_name=True)

    payment_id: str = Field(alias="paymentId")
