"""自签 compact token（这不是 JWT，文档、注释、响应里都不写 JWT）。

格式三段：

    v1.<b64url(payload_json)>.<b64url(hmac_sha256(secret, "v1." + payload_b64))>

payload = {"uid": user_id, "role": role, "exp": 到期 unix 秒, "pv": 密码指纹}
- `pv` = sha256(password_hash).hexdigest()[:16]：用户改密码后所有旧 token
  自动失效，不需要第三张表。
- 默认时效 8 小时，可用 AUTH_TOKEN_TTL_HOURS 覆盖。

AUTH_SECRET 只从环境变量读：长度 < 32 直接 raise RuntimeError，
不许有默认值、不许静默降级。这个值不许出现在任何日志、响应、测试夹具里。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

_VERSION = "v1"
_DEFAULT_TTL_HOURS = 8.0

#: decode_token 失败原因枚举，只有这五个。
REASONS = ("bad_format", "bad_signature", "expired", "pv_mismatch", "unknown_user")


class TokenError(Exception):
    """token 校验失败，reason 取 REASONS 之一。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason if reason in REASONS else "bad_format"


def _secret() -> bytes:
    raw = os.environ.get("AUTH_SECRET", "")
    if len(raw) < 32:
        raise RuntimeError("AUTH_SECRET 缺失或过短（需 ≥32 字符），拒绝签发 token")
    return raw.encode("utf-8")


def _ttl_seconds() -> int:
    try:
        hours = float(os.environ.get("AUTH_TOKEN_TTL_HOURS", "") or _DEFAULT_TTL_HOURS)
    except ValueError:
        hours = _DEFAULT_TTL_HOURS
    return max(60, int(hours * 3600))


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def password_fingerprint(password_hash: str) -> str:
    """密码指纹：sha256(password_hash)[:16]。改密码即旧 token 全失效。"""
    return hashlib.sha256(str(password_hash).encode("utf-8")).hexdigest()[:16]


def issue_token(user_id: str, role: str, password_hash: str, *, ttl_s: int | None = None) -> str:
    """签发 token。secret 不足直接抛 RuntimeError。"""
    payload = {
        "uid": str(user_id),
        "role": str(role),
        "exp": int(time.time()) + (ttl_s if ttl_s is not None else _ttl_seconds()),
        "pv": password_fingerprint(password_hash),
    }
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{_VERSION}.{body}"
    sig = hmac.new(_secret(), signing_input.encode("utf-8"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64encode(sig)}"


def decode_token(token: str) -> dict:
    """校验并解出 payload。失败抛 TokenError(reason=...)，签名比较用 compare_digest。"""
    try:
        version, body, sig = str(token).split(".")
    except ValueError:
        raise TokenError("bad_format") from None
    if version != _VERSION or not body or not sig:
        raise TokenError("bad_format")
    signing_input = f"{version}.{body}"
    try:
        expected = hmac.new(_secret(), signing_input.encode("utf-8"), hashlib.sha256).digest()
        actual = _b64decode(sig)
    except (ValueError, base64.binascii.Error):
        raise TokenError("bad_format") from None
    if not hmac.compare_digest(actual, expected):
        raise TokenError("bad_signature")
    try:
        payload = json.loads(_b64decode(body).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise TokenError("bad_format") from None
    if not isinstance(payload, dict) or "uid" not in payload or "exp" not in payload:
        raise TokenError("bad_format")
    try:
        expired = int(payload["exp"]) <= int(time.time())
    except (ValueError, TypeError):
        raise TokenError("bad_format") from None
    if expired:
        raise TokenError("expired")
    return payload
