"""FastAPI entry point.

Run with: uvicorn server:app --reload --port 8000
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.itinerary import router as itinerary_router
from api.maps import router as maps_router
from api.points import router as points_router
from api.tracks import router as tracks_router
from services.db import Base, engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    logger.info("Voyage Map API ready.")
    yield


app = FastAPI(title="Voyage Map", lifespan=lifespan)

_allowed_origins = ["http://localhost:5173", "http://localhost:3000"]
_prod_url = os.environ.get("FRONTEND_URL", "")
if _prod_url:
    _allowed_origins.append(_prod_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(maps_router, prefix="/api")
app.include_router(points_router, prefix="/api")
app.include_router(tracks_router, prefix="/api")
app.include_router(itinerary_router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve built Vue frontend (production mode)
_dist = Path("frontend/dist")
if _dist.exists():
    _assets = _dist / "assets"
    if _assets.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        file_path = _dist / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_dist / "index.html"))
