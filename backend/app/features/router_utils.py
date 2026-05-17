from __future__ import annotations

from .errors import (
    BadRequestError,
    ConflictError,
    DomainError,
    ForbiddenError,
    InsufficientPointsError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorizedError,
)

ERROR_STATUS: dict[type[DomainError], int] = {
    BadRequestError: 400,
    UnauthorizedError: 401,
    InsufficientPointsError: 402,
    ForbiddenError: 403,
    NotFoundError: 404,
    ConflictError: 409,
    ServiceUnavailableError: 503,
}


def resolve_status(exc: DomainError) -> int:
    for exc_class, status in ERROR_STATUS.items():
        if isinstance(exc, exc_class):
            return status
    return 500
