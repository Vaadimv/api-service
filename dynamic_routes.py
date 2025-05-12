from tool_decorator import tool
import json
import inspect
from typing import Callable
from fastapi import Request, Depends, Query, Body
from fastapi.responses import JSONResponse
from pydantic import create_model

from app_core import app, get_db_connection, execute_test_query


def register_dynamic_apis():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT endpoint_name, connector_id, sql_query, parameters FROM api_endpoints WHERE active = 1")
    apis = cursor.fetchall()
    cursor.close()
    conn.close()

    def build_query_params_model(params: list) -> Callable:
        def dependency(**kwargs):
            return kwargs

        dependency.__signature__ = inspect.signature(
            lambda **kwargs: None
        ).replace(
            parameters=[
                inspect.Parameter(
                    name=param,
                    kind=inspect.Parameter.KEYWORD_ONLY,
                    default=Query(...),
                    annotation=str,
                )
                for param in params
            ]
        )
        return Depends(dependency)

    def make_endpoint(endpoint_name, connector_id, sql_query, parameters):
        try:
            param_list = json.loads(parameters) if parameters else []
        except Exception:
            param_list = []

        InputModel = create_model(
            f"{endpoint_name}_PostModel",
            **{param: (str, ...) for param in param_list}
        )

        @tool(name=f"{endpoint_name}_post", description=f"[POST] Динамический API для {endpoint_name}")
        async def post_endpoint(
            data: InputModel = Body(...),
            request: Request = None
        ):
            return await process_dynamic_query(request, connector_id, sql_query, data.dict())

        @tool(name=f"{endpoint_name}_get", description=f"[GET] Динамический API для {endpoint_name}")
        async def get_endpoint(
            query_data=build_query_params_model(param_list),
            request: Request = None
        ):
            return await process_dynamic_query(request, connector_id, sql_query, query_data)

        return post_endpoint, get_endpoint

    async def process_dynamic_query(request: Request, connector_id, sql_query, query_params):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(content={"error": "Missing or invalid Authorization header"}, status_code=401)

        token = auth_header.split(" ")[1]

        conn = get_db_connection()
        token_record = conn.execute("SELECT * FROM api_tokens WHERE token = ?", (token,)).fetchone()
        if not token_record:
            conn.close()
            return JSONResponse(content={"error": "Invalid or expired token"}, status_code=401)

        cur = conn.cursor()
        cur.execute("SELECT * FROM db_connectors WHERE id = ?", (connector_id,))
        connector = cur.fetchone()
        cur.close()
        conn.close()

        if not connector:
            return JSONResponse(content={"error": "Коннектор не найден"}, status_code=404)

        db_type, host, port, db_name, username, password = connector[2:8]

        try:
            rows = execute_test_query(
                db_type, host, port, db_name, username, password,
                sql_query, query_params
            )
            return JSONResponse(content={"data": rows})
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)

    for endpoint_name, connector_id, sql_query, parameters in apis:
        route_path = f"/api/{endpoint_name}"
        print(f"Регистрирую динамический маршрут: {route_path}")

        post_ep, get_ep = make_endpoint(endpoint_name, connector_id, sql_query, parameters)

        app.add_api_route(
            route_path,
            post_ep,
            methods=["POST"],
            tags=["User API"],
            operation_id=f"{endpoint_name}_post_operation",
            summary=f"[POST] API: {endpoint_name}",
            description=f"Ожидаемые параметры:\n{parameters}"
        )

        app.add_api_route(
            route_path,
            get_ep,
            methods=["GET"],
            tags=["User API"],
            operation_id=f"{endpoint_name}_get_operation",
            summary=f"[GET] API: {endpoint_name}",
            description=f"Ожидаемые параметры:\n{parameters}"
        )
