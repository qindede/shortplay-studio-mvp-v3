from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException, Response

from .routers import admin, auth, content, upload
from . import storage
from .ai.client import close_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_client()


app = FastAPI(title="Muran API", version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(content.router)
app.include_router(admin.router)
app.include_router(upload.router)


@app.get("/api/health")
def health():
    return {"ok": True, "name": "Muran"}


@app.get("/uploads/{path:path}")
def uploads(path: str):
    try:
        data, content_type = storage.get_object(path)
    except storage.StorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(content=data, media_type=content_type)
