"""HTTP session state model for serialization."""

from __future__ import annotations

import httpx
from pydantic import BaseModel


class SessionModel(BaseModel):
    """Serializable HTTP session state for httpx Client."""

    cookies: dict[str, str] = {}
    headers: dict[str, str] = {}
    auth_header: str | None = None  # Store the pre-computed "Basic <base64>" header

    @classmethod
    def from_client(cls, client: httpx.Client) -> SessionModel:
        """Extract session state from httpx Client."""
        auth_header = None
        if client.auth is not None and isinstance(client.auth, httpx.BasicAuth):
            auth_header = client.auth._auth_header

        return cls(
            cookies=dict(client.cookies),
            headers=dict(client.headers),
            auth_header=auth_header,
        )

    def apply_to_client(self, client: httpx.Client) -> None:
        """Apply session state to httpx Client."""
        client.cookies.update(self.cookies)
        client.headers.update(self.headers)
        if self.auth_header is not None:
            # Set Authorization header directly instead of using auth object
            client.headers["Authorization"] = self.auth_header
