from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException, Response

from app.core.store import store
from app.schemas import AuthResponse, LoginRequest, MessageResponse, RegisterRequest

router = APIRouter()
SESSION_COOKIE_NAME = 'session_token'


@router.post('/register', response_model=AuthResponse)
def register(payload: RegisterRequest, response: Response) -> AuthResponse:
    if payload.email in store.users:
        raise HTTPException(status_code=400, detail='User already exists')
    store.users[payload.email] = {'password': payload.password, 'role': payload.role}
    token = str(uuid4())
    store.tokens[token] = payload.email
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite='lax',
        secure=False,
        max_age=60 * 60 * 24 * 14,
    )
    return AuthResponse(access_token=token)


@router.post('/login', response_model=AuthResponse)
def login(payload: LoginRequest, response: Response) -> AuthResponse:
    user = store.users.get(payload.email)
    if not user or user['password'] != payload.password:
        raise HTTPException(status_code=401, detail='Invalid credentials')
    token = str(uuid4())
    store.tokens[token] = payload.email
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite='lax',
        secure=False,
        max_age=60 * 60 * 24 * 14,
    )
    return AuthResponse(access_token=token)


@router.post('/logout', response_model=MessageResponse)
def logout(response: Response) -> MessageResponse:
    response.delete_cookie(SESSION_COOKIE_NAME)
    return MessageResponse(message='Logged out')
