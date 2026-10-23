from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.shared.config import FRONTEND
from app.results.platform_router import router
from app.auth.router import router as auth_router

app = FastAPI(title="Integrated counting results and audit")
app.include_router(auth_router)
app.include_router(router)
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
