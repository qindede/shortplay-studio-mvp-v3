from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .features.errors import DomainError
from .features.router_utils import resolve_status

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
from .features.upload.router import router as upload_router
from .ai.client import close_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    from .data_io import _ensure_seed_data
    _ensure_seed_data()
    yield
    close_client()


app = FastAPI(title="Muran API", version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    return JSONResponse(status_code=resolve_status(exc), content={"detail": exc.detail})


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
app.include_router(upload_router)


@app.get("/api/health")
def health():
    return {"ok": True, "name": "Muran"}

