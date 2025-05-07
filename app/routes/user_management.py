# app/routes/user_management.py

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from datetime import datetime
import secrets

from app_core import get_db_connection
from auth_utils import hash_password, get_current_user
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/manage-users", response_class=HTMLResponse, include_in_schema=False)
def manage_users(request: Request, user=Depends(get_current_user)):
    if not user or user["role"] != "admin":
        return RedirectResponse("/", status_code=302)

    conn = get_db_connection()
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return templates.TemplateResponse("manage_users.html", {
        "request": request,
        "users": users,
        "user": user
    })


@router.get("/delete-user/{user_id}", include_in_schema=False)
def delete_user(user_id: int, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/manage-users", status_code=303)


@router.get("/edit-user/{user_id}", response_class=HTMLResponse, include_in_schema=False)
def edit_user_form(user_id: int, request: Request, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = get_db_connection()
    u = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    if not u:
        return HTMLResponse("Пользователь не найден", status_code=404)

    return templates.TemplateResponse("edit_user.html", {
        "request": request,
        "user": u
    })


@router.post("/edit-user/{user_id}", include_in_schema=False)
def update_user(
    user_id: int,
    surname: str = Form(""),
    name: str = Form(""),
    patronymic: str = Form(""),
    security_answer: str = Form(""),
    role: str = Form("user"),
    current_user=Depends(get_current_user)
):
    if not current_user:
        return RedirectResponse("/login", status_code=302)

    conn = get_db_connection()
    conn.execute("""
        UPDATE users 
        SET surname = ?, name = ?, patronymic = ?, security_answer = ?, role = ?
        WHERE id = ?
    """, (surname.strip(), name.strip(), patronymic.strip(), security_answer.strip(), role.strip(), user_id))
    conn.commit()
    conn.close()

    return RedirectResponse("/manage-users", status_code=303)


@router.get("/create-user", response_class=HTMLResponse, include_in_schema=False)
def create_user_form(request: Request, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    empty_user = {
        "username": "",
        "surname": "",
        "name": "",
        "patronymic": ""
    }
    return templates.TemplateResponse("edit_user.html", {
        "request": request,
        "user": empty_user,
        "is_create": True
    })


@router.post("/create-user", include_in_schema=False)
def create_user(
    username: str = Form(...),
    password: str = Form(...),
    surname: str = Form(""),
    name: str = Form(""),
    patronymic: str = Form(""),
    user=Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = get_db_connection()
    cursor = conn.cursor()

    existing = cursor.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        conn.close()
        return HTMLResponse(content="Пользователь с таким логином уже существует", status_code=400)

    hashed_password = hash_password(password)
    cursor.execute("""
        INSERT INTO users (username, password_hash, surname, name, patronymic)
        VALUES (?, ?, ?, ?, ?)
    """, (username, hashed_password, surname, name, patronymic))
    conn.commit()
    conn.close()

    return RedirectResponse("/manage-users", status_code=303)


@router.get("/manage-api-tokens", response_class=HTMLResponse, include_in_schema=False)
def manage_api_tokens(request: Request, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = get_db_connection()

    if user["role"] == "admin":
        users = conn.execute("SELECT id, username FROM users").fetchall()
        tokens = conn.execute("""
            SELECT api_tokens.id, token, created_at, expires_at, comment, users.username
            FROM api_tokens
            JOIN users ON api_tokens.user_id = users.id
            ORDER BY created_at DESC
        """).fetchall()
        requests = conn.execute("""
            SELECT token_requests.*, users.username
            FROM token_requests
            JOIN users ON token_requests.user_id = users.id
            ORDER BY requested_at DESC
        """).fetchall()
    else:
        users = []
        tokens = conn.execute("""
            SELECT api_tokens.id, token, created_at, expires_at, comment, users.username
            FROM api_tokens
            JOIN users ON api_tokens.user_id = users.id
            WHERE users.id = ?
            ORDER BY created_at DESC
        """, (user["id"],)).fetchall()
        requests = conn.execute("""
            SELECT * FROM token_requests
            WHERE user_id = ?
            ORDER BY requested_at DESC
        """, (user["id"],)).fetchall()

    conn.close()

    return templates.TemplateResponse("manage_api_tokens.html", {
        "request": request,
        "user": user,
        "users": users,
        "tokens": tokens,
        "requests": requests
    })


@router.post("/issue-token", include_in_schema=False)
def issue_token(
    user_id: int = Form(...),
    comment: str = Form(""),
    expires_at: str = Form(None),
    user=Depends(get_current_user)
):
    if not user or user["role"] != "admin":
        return RedirectResponse("/login", status_code=302)

    token = secrets.token_hex(32)

    conn = get_db_connection()
    conn.execute("""
        INSERT INTO api_tokens (user_id, token, comment, expires_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, token, comment, expires_at))

    conn.execute("""
        UPDATE token_requests
        SET status = 'approved'
        WHERE user_id = ? AND status = 'pending'
        ORDER BY requested_at DESC
        LIMIT 1
    """, (user_id,))
    conn.commit()
    conn.close()

    return RedirectResponse("/manage-api-tokens", status_code=302)


@router.get("/delete-token/{token_id}", include_in_schema=False)
def delete_token(token_id: int, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = get_db_connection()
    conn.execute("DELETE FROM api_tokens WHERE id = ?", (token_id,))
    conn.commit()
    conn.close()

    return RedirectResponse("/manage-api-tokens", status_code=302)


@router.get("/generate-api-token/{user_id}", include_in_schema=False)
def generate_api_token(user_id: int, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    token = secrets.token_hex(32)

    conn = get_db_connection()
    conn.execute("INSERT INTO api_tokens (user_id, token) VALUES (?, ?)", (user_id, token))
    conn.commit()
    conn.close()

    return RedirectResponse("/manage-users", status_code=302)


@router.post("/request-token", include_in_schema=False)
def request_token(
    request: Request,
    comment: str = Form(""),
    user=Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = get_db_connection()
    cursor = conn.cursor()

    existing = cursor.execute("""
        SELECT id FROM token_requests
        WHERE user_id = ? AND status = 'pending'
    """, (user["id"],)).fetchone()

    if existing:
        request.session["message"] = "Заявка уже была отправлена и ожидает рассмотрения."
        conn.close()
        return RedirectResponse("/manage-api-tokens", status_code=302)

    cursor.execute("""
        INSERT INTO token_requests (user_id, comment, status, requested_at)
        VALUES (?, ?, 'pending', ?)
    """, (user["id"], comment.strip(), datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

    request.session["message"] = "Заявка на токен успешно отправлена."
    return RedirectResponse("/manage-api-tokens", status_code=302)
