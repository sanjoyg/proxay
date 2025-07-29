from fastapi import FastAPI, Request, Response

def create_test_server():
    """
    Creates a simple FastAPI application to act as a backend for tests.
    It uses middleware to echo back request information on every response.
    """
    app = FastAPI()

    @app.middleware("http")
    async def add_echo_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Original-Method"] = request.method
        response.headers["X-Original-Path"] = request.url.path
        for key, value in request.headers.items():
            if key.lower() not in ["host", "content-length", "content-type"]:
                response.headers[key] = value
        return response

    @app.get("/hello")
    async def get_hello():
        return Response("world")

    @app.post("/echo")
    async def post_echo(request: Request):
        body = await request.body()
        return Response(content=body, headers={"Content-Type": request.headers.get("content-type")})

    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def catch_all(request: Request):
        """
        A catch-all route to handle any requests not matched by specific routes.
        This is needed for tests that use arbitrary paths.
        """
        body = await request.body()
        return Response(
            content=body,
            status_code=200,
        )

    return app
