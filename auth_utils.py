import time
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Request
from fastapi.responses import RedirectResponse

from app_core import get_db_connection

SECRET_KEY = "6fG7@dk93L!vd09a"
ALGORITHM = "HS256"
SESSION_TIMEOUT_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_token(user_id: int) -> str:
    expire = int(time.time()) + SESSION_TIMEOUT_MINUTES * 60
    payload = {
        "sub": str(user_id),
        "iat": int(time.time()),
        "exp": expire
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
        exp = int(payload.get("exp", 0))
        now = int(time.time())

        # Если до истечения токена осталось меньше половины времени — обновим его
        if exp - now < (SESSION_TIMEOUT_MINUTES * 60) // 2:
            new_token = create_token(user_id)
            request.state.refresh_token = new_token  # сохранить для установки позже

    except JWTError:
        return None

    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user
