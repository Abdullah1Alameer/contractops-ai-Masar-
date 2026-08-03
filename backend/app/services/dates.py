"""Hijri/Gregorian date parsing + conversion.

RULE: the LLM NEVER converts dates — it returns the raw string + detected
calendar. This module parses that raw string and converts hijri→gregorian
using the hijri-converter library ONLY (Umm al-Qura).
"""
import re
from datetime import date

from hijri_converter import Gregorian, Hijri

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

HIJRI_MONTHS = {
    "محرم": 1, "صفر": 2,
    "ربيع الأول": 3, "ربيع الاول": 3,
    "ربيع الآخر": 4, "ربيع الاخر": 4, "ربيع الثاني": 4,
    "جمادى الأولى": 5, "جمادى الاولى": 5, "جمادى الأول": 5,
    "جمادى الآخرة": 6, "جمادى الاخرة": 6, "جمادى الثانية": 6,
    "رجب": 7, "شعبان": 8, "رمضان": 9, "شوال": 10,
    "ذو القعدة": 11, "ذي القعدة": 11, "ذو الحجة": 12, "ذي الحجة": 12,
}
HIJRI_MONTH_NAMES = [
    "محرم", "صفر", "ربيع الأول", "ربيع الآخر", "جمادى الأولى", "جمادى الآخرة",
    "رجب", "شعبان", "رمضان", "شوال", "ذو القعدة", "ذو الحجة",
]
GREG_MONTHS = {
    "يناير": 1, "فبراير": 2, "مارس": 3, "أبريل": 4, "ابريل": 4, "مايو": 5,
    "يونيو": 6, "يوليو": 7, "أغسطس": 8, "اغسطس": 8, "سبتمبر": 9,
    "أكتوبر": 10, "اكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
GREG_MONTH_NAMES_AR = [
    "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
]

_NUMERIC = re.compile(r"(\d{1,4})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{1,4})")
_NAMED = re.compile(r"(\d{1,2})\s+(?:من\s+)?([؀-ۿa-zA-Z ]+?)\s+(?:لعام\s+|عام\s+|سنة\s+)?(\d{4})")


def _ymd_from_numeric(a: int, b: int, c: int) -> tuple[int, int, int] | None:
    if a > 31:  # yyyy/mm/dd
        y, m, d = a, b, c
    elif c > 31:  # dd/mm/yyyy
        y, m, d = c, b, a
    else:
        return None
    if not (1 <= m <= 12 and 1 <= d <= 30 + (m != 2)):
        return None
    return y, m, d


def parse_date_raw(value: str | None, calendar: str | None) -> date | None:
    """Parse a raw date string as written in the contract → gregorian date.
    Returns None if unparseable (caller keeps the raw string, leaves date NULL).
    """
    if not value:
        return None
    text = value.translate(_AR_DIGITS)
    is_hijri = calendar == "hijri" or "هـ" in text or "ه‍" in text

    ymd = None
    m = _NUMERIC.search(text)
    if m:
        ymd = _ymd_from_numeric(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    if ymd is None:
        m = _NAMED.search(text)
        if m:
            day, name, year = int(m.group(1)), m.group(2).strip().lower(), int(m.group(3))
            for months, hijri_flag in ((HIJRI_MONTHS, True), (GREG_MONTHS, False)):
                for k, v in months.items():
                    if k in name:
                        ymd = (year, v, day)
                        is_hijri = hijri_flag
                        break
                if ymd:
                    break
    if ymd is None:
        return None
    y, mo, d = ymd
    try:
        if is_hijri or y < 1600:
            return date(*Hijri(y, mo, d).to_gregorian().datetuple())
        return date(y, mo, d)
    except (ValueError, OverflowError):
        return None


def gregorian_to_hijri_parts(g: date) -> dict:
    h = Gregorian(g.year, g.month, g.day).to_hijri()
    return {
        "year": h.year,
        "month": h.month,
        "day": h.day,
        "month_name_ar": HIJRI_MONTH_NAMES[h.month - 1],
        "formatted_ar": f"{_to_arabic_digits(h.day)} {HIJRI_MONTH_NAMES[h.month - 1]} {_to_arabic_digits(h.year)}",
    }


def _to_arabic_digits(n: int) -> str:
    return str(n).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))


def format_gregorian_ar(g: date) -> str:
    return f"{_to_arabic_digits(g.day)} {GREG_MONTH_NAMES_AR[g.month - 1]} {_to_arabic_digits(g.year)}"
