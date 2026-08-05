"""Abstract e-signature provider contract."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ESignProvider(ABC):
    name: str = "base"

    @abstractmethod
    def create_request(self, *, contract_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
        ...

    @abstractmethod
    def send_request(self, *, external_id: str | None, metadata: dict[str, Any]) -> dict[str, Any]:
        ...

    @abstractmethod
    def get_status(self, *, external_id: str | None, metadata: dict[str, Any]) -> dict[str, Any]:
        ...

    @abstractmethod
    def get_signer_link(self, *, token: str, metadata: dict[str, Any]) -> str:
        ...

    @abstractmethod
    def record_open(self, *, metadata: dict[str, Any]) -> None:
        ...

    @abstractmethod
    def sign(self, *, metadata: dict[str, Any]) -> dict[str, Any]:
        ...

    @abstractmethod
    def decline(self, *, metadata: dict[str, Any]) -> dict[str, Any]:
        ...

    @abstractmethod
    def download_signed_document(self, *, metadata: dict[str, Any]) -> bytes:
        ...

    @abstractmethod
    def generate_certificate(self, *, metadata: dict[str, Any]) -> bytes:
        ...
