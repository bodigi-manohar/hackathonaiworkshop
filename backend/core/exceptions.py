"""Domain exceptions, converted to HTTP JSON by core.exception_handlers."""
from __future__ import annotations


class ApiError(Exception):
    status_code: int = 500

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(ApiError):
    status_code = 404


class ConflictError(ApiError):
    status_code = 409


class RunError(ApiError):
    status_code = 500
