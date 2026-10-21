from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.shared.config import FRONTEND
from app.eligibility.router import router

app = FastAPI(title="Voter eligibility and one-vote rule standalone starter")
app.include_router(router)
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
