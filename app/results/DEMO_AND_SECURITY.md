# Counting, Results & Audit — Local verification and demo runbook

## Scope

This module is a **fictional, educational prototype**, not a real election platform. It counts local `DEMO-001` ranked-ballot fixtures and provides results publication, public results retrieval and administrative audit functions. No Australian Electoral Commission operational system is accessed.

## Running locally (Windows PowerShell, from the repository root)

1. Install dependencies: `python -m pip install -r requirements.txt` in your virtual environment.
2. Select a **new, empty** local database path and configure `RESULTS_DB_PATH` to point to it. Do not commit that database.
3. Set `RESULTS_ADMIN_TOKEN` to a locally generated strong, random token (at least 16 characters) and set `RESULTS_AUDIT_HMAC_KEY` to the hex encoding of 32 securely random bytes. Keep both out of source control. **Reuse the same HMAC key** for any previously written log.
4. Start `python -m uvicorn app.main:app --reload` in the same terminal session where environment variables were configured.
5. Open `http://127.0.0.1:8000/static/results/index.html` for the results dashboard, or `http://127.0.0.1:8000/docs` for endpoint documentation.

## Demo sequence and expected behavior

- Start with an **empty local** results database. Counting twice for the same election is intentionally rejected.
- With `X-Results-Admin-Token` set to the configured token, `POST /results/count` calculates DEMO-001; expected first round is A=4, B=4, C=2, then A=6, B=4 after C is excluded. Winner: `CAND-A`.
- `GET /results/DEMO-001` returns 404 before publication, including if a count has been saved.
- `POST /results/DEMO-001/publish` without a token returns 401; with an incorrect token, 403; with the correct token, 200. Second publication returns 409.
- `GET /results/DEMO-001` returns 200 after publication. Only aggregate results are exposed; raw ballots and voter identities are not included.
- `GET /results/DEMO-001/audit` and `/results/DEMO-001/audit/verify` require an administrator token. Verify should report a valid audit chain after normal counting and publication.
- Tamper detection should be demonstrated only against a **disposable copy** of the local SQLite database. Changing an event without recomputing its HMAC makes verification fail.

## Test commands

```powershell
.\.venv\Scripts\python.exe -m pytest tests/results/test_end_to_end.py -v
.\.venv\Scripts\python.exe -m pytest -q
```

## Security and functional limitations

- Mock administrator tokens are **not production authentication**. Integrate with the verified authentication module before group deployment.
- Ballots/candidates are local fictional fixtures; the application is not yet connected to the team's ballot and candidate APIs.
- This is a simplified ranked preferential count; tie-resolution and full statutory electoral rules are not implemented. Do not claim full AEC compliance.
- The audit HMAC chain detects unauthorized modification of recorded events when the key is secure. It does **not** by itself prove completeness against truncation or an attacker who controls the key; use external checkpoints/append-only logging for stronger guarantees.
- Counting persistence and audit append, and result-publication update and audit append, are separate operations. A crash between the steps may leave an incomplete audit trail; a production design needs transactional coordination/recovery.
- For submitted evidence, capture genuine test output, a working dashboard, count/publish/audit API requests, and Git history. Never claim tests were executed without observing them locally.
