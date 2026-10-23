
"""Time-based one-time password (TOTP) utilities."""

import pyotp


def generate_mfa_secret() -> str:
    """Generate a unique secret for MFA enrolment."""
    return pyotp.random_base32()


def generate_mfa_uri(username: str, secret: str) -> str:
    """Generate a setup URI for authenticator apps."""
    totp = pyotp.TOTP(secret)

    return totp.provisioning_uri(
        name=username,
        issuer_name="Electronic Voting Platform",
    )


def verify_mfa_code(secret: str, code: str) -> bool:
    """Verify a six-digit TOTP authentication code."""

    if not isinstance(code, str):
        return False

    if len(code) != 6 or not code.isascii() or not code.isdigit():
        return False

    try:
        totp = pyotp.TOTP(secret)
        return bool(totp.verify(code, valid_window=0))
    except (ValueError, TypeError, KeyError):
        return False
