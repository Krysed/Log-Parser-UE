from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse

MAX_UPLOAD_SIZE = 10 * 1024 * 1024

class MaxSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")

        if content_length and int(content_length) > MAX_UPLOAD_SIZE:
            return PlainTextResponse(
                f"Request payload too large - 10MB limit.",
                status_code=413
            )

        return await call_next(request)
