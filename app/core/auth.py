import hashlib
import secrets
import hmac
from datetime import datetime, timedelta
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from app.core.config import settings


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_login(username: str, password: str) -> bool:
    ok_user = hmac.compare_digest(username, settings.DASHBOARD_USERNAME)
    ok_pass = hmac.compare_digest(
        _hash_password(password),
        _hash_password(settings.DASHBOARD_PASSWORD),
    )
    return ok_user and ok_pass


def create_session_token() -> str:
    return secrets.token_urlsafe(48)


def make_session_value(token: str) -> str:
    """مقدار کوکی: token|timestamp"""
    ts = int(datetime.utcnow().timestamp())
    sig = hmac.new(
        settings.SECRET_KEY.encode(),
        f"{token}|{ts}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{token}|{ts}|{sig}"


def verify_session_cookie(cookie_value: str) -> bool:
    try:
        parts = cookie_value.split("|")
        if len(parts) != 3:
            return False
        token, ts_str, sig = parts
        ts = int(ts_str)
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode(),
            f"{token}|{ts}".encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return False
        age_hours = (datetime.utcnow().timestamp() - ts) / 3600
        return age_hours < settings.SESSION_EXPIRE_HOURS
    except Exception:
        return False


def require_auth(request: Request):
    """dependency برای صفحات داشبورد"""
    cookie = request.cookies.get("brooder_session")
    if not cookie or not verify_session_cookie(cookie):
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return True


def get_auth_or_none(request: Request) -> bool:
    cookie = request.cookies.get("brooder_session")
    return bool(cookie and verify_session_cookie(cookie))
