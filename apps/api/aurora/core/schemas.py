"""Typed response envelopes.

Routes historically returned plain ``{"data": ..., "meta": ...}`` dicts, which
makes the OpenAPI spec useless to the generated web client. Declaring
``response_model=Envelope[X]`` documents the contract without changing wire
shapes. Payload models use ``extra="allow"`` so any field a serializer adds
beyond the declared core passes through instead of being stripped — declared
fields are the typed contract, extras are forward-compatibility.
"""

from __future__ import annotations

from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class Meta(BaseModel):
    model_config = ConfigDict(extra="allow")

    request_id: Optional[str] = None


class Envelope(BaseModel, Generic[T]):
    data: T
    meta: Meta
