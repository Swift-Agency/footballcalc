import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

_fernet: Optional[Fernet] = None


def _load_fernet() -> Optional[Fernet]:
    global _fernet
    if _fernet is not None:
        return _fernet
    raw = os.getenv("CRYPTO_KEY", "").strip()
    if not raw:
        return None
    try:
        _fernet = Fernet(raw.encode("ascii"))
    except Exception:
        return None
    return _fernet


def encrypt_value(plain: str) -> Optional[str]:
    f = _load_fernet()
    if not f:
        return None
    return f.encrypt(plain.encode()).decode()


def decrypt_value(token: str) -> Optional[str]:
    f = _load_fernet()
    if not f:
        return None
    try:
        return f.decrypt(token.encode()).decode()
    except InvalidToken:
        return None


def crypto_configured() -> bool:
    return _load_fernet() is not None
