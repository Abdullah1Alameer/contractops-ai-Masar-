"""Hackathon simulated e-sign provider — no external APIs."""
from __future__ import annotations

from typing import Any

from ...config import REVIEW_BASE_URL
from .base import ESignProvider


class SimulatedESignProvider(ESignProvider):
    name = "simulated"

    def create_request(self, *, contract_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
        return {"provider": self.name, "contract_id": contract_id, "simulated": True}

    def send_request(self, *, external_id: str | None, metadata: dict[str, Any]) -> dict[str, Any]:
        return {"provider": self.name, "external_id": external_id, "sent": True}

    def get_status(self, *, external_id: str | None, metadata: dict[str, Any]) -> dict[str, Any]:
        return {"provider": self.name, "status": metadata.get("status", "unknown")}

    def get_signer_link(self, *, token: str, metadata: dict[str, Any]) -> str:
        base = REVIEW_BASE_URL.rstrip("/")
        return f"{base}/sign/{token}"

    def record_open(self, *, metadata: dict[str, Any]) -> None:
        return None

    def sign(self, *, metadata: dict[str, Any]) -> dict[str, Any]:
        return {"provider": self.name, "completed": True}

    def decline(self, *, metadata: dict[str, Any]) -> dict[str, Any]:
        return {"provider": self.name, "declined": True}

    def download_signed_document(self, *, metadata: dict[str, Any]) -> bytes:
        data = metadata.get("signed_bytes")
        if isinstance(data, bytes):
            return data
        return b""

    def generate_certificate(self, *, metadata: dict[str, Any]) -> bytes:
        data = metadata.get("certificate_bytes")
        if isinstance(data, bytes):
            return data
        return b""
