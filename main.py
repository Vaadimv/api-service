import json
import sqlite3
from datetime import datetime
from fastapi import (
    Depends, FastAPI, Form, HTTPException, Path, Query, Request
)
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app_core import app, get_db_connection, execute_test_query
from dynamic_routes import register_dynamic_apis
import secrets
from auth_utils import (
    hash_password,
    verify_password,
    create_token,
    get_current_user
)
from app.routes.auth_routes import router as auth_router
app.include_router(auth_router)
from app.routes.user_management import router as user_router
app.include_router(user_router)
from app.routes.connector_routes import router as connector_router
app.include_router(connector_router)
from app.routes.api_routes import router as api_router

app.include_router(api_router)
app.add_middleware(SessionMiddleware, secret_key="6fG7@dk93L!vd09a")  # желательно длиннее и безопаснее
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.middleware("http")
async def refresh_token_middleware(request: Request, call_next):
    response: Response = await call_next(request)

    # Если в auth_utils был установлен новый токен — добавим его в cookie
    new_token = getattr(request.state, "refresh_token", None)
    if new_token:
        response.set_cookie("access_token", new_token, httponly=True)

    return response

@app.get("/reset-password/{user_id}", response_class=HTMLResponse, include_in_schema=False)
def reset_password_form(user_id: int, request: Request):
    return templates.TemplateResponse("reset-password.html", {"request": request, "user_id": user_id})

@app.post("/reset-password/{user_id}", include_in_schema=False)
def reset_password(user_id: int, password: str = Form(...)):
    hashed_password = hash_password(password)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (hashed_password, user_id)
    )
    conn.commit()
    conn.close()
    return RedirectResponse("/login", status_code=302)

#Zschita glavnoi
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home(request: Request, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = get_db_connection()
    cursor = conn.cursor()

    if user["role"] == "admin":
        cursor.execute('''
            SELECT api_endpoints.id, api_endpoints.endpoint_name, 
                   db_connectors.name as connector_name, db_connectors.db_type, 
                   api_endpoints.active
            FROM api_endpoints
            JOIN db_connectors ON api_endpoints.connector_id = db_connectors.id
            ORDER BY api_endpoints.id DESC
            LIMIT 10
        ''')
    else:
        cursor.execute('''
            SELECT api_endpoints.id, api_endpoints.endpoint_name, 
                   db_connectors.name as connector_name, db_connectors.db_type, 
                   api_endpoints.active
            FROM api_endpoints
            JOIN db_connectors ON api_endpoints.connector_id = db_connectors.id
            WHERE api_endpoints.user_id = ?
            ORDER BY api_endpoints.id DESC
            LIMIT 10
        ''', (user["id"],))

    apis = cursor.fetchall()
    cursor.close()
    conn.close()

    return templates.TemplateResponse("home.html", {
        "request": request,
        "user": user,
        "apis": apis
    })


# --- GET: форма сброса пароля ---
@app.get("/reset-password/{user_id}", response_class=HTMLResponse, include_in_schema=False)
def reset_password_form(user_id: int, request: Request):
    conn = get_db_connection()
    user = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    if not user:
        return HTMLResponse("Пользователь не найден", status_code=404)

    return templates.TemplateResponse("reset-password.html", {
        "request": request,
        "user_id": user_id,
        "username": user["username"]
    })

# --- POST: изменение пароля ---
@app.post("/reset-password", include_in_schema=False)
def reset_password(user_id: int = Form(...), new_password: str = Form(...)):
    conn = get_db_connection()

    # Проверка, существует ли пользователь
    user = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return HTMLResponse("Пользователь не найден", status_code=404)

    hashed = hash_password(new_password)
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hashed, user_id))
    conn.commit()
    conn.close()

    return RedirectResponse("/login", status_code=302)

#Testirivanie SQL-podklyucheniya
@app.post("/test-sql", include_in_schema=False)
def test_sql(request: Request, connector_id: int = Form(...), sql_query: str = Form(...)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM db_connectors WHERE id = ?", (connector_id,))
    connector = cursor.fetchone()
    cursor.close()
    conn.close()

    if not connector:
        message = "Коннектор не найден"
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JSONResponse(status_code=404, content={"error": message})
        return HTMLResponse(content=message, status_code=404)

    db_type, host, port, db_name, username, password = connector[2:8]

    try:
        rows = execute_test_query(db_type, host, port, db_name, username, password, sql_query)
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JSONResponse(content={"rows": rows})
        return templates.TemplateResponse("test_sql.html", {"request": request, "rows": rows})
    except Exception as e:
        error_message = str(e)
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JSONResponse(status_code=500, content={"error": error_message})
        return templates.TemplateResponse("test_sql.html", {
            "request": request,
            "error": error_message
        })


#Avtorizciya v Swagger
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Oracle API Service",
        version="1.0.0",
        description="Документация API",
        routes=app.routes,
    )

    # Обеспечим наличие ключа components
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}

    if "securitySchemes" not in openapi_schema["components"]:
        openapi_schema["components"]["securitySchemes"] = {}

    openapi_schema["components"]["securitySchemes"]["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT"
    }

    for path in openapi_schema["paths"].values():
        for operation in path.values():
            operation["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

@app.on_event("startup")
async def startup_event():
    register_dynamic_apis()

