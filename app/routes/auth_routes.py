from fastapi import APIRouter, Form, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from app_core import get_db_connection
from auth_utils import hash_password, verify_password, create_token
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

router = APIRouter()


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login", include_in_schema=False)
def login(username: str = Form(...), password: str = Form(...)):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()

    if not user or not verify_password(password, user["password_hash"]):
        return HTMLResponse("Неверные учетные данные", status_code=401)

    token = create_token(user["id"])
    response = RedirectResponse("/", status_code=302)
    response.set_cookie("access_token", token, httponly=True)
    return response


@router.get("/register", response_class=HTMLResponse, include_in_schema=False)
def register_form(request: Request):
    return templates.TemplateResponse("auth-form.html", {
        "request": request,
        "title": "Регистрация",
        "action": "/register",
        "submit_label": "Зарегистрироваться",
        "fields": [
            {"name": "username", "type": "text", "placeholder": "Имя пользователя", "required": True},
            {"name": "password", "type": "password", "placeholder": "Пароль", "required": True},
            {"name": "security_answer", "type": "text", "placeholder": "Секретное слово", "required": True}
        ],
        "footer": 'Уже есть аккаунт? <a href="/login">Войти</a>'
    })


@router.post("/register", include_in_schema=False)
def register(
    username: str = Form(...),
    password: str = Form(...),
    security_answer: str = Form(...)
):
    conn = get_db_connection()

    existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        conn.close()
        return HTMLResponse("Пользователь уже существует", status_code=400)

    hashed = hash_password(password)

    conn.execute(
        "INSERT INTO users (username, password_hash, security_answer) VALUES (?, ?, ?)",
        (username, hashed, security_answer.strip().lower())
    )
    conn.commit()

    user_id = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()["id"]
    conn.close()

    token = create_token(user_id)
    response = RedirectResponse("/", status_code=302)
    response.set_cookie("access_token", token, httponly=True)
    return response


@router.get("/logout", include_in_schema=False)
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("access_token")
    return response


@router.get("/forgot-password", response_class=HTMLResponse, include_in_schema=False)
def forgot_password_form(request: Request):
    return templates.TemplateResponse("forgot-password.html", {"request": request})


@router.post("/forgot-password", response_class=HTMLResponse, include_in_schema=False)
def verify_security_answer(
    request: Request,
    username: str = Form(...),
    security_answer: str = Form(...)
):
    conn = get_db_connection()
    user = conn.execute(
        "SELECT id, security_answer FROM users WHERE username = ?", (username,)
    ).fetchone()
    conn.close()

    if not user:
        return templates.TemplateResponse("forgot-password.html", {
            "request": request,
            "error": "Пользователь не найден"
        })

    if not user["security_answer"] or user["security_answer"].strip().lower() != security_answer.strip().lower():
        return templates.TemplateResponse("forgot-password.html", {
            "request": request,
            "error": "Неверный ответ на контрольный вопрос"
        })

    return RedirectResponse(url=f"/reset-password/{user['id']}", status_code=302)
