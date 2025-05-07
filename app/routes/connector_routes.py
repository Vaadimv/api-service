# app/routes/connector_routes.py

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app_core import get_db_connection
from auth_utils import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/manage-connectors", response_class=HTMLResponse, include_in_schema=False)
def manage_connectors(request: Request, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = get_db_connection()
    if user["role"] == "admin":
        connectors = conn.execute("SELECT * FROM db_connectors").fetchall()
    else:
        connectors = conn.execute(
            "SELECT * FROM db_connectors WHERE user_id = ?",
            (user["id"],)
        ).fetchall()
    conn.close()

    return templates.TemplateResponse("manage_connectors.html", {
        "request": request,
        "connectors": connectors
    })


@router.get("/create-connector", response_class=HTMLResponse, include_in_schema=False)
def create_connector_form(request: Request, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    return templates.TemplateResponse("connector_form.html", {
        "request": request,
        "mode": "create",
        "action": "/create-connector",
        "connector": None
    })


@router.post("/create-connector", include_in_schema=False)
def create_connector(
    name: str = Form(...),
    db_type: str = Form(...),
    host: str = Form(...),
    port: int = Form(...),
    db_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    user=Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = get_db_connection()
    conn.execute('''
        INSERT INTO db_connectors (name, db_type, host, port, db_name, username, password, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, db_type, host, port, db_name, username, password, user["id"]))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/manage-connectors", status_code=303)


@router.get("/edit-connector/{connector_id}", response_class=HTMLResponse, include_in_schema=False)
def edit_connector_form(request: Request, connector_id: int, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = get_db_connection()
    connector = conn.execute(
        "SELECT * FROM db_connectors WHERE id = ? AND user_id = ?", (connector_id, user["id"])
    ).fetchone()
    conn.close()

    if not connector:
        return HTMLResponse(content="Коннектор не найден или доступ запрещён", status_code=403)

    return templates.TemplateResponse("connector_form.html", {
        "request": request,
        "mode": "edit",
        "action": f"/edit-connector/{connector_id}",
        "connector": connector
    })


@router.post("/edit-connector/{connector_id}", include_in_schema=False)
def update_connector(
    connector_id: int,
    name: str = Form(...),
    db_type: str = Form(...),
    host: str = Form(...),
    port: int = Form(...),
    db_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(None),
    active: int = Form(0),
    user=Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = get_db_connection()
    cursor = conn.cursor()

    existing = cursor.execute(
        "SELECT * FROM db_connectors WHERE id = ? AND user_id = ?", (connector_id, user["id"])
    ).fetchone()

    if not existing:
        cursor.close()
        conn.close()
        return HTMLResponse(content="Коннектор не найден или доступ запрещён", status_code=403)

    new_password = password if password else existing["password"]

    cursor.execute('''
        UPDATE db_connectors
        SET name = ?, db_type = ?, host = ?, port = ?, db_name = ?, username = ?, password = ?, active = ?
        WHERE id = ?
    ''', (name, db_type, host, port, db_name, username, new_password, active, connector_id))

    conn.commit()
    cursor.close()
    conn.close()

    return RedirectResponse("/manage-connectors", status_code=303)


@router.get("/delete-connector/{connector_id}", include_in_schema=False)
def delete_connector(connector_id: int, user=Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)

    conn = get_db_connection()
    cursor = conn.cursor()
    connector = cursor.execute(
        "SELECT id FROM db_connectors WHERE id = ? AND user_id = ?", (connector_id, user["id"])
    ).fetchone()

    if not connector:
        cursor.close()
        conn.close()
        return HTMLResponse(content="Коннектор не найден или доступ запрещён", status_code=403)

    cursor.execute("DELETE FROM db_connectors WHERE id = ?", (connector_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return RedirectResponse("/manage-connectors", status_code=303)


@router.get("/test-connector/{connector_id}", response_class=HTMLResponse, include_in_schema=False)
def test_connector(request: Request, connector_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM db_connectors WHERE id = ?", (connector_id,))
    connector = cursor.fetchone()
    cursor.close()
    conn.close()

    if not connector:
        return HTMLResponse(content="Коннектор не найден", status_code=404)

    try:
        db_type, host, port, db_name, username, password = connector[2:8]
        test_connection(db_type, host, port, db_name, username, password)
        result = "Подключение успешно!"
    except Exception as e:
        result = f"Ошибка подключения: {str(e)}"

    return templates.TemplateResponse("test_connector.html", {"request": request, "result": result})


# Вспомогательная функция — не регистрируется как маршрут
def test_connection(db_type, host, port, db_name, username, password):
    if db_type == "oracle":
        import oracledb
        dsn = f"{host}:{port}/{db_name}"
        conn = oracledb.connect(user=username, password=password, dsn=dsn)
    elif db_type == "oracle_legacy":
        import cx_Oracle
        dsn = cx_Oracle.makedsn(host, port, db_name)
        conn = cx_Oracle.connect(user=username, password=password, dsn=dsn)
    elif db_type == "postgresql":
        import psycopg2
        conn = psycopg2.connect(host=host, port=port, dbname=db_name, user=username, password=password)
    elif db_type == "clickhouse":
        import clickhouse_connect
        client = clickhouse_connect.get_client(host=host, port=port, username=username, password=password)
        client.query('SELECT 1')
        conn = None
    else:
        raise Exception("Неподдерживаемый тип БД")

    if conn:
        conn.close()
