from cryptography.fernet import Fernet, InvalidToken

_fernet: Fernet | None = None


class EncryptionNotInitialized(Exception):
    pass


def init_fernet(encryption_key: str) -> None:
    global _fernet
    _fernet = Fernet(encryption_key.encode())


def encrypt_api_key(raw_key: str) -> bytes:
    if _fernet is None:
        raise EncryptionNotInitialized("init_fernet() was not called")
    return _fernet.encrypt(raw_key.encode())


def decrypt_api_key(token: bytes) -> str:
    """Raises cryptography.fernet.InvalidToken if the token can't be decrypted
    (e.g. ENCRYPTION_KEY was rotated) — callers should treat this like an invalid API key."""
    if _fernet is None:
        raise EncryptionNotInitialized("init_fernet() was not called")
    return _fernet.decrypt(token).decode()


__all__ = ["init_fernet", "encrypt_api_key", "decrypt_api_key", "InvalidToken", "EncryptionNotInitialized"]
