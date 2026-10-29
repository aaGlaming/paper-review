"""密码哈希与账号字段校验，全部标准库。

哈希：`hashlib.scrypt(n=2**14, r=8, p=1, dklen=32)`，salt 16 字节随机。
存储格式自描述，一个字段装完：

    scrypt$16384$8$1$<salt_b64>$<dk_b64>

base64 后总长约 90 字符，`user.password_hash` 的 VARCHAR(256) 富余。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_DKLEN = 32
_SALT_LEN = 16

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def hash_password(password: str) -> str:
    """scrypt 哈希。salt 每次随机，同一密码两次结果不同。"""
    salt = secrets.token_bytes(_SALT_LEN)
    dk = hashlib.scrypt(
        password.encode("utf-8"), salt=salt,
        n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_DKLEN,
    )
    salt_b64 = base64.b64encode(salt).decode("ascii")
    dk_b64 = base64.b64encode(dk).decode("ascii")
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt_b64}${dk_b64}"


def verify_password(password: str, stored: str) -> bool:
    """校验密码。stored 格式不对时返回 False，不抛异常——
    库里的脏数据不该把登录接口打成 500。"""
    try:
        parts = str(stored).split("$")
        if len(parts) != 6 or parts[0] != "scrypt":
            return False
        n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
        salt = base64.b64decode(parts[4].encode("ascii"))
        expected = base64.b64decode(parts[5].encode("ascii"))
    except (ValueError, TypeError, base64.binascii.Error):
        return False
    try:
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=len(expected),
        )
    except (ValueError, OverflowError):
        return False
    return hmac.compare_digest(actual, expected)


def check_password_strength(password: str) -> str | None:
    """密码强度：返回错误原因，合规则返回 None。"""
    text = str(password or "")
    if not 8 <= len(text) <= 64:
        return "密码长度需 8~64 位"
    if any(ch.isspace() for ch in text):
        return "密码不能含空白字符"
    if not re.search(r"[A-Za-z]", text):
        return "密码需至少一个字母"
    if not re.search(r"[0-9]", text):
        return "密码需至少一个数字"
    return None


def check_username(username: str) -> str | None:
    """用户名：3~32 位，仅字母数字下划线与连字符。"""
    if not _USERNAME_RE.match(str(username or "")):
        return "用户名需 3~32 位，仅字母、数字、下划线与连字符"
    return None


def check_email(email: str) -> str | None:
    """邮箱：简单正则，不追求 RFC 5322 全量。"""
    if not _EMAIL_RE.match(str(email or "")):
        return "邮箱格式不正确"
    return None
