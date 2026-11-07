"""Presentation-only fund labels; no changes to persisted fund data."""
import re


_CATEGORY_PATTERNS = (
    ("midcap", "Midcap", r"\bmid[\s-]*cap\b"),
    ("smallcap", "Smallcap", r"\bsmall[\s-]*cap\b"),
    ("flexicap", "Flexi Cap", r"\bflexi[\s-]*cap\b"),
    ("elss", "ELSS", r"\belss\b"),
    ("microcap", "Microcap", r"\bmicro[\s-]*cap\b"),
)


def fund_category(name):
    """Classify recognizable scheme names, leaving unknown schemes as Other."""
    for key, label, pattern in _CATEGORY_PATTERNS:
        if re.search(pattern, name or "", re.IGNORECASE):
            return {"key": key, "label": label}
    return {"key": "other", "label": "Other"}
