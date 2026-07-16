"""결제 요청 DTO의 Amplitude 식별자 정규화 회귀 테스트.

신뢰 경계 밖 device_id/session_id가 DB 컬럼(String(64)/BigInteger) 범위를 넘겨도
검증 실패(422)가 아니라 절단/폐기로 흡수돼 결제 요청이 깨지지 않아야 한다.
"""

from app.domains.payment.application.request.dev_bypass_request import DevBypassRequest
from app.domains.payment.application.request.redeem_coupon_request import (
    RedeemCouponRequest,
)
from app.domains.payment.application.request.request_payment_request import (
    RequestPaymentRequest,
)

_BIGINT_MAX = 9223372036854775807


def _base_request_payment(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "sessionToken": "tok",
        "character": "yeonwoo",
        "customerEmail": "a@b.com",
    }
    payload.update(overrides)
    return payload


def test_oversized_device_id_truncated_to_64_not_rejected() -> None:
    req = RequestPaymentRequest(**_base_request_payment(deviceId="x" * 200))
    assert req.device_id is not None
    assert len(req.device_id) == 64


def test_normal_uuid_device_id_passes_through() -> None:
    uuid = "01234567-89ab-cdef-0123-456789abcdef"  # 36자
    req = RequestPaymentRequest(**_base_request_payment(deviceId=uuid))
    assert req.device_id == uuid


def test_session_id_over_bigint_max_nulled() -> None:
    req = RequestPaymentRequest(**_base_request_payment(sessionId=_BIGINT_MAX + 1))
    assert req.session_id is None


def test_negative_session_id_nulled() -> None:
    req = RequestPaymentRequest(**_base_request_payment(sessionId=-1))
    assert req.session_id is None


def test_valid_epoch_ms_session_id_passes() -> None:
    epoch_ms = 1749607739000
    req = RequestPaymentRequest(**_base_request_payment(sessionId=epoch_ms))
    assert req.session_id == epoch_ms


def test_missing_ids_default_to_none() -> None:
    req = RequestPaymentRequest(**_base_request_payment())
    assert req.device_id is None
    assert req.session_id is None


def test_clamp_applies_to_dev_bypass_and_redeem() -> None:
    bypass = DevBypassRequest(
        sessionToken="tok",
        character="yeonwoo",
        customerEmail="a@b.com",
        deviceId="y" * 100,
        sessionId=_BIGINT_MAX + 5,
    )
    assert len(bypass.device_id or "") == 64
    assert bypass.session_id is None

    redeem = RedeemCouponRequest(
        sessionToken="tok",
        character="yeonwoo",
        customerEmail="a@b.com",
        code="FREE1",
        deviceId="z" * 100,
        sessionId=-9,
    )
    assert len(redeem.device_id or "") == 64
    assert redeem.session_id is None
