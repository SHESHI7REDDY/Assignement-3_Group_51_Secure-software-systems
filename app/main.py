from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.shared.config import FRONTEND
from app.auth import router as auth_router
from app.eligibility import router as eligibility_router
from app.ballot import router as ballot_router
from app.candidates import router as candidates_router
from app.results import platform_router as results_router

app = FastAPI(title="Electronic Voting Prototype", version="0.1.0",
    description="Group 51 educational voting prototype with authentication, eligibility, ballot casting and results.")
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
app.include_router(auth_router.router)
app.include_router(eligibility_router.router)
app.include_router(ballot_router.router)
app.include_router(candidates_router.router)
app.include_router(results_router.router)

@app.get("/health", tags=["setup"])
def health():
    return {"status": "ok", "stage": "integration-prototype"}

@app.get("/", include_in_schema=False)
def home():
    return FileResponse(FRONTEND / "index.html")
