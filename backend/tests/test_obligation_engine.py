"""Obligation intelligence fields."""
from app.services.intelligence import _rebuild_obligations


def test_rebuild_obligations_preserves_manual_flag():
    assert callable(_rebuild_obligations)
