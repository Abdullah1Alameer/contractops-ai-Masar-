"""THE MOST IMPORTANT FILE IN THE REPO.

Quote verification: every value the model returns must be traceable to a
verbatim substring of the contract text. Values whose quote does not verify
are kept but demoted (confidence capped at 0.5, no clause link) and are NEVER
shown as clickable sources in the UI.

normalize() is a strict 1:1 character mapping (length-preserving), applied to
BOTH the prompt input and the verification target, so char offsets computed on
normalized text are valid offsets into the original raw_text.
"""

# Arabic-Indic ٠-٩ and Eastern Arabic-Indic ۰-۹ → ASCII 0-9 (1:1, length-preserving)
_DIGIT_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def normalize(text: str) -> str:
    """Pure, length-preserving normalization used consistently for the prompt
    input AND quote verification so offsets always match."""
    return text.translate(_DIGIT_MAP)


def _collapse_ws(s: str) -> tuple[str, list[int]]:
    """Collapse whitespace runs to a single space; return (collapsed, index_map)
    where index_map[i] = offset in the original string of collapsed char i."""
    out: list[str] = []
    idx: list[int] = []
    prev_space = False
    for i, ch in enumerate(s):
        if ch.isspace():
            if not prev_space and out:
                out.append(" ")
                idx.append(i)
            prev_space = True
        else:
            out.append(ch)
            idx.append(i)
            prev_space = False
    return "".join(out), idx


def validate_quote(raw_text_normalized: str, quote_normalized: str) -> tuple[bool, int | None, int | None]:
    """Exact substring search on normalized text; fallback to a
    whitespace-collapsed search (offsets mapped back to the original text).

    Returns (found, char_start, char_end) — offsets valid in raw_text.
    """
    quote = quote_normalized.strip()
    if not quote:
        return False, None, None

    pos = raw_text_normalized.find(quote)
    if pos != -1:
        return True, pos, pos + len(quote)

    collapsed_text, index_map = _collapse_ws(raw_text_normalized)
    collapsed_quote, _ = _collapse_ws(quote)
    if not collapsed_quote:
        return False, None, None
    pos = collapsed_text.find(collapsed_quote)
    if pos == -1:
        return False, None, None
    start = index_map[pos]
    end = index_map[pos + len(collapsed_quote) - 1] + 1
    return True, start, end


def page_for_offset(page_starts: dict[int, int], offset: int) -> int | None:
    """Map a global char offset back to its page using the [[PAGE n]] boundaries."""
    best = None
    for page, start in sorted(page_starts.items(), key=lambda kv: kv[1]):
        if start <= offset:
            best = page
        else:
            break
    return best
