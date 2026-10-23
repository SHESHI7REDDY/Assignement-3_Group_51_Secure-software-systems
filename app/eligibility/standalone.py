"""Standalone demo of the eligibility module (owner: Ved).

Run:  python -m app.eligibility.repository        (seed fictional voters)
      python -m uvicorn app.eligibility.standalone:app --reload --port 8002
Open: http://127.0.0.1:8002/static/eligibility/index.html

The standalone server includes real authentication for the shared eligibility
page. Signed mock tokens remain available only when explicitly enabled for
isolated API tests. The integrated app never exposes /dev/mock-token.
"""
import os

os.environ.setdefault("ELIG_MOCK_AUTH", "0")
os.environ.setdefault("ELIG_AUTH_VERIFY_URL", "http://127.0.0.1:8002/auth/verify")

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.responses import RedirectResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from app.eligibility.config import get_settings  # noqa: E402
from app.eligibility.router import router  # noqa: E402
from app.eligibility.schemas import MockTokenRequest  # noqa: E402
from app.eligibility.security import issue_mock_token  # noqa: E402
from app.shared.config import FRONTEND  # noqa: E402
from app.auth.router import router as auth_router  # noqa: E402

SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; "
                               "img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
    "Cache-Control": "no-store",
}


def create_app() -> FastAPI:
    app = FastAPI(title="Voter eligibility and one-vote rule (standalone)")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            if k == "Content-Security-Policy" and request.url.path in ("/docs", "/redoc"):
                continue  # Swagger UI (dev only) loads CDN assets
            response.headers.setdefault(k, v)
        return response

    app.include_router(router)
    app.include_router(auth_router)
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

    @app.post("/dev/mock-token", tags=["dev"])
    def mock_token(body: MockTokenRequest, request: Request):
        settings = request.app.dependency_overrides.get(get_settings, get_settings)()
        if not settings.mock_auth:
            raise HTTPException(404, "Not found")
        if body.role == "voter" and not body.voter_id:
            raise HTTPException(422, "voter tokens need a voter_id")
        return {"access_token": issue_mock_token(settings, body.user_id, body.role, body.voter_id),
                "token_type": "bearer"}

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse("/static/eligibility/index.html")

    return app


app = create_app()
