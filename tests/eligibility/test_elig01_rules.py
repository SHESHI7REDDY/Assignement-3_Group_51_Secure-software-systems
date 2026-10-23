"""ELIG-01: server-side eligibility verification against the electoral roll."""
from datetime import date

import pytest

from app.eligibility.service import evaluate

ELECTION = date(2026, 12, 5)


def elector(**over):
    base = {"enrolment_status": "ENROLLED", "citizenship": "AU", "date_of_birth": "1990-01-01",
            "disqualified": 0}
    base.update(over)
    return base


@pytest.mark.parametrize("voter_id,eligible,reason", [
    ("V0001", True, "ELIGIBLE"),        # enrolled adult citizen
    ("V0002", False, "NOT_ELIGIBLE"),   # under 18
    ("V0003", False, "NOT_ELIGIBLE"),   # not a citizen
    ("V0004", False, "NOT_ELIGIBLE"),   # disqualified
    ("V0005", False, "NOT_ENROLLED"),   # enrolment pending
    ("V0006", False, "ALREADY_VOTED"),  # already voted
    ("V9999", False, "NOT_ENROLLED"),   # not on the roll
])
def test_eligibility_decisions_via_api(client, auth, voter_id, eligible, reason):
    r = client.post("/eligibility/check", json={"voter_id": voter_id}, headers=auth("officer"))
    assert r.status_code == 200
    assert r.json()["eligible"] is eligible
    assert r.json()["reason"] == reason


def test_turning_18_on_election_day_is_eligible():
    assert evaluate(elector(date_of_birth="2008-12-05"), False, ELECTION).eligible


def test_turning_18_day_after_election_is_not_eligible():
    d = evaluate(elector(date_of_birth="2008-12-06"), False, ELECTION)
    assert not d.eligible and d.detail == "under_18"


def test_deny_by_default_for_missing_record():
    assert evaluate(None, False, ELECTION).reason == "NOT_ENROLLED"


def test_response_does_not_leak_personal_details(client, auth):
    body = client.post("/eligibility/check", json={"voter_id": "V0004"}, headers=auth("officer")).text
    for leaked in ["Dev Patel", "1979", "disqualified", "Perth"]:
        assert leaked not in body
