from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.shared.config import FRONTEND
from app.auth.router import router

app = FastAPI(title="Authentication and sessions standalone starter")
app.include_router(router)
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
