"""Vercel serverless entry point.

Vercel invokes this function at `/api/index` for every request (see the rewrite
in `vercel.json`). This ASGI wrapper restores the ORIGINAL request path before
FastAPI routes the request, using, in order:

1. the `__path` query parameter added by the rewrite (`/api/index?__path=/$1`);
2. Vercel's rewrite headers (`x-now-route-matches` capture group, or a forwarded URI).

Only the wrapper is exposed at module level: Vercel's runtime looks for an ASGI
app in this module, and exposing the FastAPI instance itself would bypass the
wrapper. Requests without rewrite information pass through unchanged.
"""

from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit

import app.main as _main

PATH_PARAM = "__path"
FUNCTION_PATH = "/api/index"
_FORWARDED_URI_HEADERS = (b"x-forwarded-uri", b"x-original-url", b"x-original-uri", b"x-rewrite-url")


def _original_path(scope) -> tuple[str | None, list[tuple[str, str]], str]:
    """Return (original path or None, remaining query params, source used)."""
    params = parse_qsl(scope.get("query_string", b"").decode("latin-1"), keep_blank_values=True)
    for key, value in params:
        if key == PATH_PARAM:
            return value, [(k, v) for k, v in params if k != PATH_PARAM], "query"

    headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
    # Vercel passes rewrite capture groups as e.g. "1=api%2Fhealth".
    matches = headers.get("x-now-route-matches")
    if matches:
        captured = dict(parse_qsl(matches, keep_blank_values=True)).get("1")
        if captured is not None:
            return unquote(captured), params, "x-now-route-matches"
    for name in _FORWARDED_URI_HEADERS:
        value = headers.get(name.decode())
        if value:
            parts = urlsplit(value)
            if parts.path and parts.path != FUNCTION_PATH:
                extra = parse_qsl(parts.query, keep_blank_values=True)
                return parts.path, params + extra, name.decode()
    return None, params, "none"


class RestoreOriginalPath:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            original, rest, source = _original_path(scope)
            routing = {"wrapper": True, "source": source, "received_path": scope.get("path")}
            if original is not None:
                path = "/" + original.lstrip("/")
                scope = {
                    **scope,
                    "path": path,
                    "raw_path": quote(path).encode("latin-1"),
                    "query_string": urlencode(rest).encode("latin-1"),
                    # Starlette strips root_path before routing; a runtime-set value would break matching.
                    "root_path": "",
                }
            scope = {**scope, "state": {**scope.get("state", {}), "vercel_routing": routing}}
        await self.inner(scope, receive, send)


app = RestoreOriginalPath(_main.app)
