
"""Encryption helpers for MFA secrets."""

import os

from cryptography.fernet import Fernet, InvalidToken


def get_cipher() -> Fernet:
    """Read the MFA encryption key from the environment."""
    key = os.environ.get("AUTH_MFA_KEY")

    if not key:
        raise RuntimeError(
            "AUTH_MFA_KEY is not configured"
        )

    return Fernet(key.encode("ascii"))


def encrypt_mfa_secret(secret: str) -> str:
    """Encrypt a TOTP secret before database storage."""
    encrypted = get_cipher().encrypt(
        secret.encode("utf-8")
    )
    return encrypted.decode("ascii")


def decrypt_mfa_secret(encrypted_secret: str) -> str:
    """Decrypt a stored TOTP secret."""
    try:
        decrypted = get_cipher().decrypt(
            encrypted_secret.encode("ascii")
        )
        return decrypted.decode("utf-8")
    except InvalidToken as exc:
        raise ValueError(
            "Unable to decrypt MFA secret"
        ) from exc
