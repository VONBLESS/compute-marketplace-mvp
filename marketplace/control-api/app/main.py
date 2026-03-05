from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routes import auth, hosts, jobs

app = FastAPI(title='Compute Marketplace Control API', version='0.1.0')
static_dir = Path(__file__).parent / 'static'

app.include_router(auth.router, prefix='/auth', tags=['auth'])
app.include_router(hosts.router, prefix='/hosts', tags=['hosts'])
app.include_router(jobs.router, prefix='/jobs', tags=['jobs'])
app.mount('/static', StaticFiles(directory=static_dir), name='static')


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.get('/', include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(static_dir / 'index.html')


@app.get('/client', include_in_schema=False)
def client_page() -> FileResponse:
    return FileResponse(static_dir / 'client.html')


@app.get('/host', include_in_schema=False)
def host_page() -> FileResponse:
    return FileResponse(static_dir / 'host.html')
