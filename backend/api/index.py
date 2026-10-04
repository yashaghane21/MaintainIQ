"""Vercel serverless entry point.

`vercel.json` rewrites every request to this function as
`/api/index?__path=/<original path>`, because the function itself is invoked
at `/api/index`. This thin ASGI wrapper restores the original path (and
strips the helper parameter) before FastAPI routes the request. Requests
without `__path` (e.g. local `uvicorn api.index:app`) pass through unchanged.
"""

from urllib.parse import parse_qsl, quote, urlencode

from app.main import app as fastapi_app

PATH_PARAM = "__path"


class RestoreOriginalPath:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            params = parse_qsl(scope.get("query_string", b"").decode("latin-1"), keep_blank_values=True)
            original = [v for k, v in params if k == PATH_PARAM]
            if original:
                path = "/" + original[0].lstrip("/")
                rest = [(k, v) for k, v in params if k != PATH_PARAM]
                scope = {
                    **scope,
                    "path": path,
                    "raw_path": quote(path).encode("latin-1"),
                    "query_string": urlencode(rest).encode("latin-1"),
                    # Starlette strips root_path from path before routing; a runtime-set
                    # root_path (e.g. the function path) would otherwise break matching.
                    "root_path": "",
                }
        await self.inner(scope, receive, send)


app = RestoreOriginalPath(fastapi_app)
