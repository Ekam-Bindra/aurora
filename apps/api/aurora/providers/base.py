"""AI provider abstraction (Architecture §8)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentResponse:
    answer: str
    tools_used: List[Dict[str, Any]] = field(default_factory=list)
    citations: List[Dict[str, str]] = field(default_factory=list)
    provider: str = "mock"
    model: str = "aurora-mock-1"
    tokens_input: int = 0
    tokens_output: int = 0


class AIProvider(ABC):
    @abstractmethod
    def complete(
        self,
        message: str,
        *,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        ...
