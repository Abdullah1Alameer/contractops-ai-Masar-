from datetime import date as _date

from fastapi import APIRouter, HTTPException

from ..services.dates import format_gregorian_ar, gregorian_to_hijri_parts

router = APIRouter(prefix="/util", tags=["util"])


@router.get("/hijri")
def hijri(date: str):
    """Dual-calendar rendering helper for the frontend <DualDate> component.
    All conversion via hijri-converter (Umm al-Qura) — single source of truth."""
    try:
        g = _date.fromisoformat(date)
    except ValueError:
        raise HTTPException(422, detail={"error": "invalid_date"})
    return {
        "gregorian": g.isoformat(),
        "gregorian_ar": format_gregorian_ar(g),
        "hijri": gregorian_to_hijri_parts(g),
    }
