"""Exception handlers: domain errors -> clean JSON, never raw stack traces."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.core.exceptions import ApiError

logger = logging.getLogger("gridsight.api")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        logger.info("%s %s -> %s: %s", request.method, request.url.path, exc.status_code, exc.message)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
