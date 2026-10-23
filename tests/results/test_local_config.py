"""Local secrets persist across restarts and are never silently replaced."""
import pytest
from scripts.prepare_local_config import prepare


def test_creates_private_reusable_config_without_replacing_key(tmp_path, monkeypatch):
    monkeypatch.setenv("RESULTS_DB_PATH", str(tmp_path / "results.db"))
    monkeypatch.delenv("RESULTS_AUDIT_HMAC_KEY", raising=False)
    path = tmp_path / ".env.integration"
    assert prepare(path) is True
    content = path.read_text()
    assert "RESULTS_AUDIT_HMAC_KEY=" in content
    assert "ELIG_MOCK_AUTH=0" in content
    assert path.stat().st_mode & 0o777 == 0o600
    assert prepare(path) is False
    assert path.read_text() == content


def test_preserves_existing_configured_hmac_key(tmp_path, monkeypatch):
    monkeypatch.setenv("RESULTS_AUDIT_HMAC_KEY", "ab" * 32)
    path = tmp_path / ".env.integration"
    assert prepare(path)
    assert "RESULTS_AUDIT_HMAC_KEY=" + "ab" * 32 in path.read_text()


def test_existing_audit_needs_original_key(tmp_path, monkeypatch):
    from app.results.audit import append_event
    db = tmp_path / "results.db"
    append_event("DEMO-A3-ELECTIONS", "COUNT_COMPLETED", "tester", "success", bytes(range(32)), db)
    monkeypatch.setenv("RESULTS_DB_PATH", str(db))
    monkeypatch.delenv("RESULTS_AUDIT_HMAC_KEY", raising=False)
    path = tmp_path / ".env.integration"
    with pytest.raises(ValueError, match="Restore the existing"):
        prepare(path)
    assert not path.exists()


def test_invalid_configured_key_is_not_silently_replaced(tmp_path, monkeypatch):
    monkeypatch.setenv("RESULTS_AUDIT_HMAC_KEY", "invalid-key")
    path = tmp_path / ".env.integration"
    with pytest.raises(ValueError, match="at least 32 bytes"):
        prepare(path)
    assert not path.exists()
