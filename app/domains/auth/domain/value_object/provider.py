from enum import Enum


class Provider(str, Enum):
    KAKAO = "kakao"
    GOOGLE = "google"
    TEST = "test"  # 카드사 심사용 테스트 계정 (OAuth 아님, /api/auth/test-login 으로만 발급)
