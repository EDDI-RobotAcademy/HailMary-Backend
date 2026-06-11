"""Amplitude 식별자(device_id/session_id) 입력 정규화 — 결제 요청 3종 DTO 공용.

device_id/session_id는 FE가 보내는 클라이언트 제어 값이라 신뢰 경계 밖이다.
DB 컬럼은 device_id=String(64), session_id=BigInteger(부호 있는 64bit)이므로
범위를 넘는 값이 그대로 INSERT되면 MySQL strict mode에서 1406/1264로 터지고,
결제 라우터는 PayAppGatewayError/ValueError만 잡아 500이 난다.

분석 식별자 때문에 결제가 깨지면 안 된다 → 검증 실패(422)로 막지 말고
조용히 절단/폐기한다(truncate/null). 분석은 degrade는 해도 결제를 블록하지 않는다.
"""

from typing import Annotated

from pydantic import AfterValidator

_DEVICE_ID_MAX = 64  # payment_orm.PaymentORM.device_id = String(64)
_BIGINT_MAX = 9223372036854775807  # signed BIGINT 상한


def _clamp_device_id(v: str | None) -> str | None:
    if v is None:
        return None
    return v[:_DEVICE_ID_MAX]


def _clamp_session_id(v: int | None) -> int | None:
    if v is None:
        return None
    return v if 0 <= v <= _BIGINT_MAX else None


# 결제 요청 DTO에서 device_id/session_id 타입으로 사용. Field(alias=...) 와 함께 쓴다.
AmplitudeDeviceId = Annotated[str | None, AfterValidator(_clamp_device_id)]
AmplitudeSessionId = Annotated[int | None, AfterValidator(_clamp_session_id)]
