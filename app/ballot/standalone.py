from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .router import router
from app.auth.router import router as auth_router


app = FastAPI(
    title="Ballot Casting and Privacy Standalone Module"
)

app.include_router(auth_router)
app.include_router(router)

BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BASE_DIR / "frontend"
BALLOT_FRONTEND_DIR = FRONTEND_DIR / "ballot"

app.mount(
    "/static",
    StaticFiles(directory=FRONTEND_DIR),
    name="static"
)


@app.get("/")
def home():
    return FileResponse(
        BALLOT_FRONTEND_DIR / "index.html"
    )