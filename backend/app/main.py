from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException, Response

from .features.admin.router import router as admin_router
from .features.ai_job.router import router as ai_job_router
from .features.asset.router import router as asset_router
from .features.auth.router import router as auth_router
from .features.episode.router import router as episode_router
from .features.project.router import router as project_router
from .features.shot.router import router as shot_router
from .features.storyboard.router import router as storyboard_router
from .features.video.router import router as video_router
from .features.workspace.router import router as workspace_router
from .routers import upload
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

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(workspace_router)
app.include_router(project_router)
app.include_router(episode_router)
app.include_router(shot_router)
app.include_router(storyboard_router)
app.include_router(asset_router)
app.include_router(video_router)
app.include_router(ai_job_router)
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
