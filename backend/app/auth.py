"""Autenticação: hash de senha (bcrypt) + JWT."""
import datetime as dt

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext

from . import config
from . import db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(user_id: int) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + dt.timedelta(hours=config.JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGO)


def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    """Dependency: valida o JWT e devolve o registro do usuário."""
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sem token")
    try:
        payload = jwt.decode(
            creds.credentials, config.JWT_SECRET, algorithms=[config.JWT_ALGO]
        )
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido")

    user = db.query_one(
        "SELECT id, name, email, role, level FROM users WHERE id=%s", (user_id,)
    )
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário não existe")
    return user
