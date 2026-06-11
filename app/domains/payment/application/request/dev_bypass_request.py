from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domains.payment.application.request._amplitude_ids import (
    AmplitudeDeviceId,
    AmplitudeSessionId,
)
from app.domains.payment.domain.value_object.payment_status import CharacterCode


class DevBypassRequest(BaseModel):
    """staging/local 결제 패스 요청. prod 환경에서는 endpoint 자체가 등록 X."""

    model_config = ConfigDict(populate_by_name=True)

    session_token: str = Field(alias="sessionToken", min_length=1)
    character: CharacterCode
    customer_email: EmailStr = Field(alias="customerEmail")
    # Amplitude 깔때기 조인용 (선택). 신뢰 경계 밖 — 범위 초과 시 절단/폐기(결제 비블록).
    device_id: AmplitudeDeviceId = Field(default=None, alias="deviceId")
    session_id: AmplitudeSessionId = Field(default=None, alias="sessionId")
