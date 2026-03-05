from __future__ import annotations

from fastapi import Cookie, Header, HTTPException

from app.core.store import store


def get_current_email(
    authorization: str = Header(default=''),
    session_token: str | None = Cookie(default=None),
) -> str:
    token = ''
    if authorization.startswith('Bearer '):
        token = authorization.removeprefix('Bearer ').strip()
    elif session_token:
        token = session_token

    if not token:
        raise HTTPException(status_code=401, detail='Missing authentication')

    email = store.tokens.get(token)
    if not email:
        raise HTTPException(status_code=401, detail='Invalid token')
    return email


def get_host_from_api_key(x_host_api_key: str = Header(default='')) -> str:
    for host in store.hosts.values():
        if host.api_key == x_host_api_key:
            return host.id
    raise HTTPException(status_code=401, detail='Invalid host api key')
