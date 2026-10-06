"""One error shape for the whole API: {"error": {"code", "message", "details"}}."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("liv")


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, details=None):
        super().__init__(message)
        self.message = message
        self.code = code or self.code
        self.details = details


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


def _friendly(e: dict) -> str:
    """Plain-language validation messages instead of Pydantic's technical ones."""
    kind, ctx = e.get("type", ""), e.get("ctx") or {}
    if kind == "missing":
        return "This field is required."
    if kind == "greater_than_equal":
        return f"Must be {ctx['ge']} or more."
    if kind == "less_than_equal":
        return f"Must be {ctx['le']} or less."
    if kind == "greater_than":
        return f"Must be more than {ctx['gt']}."
    if kind == "less_than":
        return f"Must be less than {ctx['lt']}."
    if kind == "string_too_short":
        return f"Must be at least {ctx['min_length']} characters."
    if kind == "string_too_long":
        return f"Must be at most {ctx['max_length']} characters."
    if kind in ("int_parsing", "int_from_float", "float_parsing"):
        return "Enter a valid number."
    if kind == "value_error":
        return str(e["msg"]).removeprefix("Value error, ")
    return e["msg"]


def _body(code: str, message: str, details=None) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(_body(exc.code, exc.message, exc.details), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(p) for p in e["loc"][1:]) or str(e["loc"][0]), "message": _friendly(e)}
            for e in exc.errors()
        ]
        return JSONResponse(
            _body("validation_error", "Some of the information you entered isn't valid.", details),
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        message = "That resource doesn't exist." if exc.status_code == 404 else str(exc.detail)
        return JSONResponse(_body("http_error", message), status_code=exc.status_code)

    @app.exception_handler(SQLAlchemyError)
    async def _db(_: Request, exc: SQLAlchemyError):
        log.exception("Database error", exc_info=exc)
        return JSONResponse(
            _body("database_error", "We couldn't save or load your data. Try again in a moment."),
            status_code=500,
        )

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception):
        log.exception("Unhandled error", exc_info=exc)
        return JSONResponse(
            _body("internal_error", "Something went wrong on our side. Try again in a moment."),
            status_code=500,
        )
