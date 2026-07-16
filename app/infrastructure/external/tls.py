"""Windows 로컬 OPENSSL_Applink 크래시 우회용 SSL 컨텍스트.

증상: `ssl.create_default_context()` / httpx 기본 verify가
`OPENSSL_Uplink(...): no OPENSSL_Applink`로 프로세스 즉사 (Windows 로컬 한정,
Linux EC2 정상 — DEPLOY.md Troubleshooting 2026-05-30 참조).

원인: OpenSSL이 CA "파일"을 읽는 경로(stdio FILE* / applink 필요)가 이 환경에서 깨짐.
우회: certifi PEM을 파이썬이 읽어 **메모리(cadata)** 로 로드 — OpenSSL 파일 I/O를 안 탐.
신뢰 저장소는 httpx 기본(certifi)과 동일하므로 보안 다운그레이드 없음. 전 플랫폼 안전.
"""

import ssl

import certifi


def build_client_ssl_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.check_hostname = True
    with open(certifi.where(), encoding="utf-8") as f:
        ctx.load_verify_locations(cadata=f.read())
    return ctx
