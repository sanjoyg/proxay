from fastapi import FastAPI, Request, Response

def create_test_server():
    """
    Creates a simple FastAPI application to act as a backend for tests.
    It uses middleware to echo back request information on every response.
    """
    app = FastAPI()

    @app.middleware("http")
    async def add_echo_headers(request: Request, call_next):
        # First, get the response from the actual route
        response = await call_next(request)

        # Now, add the echo headers to it
        response.headers["X-Original-Method"] = request.method
        response.headers["X-Original-Path"] = request.url.path

        # Also echo back the request headers into the response headers
        for key, value in request.headers.items():
            # Avoid overwriting critical response headers or causing issues.
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

    return app
