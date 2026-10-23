"""ELIG-04: identity kept separate from the ballot token + tamper-evident audit."""
from app.eligibility.repository import connect


def issue(client, auth):
    return client.post("/eligibility/authorizations", json={"voter_id": "V0001", "channel": "ONLINE"},
                       headers=auth("voter", "V0001")).json()


def test_ballot_token_table_has_no_voter_identity(settings):
    conn = connect(settings.db_path)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(ballot_tokens)")}
    assert cols == {"token_hash", "election_id", "division", "expires_at", "redeemed"}


def test_raw_token_never_stored(client, auth, settings):
    token = issue(client, auth)["ballot_token"]
    with open(settings.db_path, "rb") as f:
        raw = f.read()
    conn = connect(settings.db_path)
    dump = "\n".join(conn.iterdump())
    assert token not in dump and token.encode() not in raw


def test_audit_log_has_no_raw_identity(client, auth, settings):
    issue(client, auth)
    client.post("/eligibility/check", json={"voter_id": "V0004"}, headers=auth("officer"))
    conn = connect(settings.db_path)
    text = " ".join(" ".join(map(str, tuple(r))) for r in conn.execute("SELECT * FROM audit_log"))
    for pii in ["V0001", "V0004", "Alice", "Nguyen", "Dev Patel"]:
        assert pii not in text


def test_audit_chain_valid_then_detects_tampering(client, auth, settings):
    issue(client, auth)
    client.post("/eligibility/check", json={"voter_id": "V0002"}, headers=auth("officer"))
    ok = client.get("/eligibility/audit/verify", headers=auth("officer")).json()
    assert ok["valid"] is True and ok["entries"] >= 2

    conn = connect(settings.db_path)
    conn.execute("UPDATE audit_log SET outcome = 'GRANTED' WHERE seq = 2")  # insider edits history
    bad = client.get("/eligibility/audit/verify", headers=auth("officer")).json()
    assert bad == {"valid": False, "entries": 1, "broken_at_seq": 2}


def test_deleting_an_audit_entry_is_detected(client, auth, settings):
    issue(client, auth)
    client.post("/eligibility/check", json={"voter_id": "V0002"}, headers=auth("officer"))
    client.post("/eligibility/check", json={"voter_id": "V0003"}, headers=auth("officer"))
    connect(settings.db_path).execute("DELETE FROM audit_log WHERE seq = 2")
    assert client.get("/eligibility/audit/verify", headers=auth("officer")).json()["valid"] is False


def test_denied_attempts_are_audited(client, auth, settings):
    issue(client, auth)
    client.post("/eligibility/authorizations", json={"voter_id": "V0001", "channel": "ONLINE"},
                headers=auth("voter", "V0001"))
    conn = connect(settings.db_path)
    outcomes = [r[0] for r in conn.execute("SELECT outcome FROM audit_log WHERE action='AUTHORISE' ORDER BY seq")]
    assert outcomes == ["GRANTED", "DENIED:ALREADY_VOTED:already_voted"]
