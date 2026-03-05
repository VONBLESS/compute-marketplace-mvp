from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse

from app.core.security import get_current_email
from app.core.store import store
from app.schemas import FileUploadResponse, utc_after

router = APIRouter()
upload_dir = Path(__file__).resolve().parents[2] / 'uploads'
upload_dir.mkdir(parents=True, exist_ok=True)
FILE_TTL_SECONDS = int(os.getenv('FILE_TTL_SECONDS', '1800'))


@router.post('/upload', response_model=FileUploadResponse)
async def upload_file(request: Request, file: UploadFile = File(...), email: str = Depends(get_current_email)) -> FileUploadResponse:
    store.cleanup_expired_files()
    if not file.filename:
        raise HTTPException(status_code=400, detail='File name is required')

    safe_name = Path(file.filename).name
    file_id = str(uuid4())
    target_name = f'{file_id}_{safe_name}'
    target_path = upload_dir / target_name

    data = await file.read()
    target_path.write_bytes(data)
    expires_at = utc_after(FILE_TTL_SECONDS)
    download_token = str(uuid4())

    store.files[file_id] = {
        'owner_email': email,
        'filename': safe_name,
        'path': str(target_path),
        'download_token': download_token,
        'expires_at': expires_at.isoformat(),
    }

    download_url = str(request.base_url).rstrip('/') + f'/files/{file_id}/{safe_name}?token={download_token}'
    return FileUploadResponse(file_id=file_id, filename=safe_name, download_url=download_url, expires_at=expires_at)


@router.get('/{file_id}/{filename}', include_in_schema=False)
def download_file(file_id: str, filename: str, token: str = Query(default='')) -> FileResponse:
    store.cleanup_expired_files()
    metadata = store.files.get(file_id)
    if not metadata:
        raise HTTPException(status_code=404, detail='File not found')
    if metadata['filename'] != filename:
        raise HTTPException(status_code=404, detail='File not found')
    if not token or metadata.get('download_token') != token:
        raise HTTPException(status_code=403, detail='Invalid download token')

    path = Path(metadata['path'])
    if not path.exists():
        raise HTTPException(status_code=404, detail='File not found')

    return FileResponse(path, filename=metadata['filename'])
