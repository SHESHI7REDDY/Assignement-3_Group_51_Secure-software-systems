from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.shared.config import FRONTEND
from app.candidates.router import router

app = FastAPI(title="Candidate management and administrator security standalone starter")
app.include_router(router)
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
