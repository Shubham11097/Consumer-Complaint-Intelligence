"""Text cleaning rules for CFPB complaint narratives.

CFPB redacts personal details before publishing a narrative:
  * names, account numbers, places   -> "XXXX" (often several in a row)
  * dates                            -> "XX/XX/XXXX" or "XX/XX/2025"
  * money amounts are wrapped        -> "{$1,250.00}"

The cleaned text replaces these with consistent placeholder tokens, so a model
learns "a date was mentioned" instead of memorising strings of X's or specific
amounts, and tidies whitespace. The original text is always kept alongside.
"""

import hashlib
import re

DATE_TOKEN = "[DATE]"
AMOUNT_TOKEN = "[AMOUNT]"
REDACTED_TOKEN = "[REDACTED]"

_DATE = re.compile(r"\bX{2}/X{2}/(?:X{2,4}|\d{2,4})\b")
_AMOUNT = re.compile(r"\{\s*\$?\s*[\d,]+(?:\.\d+)?\s*\}")
_REDACTED_RUN = re.compile(r"\bX{2,}\b(?:[\s,.-]*\bX{2,}\b)*")
_WHITESPACE = re.compile(r"\s+")
_LETTER = re.compile(r"[A-Za-z]")
_TOKENS = re.compile(r"\[(?:DATE|AMOUNT|REDACTED)\]")


def clean_narrative(text: str) -> str:
    """Return the cleaned narrative: placeholders for redactions, tidy whitespace."""
    if not isinstance(text, str):
        return ""
    text = _DATE.sub(f" {DATE_TOKEN} ", text)
    text = _AMOUNT.sub(f" {AMOUNT_TOKEN} ", text)
    text = _REDACTED_RUN.sub(f" {REDACTED_TOKEN} ", text)
    return _WHITESPACE.sub(" ", text).strip()


def has_content(cleaned: str) -> bool:
    """True if the cleaned text has real words, not only placeholder tokens."""
    return bool(_LETTER.search(_TOKENS.sub("", cleaned)))


def word_count(cleaned: str) -> int:
    return len(cleaned.split()) if cleaned else 0


def text_hash(cleaned: str) -> str:
    """Short fingerprint of the cleaned text, used to find repeated template complaints."""
    normalised = _WHITESPACE.sub(" ", cleaned.lower()).strip()
    return hashlib.sha1(normalised.encode("utf-8")).hexdigest()[:16]
