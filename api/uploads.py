"""POST /api/uploads/image — multipart image upload."""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from services import storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/uploads", tags=["uploads"])

# Soft upper bound on raw upload size. Pillow downscales below FULL_MAX_DIM
# anyway, but we want to reject obvious abuse before reading the whole body.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/image")
async def upload_image(file: UploadFile = File(...)) -> dict[str, str]:
    if file.content_type not in storage.ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported type: {file.content_type}")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large (>{MAX_UPLOAD_BYTES // (1024 * 1024)} MB)")
    try:
        return storage.save_image(data, file.content_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
