"""Create persistent local demo configuration without printing secret values."""
import os
import secrets
import shlex
import sqlite3
from pathlib import Path
from app.shared.config import BASE, DATA


def prepare(path=BASE / ".env.integration"):
    path = Path(path)
    if path.exists():
        return False  # Never replace an existing local key configuration.
    results_key = os.getenv("RESULTS_AUDIT_HMAC_KEY")
    db = Path(os.getenv("RESULTS_DB_PATH", str(DATA / "platform_results.sqlite3")))
    if not results_key and db.is_file():
        connection = sqlite3.connect(db)
        try:
            exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                                        "AND name='results_audit_events'").fetchone()
            if exists and connection.execute("SELECT 1 FROM results_audit_events LIMIT 1").fetchone():
                raise ValueError("Restore the existing results audit key before preparing configuration")
        finally:
            connection.close()
    if results_key:
        try:
            if len(bytes.fromhex(results_key)) < 32:
                raise ValueError()
        except ValueError:
            raise ValueError("The existing results audit key must contain at least 32 bytes in hexadecimal") from None
    values = {
        "ELECTION_ID": os.getenv("ELECTION_ID", "DEMO-A3-ELECTIONS"),
        "ELIG_MOCK_AUTH": "0",
        "ELIG_AUTH_VERIFY_URL": "http://127.0.0.1:8000/auth/verify",
        "CAND_AUTH_VERIFY_URL": "http://127.0.0.1:8000/auth/verify",
        "ELIG_AUTH_SECRET": os.getenv("ELIG_AUTH_SECRET") or secrets.token_hex(32),
        "ELIG_PSEUDONYM_KEY": os.getenv("ELIG_PSEUDONYM_KEY") or secrets.token_hex(32),
        "RESULTS_AUDIT_HMAC_KEY": results_key or secrets.token_hex(32),
    }
    # Preserve explicitly configured paths and dates instead of silently switching data.
    for name in ("ELIG_DB_PATH", "RESULTS_DB_PATH", "BALLOT_KEY_FILE", "ELECTION_DATE"):
        if os.getenv(name):
            values[name] = os.environ[name]
    content = "# Local configuration. Never commit or share this file.\n"
    content += "".join(f"export {name}={shlex.quote(value)}\n" for name, value in values.items())
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as destination:
        destination.write(content)
    return True


if __name__ == "__main__":
    try:
        created = prepare()
    except ValueError as error:
        raise SystemExit(str(error)) from None
    print("Local configuration created." if created else "Existing local configuration preserved.")
    print("In the server terminal run: source .env.integration")
    print("Keep this file and data/ballot_key.key private and backed up.")
