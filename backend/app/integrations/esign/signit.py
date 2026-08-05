"""Signit adapter skeleton — no live API calls."""
from __future__ import annotations

from typing import Any

from .base import ESignProvider


class SignitESignProvider(ESignProvider):
    """
    TODO: Map Signit REST endpoints when credentials are available.
    Configure: SIGNIT_API_KEY, SIGNIT_BASE_URL, SIGNIT_WEBHOOK_SECRET
    """

    name = "signit"

    def _todo(self) -> None:
        raise NotImplementedError("Signit integration not configured for this environment")

    def create_request(self, *, contract_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
        self._todo()

    def send_request(self, *, external_id: str | None, metadata: dict[str, Any]) -> dict[str, Any]:
        self._todo()

    def get_status(self, *, external_id: str | None, metadata: dict[str, Any]) -> dict[str, Any]:
        self._todo()

    def get_signer_link(self, *, token: str, metadata: dict[str, Any]) -> str:
        self._todo()

    def record_open(self, *, metadata: dict[str, Any]) -> None:
        self._todo()

    def sign(self, *, metadata: dict[str, Any]) -> dict[str, Any]:
        self._todo()

    def decline(self, *, metadata: dict[str, Any]) -> dict[str, Any]:
        self._todo()

    def download_signed_document(self, *, metadata: dict[str, Any]) -> bytes:
        self._todo()

    def generate_certificate(self, *, metadata: dict[str, Any]) -> bytes:
        self._todo()
