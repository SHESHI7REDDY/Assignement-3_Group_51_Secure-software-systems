# Counting, results and audit

Module owner: Moinul. The shared integration reuses the module's preferential counting algorithm and adds the real-ballot adapter.

Run the shared application with `python -m uvicorn app.main:app --reload --port 8000`.
The results page is `/static/results/index.html`. Use a separately provisioned real administrator account; the old demonstration header does not grant access to the shared application.

Read [the integration instructions](../../docs/results-integration.md) for persistent configuration, account setup, election closure, counting, publication and report evidence.

- Shared router: `platform_router.py`; orchestration: `platform.py`.
- Counting algorithm: `counting.py`, `preferential.py`, `elimination.py`, `service.py`.
- Storage and HMAC audit helpers: `repository.py`, `audit.py`.
- Original fixture routes: `router.py` and related `*_api.py` files. These remain in isolated module tests, and are not mounted by `app.main` or `app.results.standalone`.
- Tests: `python -m pytest tests/results -q`.

The old fixture instructions below are historical algorithm demonstrations, not the final integrated flow: `API_CONTRACT.md` and `DEMO_AND_SECURITY.md`.
