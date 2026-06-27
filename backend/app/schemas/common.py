"""
Unified response schemas for the 预知梦基金 API.

All endpoints return responses wrapped in these generic models
so that every response has the shape: {code, message, data}.
"""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

# Generic type variable for the `data` field
T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Standard API response envelope.

    - code=0 means success; non-zero values indicate errors.
    - message provides a human-readable description.
    - data carries the actual payload (None on error).
    """

    code: int = Field(default=0, description="Status code — 0 for success")
    message: str = Field(default="ok", description="Human-readable message")
    data: T | None = Field(
        default=None, description="Response payload; None on error"
    )


class PaginatedData(BaseModel, Generic[T]):
    """Inner payload for paginated responses."""

    items: list[T] = Field(default_factory=list, description="Current page items")
    total: int = Field(default=0, description="Total number of items across all pages")
    page: int = Field(default=1, description="Current page number (1-indexed)")
    page_size: int = Field(default=20, description="Number of items per page")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response envelope.

    Wraps a PaginatedData[T] inside the standard {code, message, data} shape.
    """

    code: int = Field(default=0)
    message: str = Field(default="ok")
    data: PaginatedData[T] = Field(
        default_factory=lambda: PaginatedData[T]()
    )


class ErrorResponse(BaseModel):
    """Error-only response — data is always None."""

    code: int = Field(default=-1, description="Non-zero error code")
    message: str = Field(default="error", description="Error description")
    data: None = Field(default=None, description="Always None for error responses")


class PaginationParams(BaseModel):
    """Query-string pagination parameters accepted by list endpoints."""

    page: int = Field(
        default=1,
        ge=1,
        description="Page number (1-indexed, minimum 1)",
    )
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Items per page (1-100, default 20)",
    )

    # No validators are needed for simple ge/le; they are enforced by Pydantic.
