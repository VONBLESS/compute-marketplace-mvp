from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routes import auth, files, hosts, jobs

app = FastAPI(title='Compute Marketplace Control API', version='0.1.0')
static_dir = Path(__file__).parent / 'static'
agent_binary_path = Path('/opt/host-agent/marketplace-host-agent-setup.exe')

app.include_router(auth.router, prefix='/auth', tags=['auth'])
app.include_router(hosts.router, prefix='/hosts', tags=['hosts'])
app.include_router(jobs.router, prefix='/jobs', tags=['jobs'])
app.include_router(files.router, prefix='/files', tags=['files'])
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


@app.get('/downloads/marketplace-host-agent-setup.exe', include_in_schema=False)
def download_host_agent() -> FileResponse:
    if not agent_binary_path.exists():
        raise HTTPException(status_code=404, detail='Host agent binary is not available on server')
    return FileResponse(
        agent_binary_path,
        media_type='application/octet-stream',
        filename='marketplace-host-agent-setup.exe',
    )
