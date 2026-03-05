from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from app.core.security import get_current_email
from app.core.store import store
from app.schemas import FileUploadResponse

router = APIRouter()
upload_dir = Path(__file__).resolve().parents[2] / 'uploads'
upload_dir.mkdir(parents=True, exist_ok=True)


@router.post('/upload', response_model=FileUploadResponse)
async def upload_file(request: Request, file: UploadFile = File(...), _: str = Depends(get_current_email)) -> FileUploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail='File name is required')

    safe_name = Path(file.filename).name
    file_id = str(uuid4())
    target_name = f'{file_id}_{safe_name}'
    target_path = upload_dir / target_name

    data = await file.read()
    target_path.write_bytes(data)

    store.files[file_id] = {
        'filename': safe_name,
        'path': str(target_path),
    }

    download_url = str(request.base_url).rstrip('/') + f'/files/{file_id}/{safe_name}'
    return FileUploadResponse(file_id=file_id, filename=safe_name, download_url=download_url)


@router.get('/{file_id}/{filename}', include_in_schema=False)
def download_file(file_id: str, filename: str) -> FileResponse:
    metadata = store.files.get(file_id)
    if not metadata:
        raise HTTPException(status_code=404, detail='File not found')
    if metadata['filename'] != filename:
        raise HTTPException(status_code=404, detail='File not found')

    path = Path(metadata['path'])
    if not path.exists():
        raise HTTPException(status_code=404, detail='File not found')

    return FileResponse(path, filename=metadata['filename'])
