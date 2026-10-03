from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ConnectorError(RuntimeError):
    """Base connector error safe to surface to an agent."""


class AuthenticationError(ConnectorError):
    """OAuth token acquisition or authentication failed."""


class RateLimitError(ConnectorError):
    """Zoho rate limit was still exceeded after bounded retries."""


@dataclass(slots=True)
class ZohoAPIError(ConnectorError):
    status_code: int
    message: str
    code: int | str | None = None
    details: Any = None

    def __str__(self) -> str:
        suffix = f" (code={self.code})" if self.code is not None else ""
        return f"Zoho API error {self.status_code}{suffix}: {self.message}"
