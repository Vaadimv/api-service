# app/routes/api_routes.py

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from app_core import get_db_connection, execute_test_query
from auth_utils import get_current_user
from dynamic_routes import register_dynamic_apis
from fastapi.templating import Jinja2Templates
import json

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/create-api", response_class=HTMLResponse, include_in_schema=False)
def create_api_form(request: Request, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name FROM db_connectors 
        WHERE active = 1 AND user_id = ?
    """, (user["id"],))
    connectors = cursor.fetchall()
    cursor.close()
    conn.close()

    return templates.TemplateResponse("create_api.html", {
        "request": request,
        "connectors": connectors
    })


@router.post("/create-api", include_in_schema=False)
def create_api(
    endpoint_name: str = Form(...),
    connector_id: int = Form(...),
    sql_query: str = Form(...),
    parameters: str = Form(""),
    user=Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Проверка: endpoint_name уже существует?
    existing_api = cursor.execute(
        "SELECT id FROM api_endpoints WHERE endpoint_name = ?",
        (endpoint_name,)
    ).fetchone()

    if existing_api:
        cursor.close()
        conn.close()
        return HTMLResponse(
            content="API с таким именем уже существует. Пожалуйста, выберите другое имя.",
            status_code=400
        )

    # Проверяем, что коннектор принадлежит текущему пользователю
    connector = cursor.execute(
        "SELECT id FROM db_connectors WHERE id = ? AND user_id = ?",
        (connector_id, user["id"])
    ).fetchone()

    if not connector:
        cursor.close()
        conn.close()
        return HTMLResponse(content="Коннектор не найден или не принадлежит вам", status_code=403)

    # Вставка API
    cursor.execute('''
        INSERT INTO api_endpoints (endpoint_name, connector_id, sql_query, parameters, user_id, active)
        VALUES (?, ?, ?, ?, ?, 1)
    ''', (endpoint_name, connector_id, sql_query, parameters, user["id"]))

    conn.commit()
    cursor.close()
    conn.close()

    register_dynamic_apis()

    return RedirectResponse(url="/manage-apis", status_code=303)

@router.get("/manage-apis", response_class=HTMLResponse, include_in_schema=False)
def manage_apis(request: Request, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = get_db_connection()
    cursor = conn.cursor()

    if user["role"] == "admin":
        cursor.execute('''
            SELECT api_endpoints.id, api_endpoints.endpoint_name, api_endpoints.sql_query,
                   api_endpoints.active, db_connectors.name as connector_name, db_connectors.db_type
            FROM api_endpoints
            JOIN db_connectors ON api_endpoints.connector_id = db_connectors.id
        ''')
    else:
        cursor.execute('''
            SELECT api_endpoints.id, api_endpoints.endpoint_name, api_endpoints.sql_query,
                   api_endpoints.active, db_connectors.name as connector_name, db_connectors.db_type
            FROM api_endpoints
            JOIN db_connectors ON api_endpoints.connector_id = db_connectors.id
            WHERE api_endpoints.user_id = ?
        ''', (user["id"],))

    apis = cursor.fetchall()
    cursor.close()
    conn.close()

    return templates.TemplateResponse("manage_apis.html", {
        "request": request,
        "apis": apis
    })

@router.get("/edit-api/{api_id}", response_class=HTMLResponse, include_in_schema=False)
def edit_api_form(api_id: int, request: Request, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = get_db_connection()
    cursor = conn.cursor()

    api = cursor.execute(
        "SELECT * FROM api_endpoints WHERE id = ? AND user_id = ?",
        (api_id, user["id"])
    ).fetchone()

    if not api:
        cursor.close()
        conn.close()
        return HTMLResponse("API не найден или доступ запрещён", status_code=403)

    connectors = cursor.execute(
        "SELECT * FROM db_connectors WHERE active = 1 AND user_id = ?",
        (user["id"],)
    ).fetchall()

    cursor.close()
    conn.close()

    return templates.TemplateResponse("edit_api.html", {
        "request": request,
        "api": api,
        "connectors": connectors
    })

@router.post("/edit-api/{api_id}", include_in_schema=False)
def update_api(
    api_id: int,
    endpoint_name: str = Form(...),
    connector_id: int = Form(...),
    sql_query: str = Form(...),
    parameters: str = Form(""),
    user=Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = get_db_connection()
    cursor = conn.cursor()

    api = cursor.execute(
        "SELECT id FROM api_endpoints WHERE id = ? AND user_id = ?",
        (api_id, user["id"])
    ).fetchone()

    if not api:
        cursor.close()
        conn.close()
        return HTMLResponse("API не найден или доступ запрещён", status_code=403)

    conflict = cursor.execute(
        "SELECT id FROM api_endpoints WHERE endpoint_name = ? AND id != ?",
        (endpoint_name, api_id)
    ).fetchone()

    if conflict:
        cursor.close()
        conn.close()
        return HTMLResponse("API с таким именем уже существует", status_code=400)

    cursor.execute('''
        UPDATE api_endpoints
        SET endpoint_name = ?, connector_id = ?, sql_query = ?, parameters = ?
        WHERE id = ? AND user_id = ?
    ''', (endpoint_name, connector_id, sql_query, parameters, api_id, user["id"]))

    conn.commit()
    cursor.close()
    conn.close()

    register_dynamic_apis()
    return RedirectResponse("/manage-apis", status_code=303)


@router.post("/register-api/{api_id}", include_in_schema=False)
def register_api(api_id: int, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = get_db_connection()
    cursor = conn.cursor()
    row = cursor.execute(
        "SELECT endpoint_name FROM api_endpoints WHERE id = ? AND user_id = ? AND active = 1",
        (api_id, user["id"])
    ).fetchone()

    cursor.close()
    conn.close()

    if not row:
        return HTMLResponse("API не найден или доступ запрещён", status_code=403)

    register_dynamic_apis()
    return RedirectResponse("/manage-apis", status_code=303)


@router.get("/toggle-api/{api_id}", include_in_schema=False)
def toggle_api(api_id: int, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = get_db_connection()
    cursor = conn.cursor()
    api = cursor.execute(
        "SELECT active FROM api_endpoints WHERE id = ? AND user_id = ?",
        (api_id, user["id"])
    ).fetchone()

    if not api:
        cursor.close()
        conn.close()
        return HTMLResponse("API не найден или доступ запрещён", status_code=403)

    new_status = 0 if api["active"] else 1
    cursor.execute(
        "UPDATE api_endpoints SET active = ? WHERE id = ?", (new_status, api_id)
    )

    conn.commit()
    cursor.close()
    conn.close()

    return RedirectResponse("/manage-apis", status_code=303)


@router.get("/delete-api/{api_id}", include_in_schema=False)
def delete_api(api_id: int, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = get_db_connection()
    cursor = conn.cursor()
    api = cursor.execute(
        "SELECT id FROM api_endpoints WHERE id = ? AND user_id = ?",
        (api_id, user["id"])
    ).fetchone()

    if not api:
        cursor.close()
        conn.close()
        return HTMLResponse("API не найден или доступ запрещён", status_code=403)

    cursor.execute("DELETE FROM api_endpoints WHERE id = ?", (api_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return RedirectResponse("/manage-apis", status_code=303)


@router.get("/test-api/{api_id}", response_class=HTMLResponse, include_in_schema=False)
async def test_api_form(request: Request, api_id: int, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT endpoint_name, sql_query, parameters, db_connectors.*, api_endpoints.user_id
        FROM api_endpoints
        JOIN db_connectors ON api_endpoints.connector_id = db_connectors.id
        WHERE api_endpoints.id = ?
    ''', (api_id,))
    data = cursor.fetchone()

    if not data or data["user_id"] != user["id"]:
        cursor.close()
        conn.close()
        return HTMLResponse("API не найден или доступ запрещён", status_code=403)

    token_row = conn.execute(
        "SELECT token FROM api_tokens WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user["id"],)
    ).fetchone()
    token = token_row["token"] if token_row else None

    cursor.close()
    conn.close()

    endpoint_name = data["endpoint_name"]
    base_url = f"/api/{endpoint_name}"
    try:
        parameters = json.loads(data["parameters"]) if data["parameters"] else []
    except Exception:
        parameters = []

    query_params = dict(request.query_params)
    rows = []
    error = None

    if all(param in query_params for param in parameters):
        try:
            rows = execute_test_query(
                db_type=data["db_type"],
                host=data["host"],
                port=data["port"],
                db_name=data["db_name"],
                username=data["username"],
                password=data["password"],
                sql_query=data["sql_query"],
                query_params=query_params
            )
        except Exception as e:
            error = str(e)

    return templates.TemplateResponse("test_api.html", {
        "request": request,
        "endpoint_name": endpoint_name,
        "base_url": base_url,
        "parameters": parameters,
        "result_json": rows,
        "error": error,
        "token": token
    })
