# Candidate management and administrator security
Owner: Sashi

Status: not implemented. All feature endpoints return HTTP 501.

Run the shared app with `python -m uvicorn app.main:app --reload`.
For this module alone, use `python -m uvicorn app.candidates.standalone:app --reload`.
Open `/static/candidates/index.html` for the placeholder screen and `/docs` for routes.
Run this module's future tests with `python -m pytest tests/candidates`.

Implement in your own feature branch:
- GUI in frontend/candidates/ and validated API models in schemas.py.
- API routes, service rules, SQLite schema/repository and fictional seed data.
- Positive and negative security tests linked to your four requirement issues.
- API contract changes, report evidence and setup/demo instructions.

Agree authentication, authorization and integration behavior before replacing placeholders.
Never treat a client-supplied user ID or role as proof of authority.
