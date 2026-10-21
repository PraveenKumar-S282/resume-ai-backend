"""Consistent error format: {"error": {"code", "message", "details": [{"field", "issue"}]}}"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("app")


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: list[dict] | None = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []


def _body(code: str, message: str, details: list[dict] | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or []}}


_STATUS_CODES = {400: "BAD_REQUEST", 401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 409: "CONFLICT"}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content=_body(exc.code, exc.message, exc.details))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        code = _STATUS_CODES.get(exc.status_code, "ERROR")
        return JSONResponse(status_code=exc.status_code, content=_body(code, str(exc.detail)), headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        details = []
        for err in exc.errors():
            loc = [str(p) for p in err["loc"] if p not in ("body", "query", "path")]
            details.append({"field": ".".join(loc), "issue": err["msg"].removeprefix("Value error, ")})
        return JSONResponse(status_code=422, content=_body("VALIDATION_ERROR", "Some fields are invalid.", details))

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limited(_: Request, exc: RateLimitExceeded):
        return JSONResponse(status_code=429, content=_body("RATE_LIMITED", "Too many requests. Please wait a moment and try again."))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error", exc_info=exc)
        return JSONResponse(status_code=500, content=_body("INTERNAL_ERROR", "Something went wrong on our side. Please try again."))
