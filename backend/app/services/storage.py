"""Local-disk file storage abstraction.

Swapping to Supabase Storage later = rewrite THIS FILE ONLY
(keep save/get signatures identical).
"""
import os
import uuid

from ..config import STORAGE_DIR


class StorageService:
    def __init__(self, base_dir: str = STORAGE_DIR):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def save(self, data: bytes, filename: str) -> str:
        """Store bytes; return an opaque key (goes into contracts.file_url)."""
        safe = os.path.basename(filename).replace(" ", "_")
        key = f"{uuid.uuid4().hex}_{safe}"
        with open(os.path.join(self.base_dir, key), "wb") as f:
            f.write(data)
        return key

    def get(self, key: str) -> bytes:
        with open(os.path.join(self.base_dir, key), "rb") as f:
            return f.read()


storage = StorageService()
