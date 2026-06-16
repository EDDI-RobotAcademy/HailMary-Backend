import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# ── APP_ENV에 따라 env_file 분기 ──
# local → .env.local (개발)
# test  → .env.test (QA 분리 DB, 포트 3308)
# prod  → .env.prod (운영)
_ENV_FILE_MAP: dict[str, str] = {
    "local": ".env.local",
    "test": ".env.test",
    "prod": ".env.prod",
}
_CURRENT_ENV: str = os.environ.get("APP_ENV", "local")
_ENV_FILE: str = _ENV_FILE_MAP.get(_CURRENT_ENV, ".env.local")


class Settings(BaseSettings):
    database_url: str
    fortuneteller_url: str
    claude_api_key: str | None = None
    claude_model: str = "claude-sonnet-4-6"
    app_env: str = "local"
    debug: bool = False
    # PayApp 결제 (서버 to 서버, FE는 키 사용 X)
    payapp_base_url: str = "https://api.payapp.kr"
    payapp_userid: str | None = None        # 가맹점 ID
    payapp_linkkey: str | None = None       # 연동 KEY (feedback 검증용)
    payapp_linkval: str | None = None       # 연동 VALUE (feedback 검증용)
    payapp_feedback_url: str | None = None  # PayApp webhook 수신 URL (외부 노출 필수)
    payapp_return_url: str | None = None    # 결제완료 후 사용자 도착 URL (BE redirect endpoint 권장)
    # PayApp returnurl 처리 후 FE로 redirect할 baseURL (skip_cstpage POST 우회용)
    frontend_base_url: str = "http://localhost:3000"
    # Amplitude HTTP API V2 (백엔드 결제 이벤트 발화용)
    amplitude_api_key: str | None = None
    amplitude_base_url: str = "https://api2.amplitude.com"
    # AWS SES (이메일 발송, Phase 4 추가 예정)
    aws_region: str = "ap-northeast-2"
    aws_ses_sender: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    # QA 로그인 게이트 (APP_ENV=test 일 때만 활성, 운영에선 무시)
    qa_username: str | None = None
    qa_password: str | None = None
    qa_access_token: str | None = None
    # 소셜 로그인 (HM-BE-77, 카카오/구글 OAuth + 계정 JWT)
    # 전부 미설정이어도 기존 플로 영향 0 — /api/auth/* 만 503/400으로 비활성.
    jwt_secret: str | None = None
    jwt_expires_days: int = 30
    kakao_client_id: str | None = None       # 카카오 REST API 키
    kakao_client_secret: str | None = None   # 카카오 로그인용 Client Secret
    google_client_id: str | None = None
    google_client_secret: str | None = None
    # 카드사 심사용 테스트 로그인 (HM-BE-84). enabled=True 일 때만 /api/auth/test-login 동작 +
    # provider=test 계정 결제 0원 자동 발급. 심사 종료 후 False+재배포로 완전 차단.
    test_login_enabled: bool = False
    test_login_username: str | None = None
    test_login_password: str | None = None
    # Redis 캐시 (HM-BE-67, 깨비 일일사주). cache_enabled=False면 캐시 미사용.
    redis_url: str = "redis://127.0.0.1:6379/0"
    cache_enabled: bool = True
    kkebi_pillars_ttl_seconds: int = 60 * 60 * 24 * 30  # 30일 (일주는 평생 불변, 안전상 만료)
    kkebi_result_ttl_seconds: int = 60 * 60 * 25         # 25시간 (KST 자정 + 1h 여유)

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
