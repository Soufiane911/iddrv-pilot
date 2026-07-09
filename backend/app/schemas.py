"""Stable API contracts for the v1 service skeleton.

Business endpoints are intentionally not implemented in G1. These models keep
the public wire format explicit for the frontend and future route work.
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApiError(BaseModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ApiError


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    version: str
    database: Literal["ok", "unavailable"]


class Site(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    timezone: str = "UTC"


class ProductionLine(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    site_id: int
    name: str


class Machine(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    site_id: int | None = None
    line_id: int | None = None
    name: str
    status: Literal["running", "warning", "stopped", "offline"] | None = None


class MachineStatus(BaseModel):
    machine_id: int
    status: Literal["running", "warning", "stopped", "offline"]
    as_of: datetime
    freshness_s: float | None = None


class CursorPage[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None


class TimelinePoint(BaseModel):
    timestamp: datetime
    value: float | None = None
    status: str | None = None
