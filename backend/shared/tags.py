"""Canonical playstyle/position tag vocabulary.

Shared by the pipeline (index time: ``pipeline/normalize.py``) and the
retriever's no-vector fallback (query time), so a synonym added for one side
is automatically understood by the other.
"""

from __future__ import annotations

import re

_POSITION_MAP = {
    "pg": "guard",
    "sg": "guard",
    "guard": "guard",
    "point guard": "guard",
    "shooting guard": "guard",
    "sf": "wing",
    "wing": "wing",
    "small forward": "wing",
    "forward": "wing",
    "pf": "big",
    "c": "big",
    "big": "big",
    "center": "big",
    "power forward": "big",
    "big man": "big",
}

_PLAYSTYLE_MAP = {
    "slasher": "slasher",
    "shooter": "shooter",
    "all-around": "all-around",
    "all around": "all-around",
    "allround": "all-around",
    "versatile": "all-around",
    "post": "post",
    "post player": "post",
    "post scorer": "post",
    "defender": "defender",
    "lockdown defender": "defender",
    "speedster": "speedster",
    "quick guard": "speedster",
    "shifty": "speedster",
}


def _map_tokens(text: str, mapping: dict[str, str]) -> list[str]:
    """Token-exact mapping for scraped spec fields (e.g. "PG/SG", "Slasher;Shooter")."""
    tags: list[str] = []
    for token in re.split(r"[/,;+&]| and ", text.lower()):
        tag = mapping.get(token.strip())
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def map_positions(text: str) -> list[str]:
    return _map_tokens(text, _POSITION_MAP)


def map_playstyles(text: str) -> list[str]:
    return _map_tokens(text, _PLAYSTYLE_MAP)


def extract_tags(free_text: str) -> set[str]:
    """Canonical tags mentioned anywhere in free user text.

    Whole-word/phrase matching, so "guard" doesn't fire on "safeguard" and
    "post" doesn't fire on "poster". Single-letter synonyms ("c") are skipped —
    too ambiguous outside a structured spec field.
    """
    text = free_text.lower()
    found: set[str] = set()
    for synonym, tag in {**_POSITION_MAP, **_PLAYSTYLE_MAP}.items():
        if len(synonym) > 1 and re.search(rf"\b{re.escape(synonym)}\b", text):
            found.add(tag)
    return found
