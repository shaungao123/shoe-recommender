"""Cleaning + entity resolution.

Cleaning: unit parsing (oz/g, mm, USD cents), fixed-vocabulary mapping for
cut/width/length/outdoor/positions/playstyles, boilerplate stripping.

Entity resolution: the same shoe appears on every site under a different
name ("GT Cut 3" vs "G.T. Cut 3" vs "Nike GT Cut 3 Performance Review").
We normalize brand+model into a matching key, group records, and merge each
group into one CanonicalShoe with per-field provenance. Near-miss keys are
flagged for manual review, never merged silently.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field, asdict

from pipeline.schema import (
    CanonicalShoe,
    MERGEABLE_FIELDS,
    SourceRecord,
)

# ---------------------------------------------------------------------------
# Unit / money parsing
# ---------------------------------------------------------------------------

_NUM = r"(\d+(?:\.\d+)?)"

OZ_PER_GRAM = 0.03527396


def parse_weight_oz(text: str) -> tuple[float | None, float | None]:
    """'13.9 oz' or '394 g' → (oz, g), both populated when either is found."""
    if m := re.search(_NUM + r"\s*oz", text, re.I):
        oz = float(m.group(1))
        return oz, round(oz / OZ_PER_GRAM, 1)
    if m := re.search(_NUM + r"\s*g(?:rams)?\b", text, re.I):
        g = float(m.group(1))
        return round(g * OZ_PER_GRAM, 2), g
    return None, None


def parse_mm(text: str) -> float | None:
    """'8 mm' / '8.5mm' → 8.0 / 8.5."""
    if m := re.search(_NUM + r"\s*mm", text, re.I):
        return float(m.group(1))
    if re.fullmatch(r"\s*" + _NUM + r"\s*", text):
        return float(text.strip())
    return None


def parse_usd_cents(text: str) -> int | None:
    """'$150' / '150 USD' / '$129.99' → integer cents."""
    if m := re.search(r"\$?\s*" + _NUM + r"\s*(?:USD)?", text):
        return round(float(m.group(1)) * 100)
    return None


# ---------------------------------------------------------------------------
# Fixed-vocabulary mapping
# ---------------------------------------------------------------------------


def map_cut_height(text: str) -> str | None:
    s = text.lower()
    if "low" in s:
        return "low"
    if "mid" in s:
        return "mid"
    if "high" in s:
        return "high"
    return None


def map_width_fit(text: str) -> str | None:
    s = text.lower()
    if "narrow" in s:
        return "narrow"
    if "wide" in s:
        return "wide"
    if "standard" in s or "medium" in s or "normal" in s or "true" in s:
        return "standard"
    return None


def map_length_fit(text: str) -> str | None:
    s = text.lower()
    if "true to size" in s or s in ("tts", "true"):
        return "true_to_size"
    small = "small" in s or "short" in s or "size up" in s
    large = "large" in s or "big" in s or "long" in s or "size down" in s
    slightly = "slight" in s or "half" in s or "bit" in s
    if small:
        return "slightly_small" if slightly else "runs_small"
    if large:
        return "slightly_large" if slightly else "runs_large"
    return None


def map_outdoor(text: str) -> str | None:
    s = text.lower()
    if "good" in s or "great" in s or "excellent" in s:
        return "good"
    if "fair" in s or "average" in s or "decent" in s or "ok" in s:
        return "fair"
    if "bad" in s or "poor" in s or "avoid" in s:
        return "bad"
    return None


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


def map_positions(text: str) -> list[str]:
    tags: list[str] = []
    for token in re.split(r"[/,;+&]| and ", text.lower()):
        tag = _POSITION_MAP.get(token.strip())
        if tag and tag not in tags:
            tags.append(tag)
    return tags


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


def map_playstyles(text: str) -> list[str]:
    tags: list[str] = []
    for token in re.split(r"[/,;+&]| and ", text.lower()):
        tag = _PLAYSTYLE_MAP.get(token.strip())
        if tag and tag not in tags:
            tags.append(tag)
    return tags


# ---------------------------------------------------------------------------
# Boilerplate stripping (review prose only)
# ---------------------------------------------------------------------------

_BOILERPLATE_PATTERNS = [
    re.compile(r"(?:some|the) links? (?:on|in) this (?:page|post|article).{0,300}", re.I | re.S),
    re.compile(r"affiliate (?:links?|commission|disclosure).{0,300}", re.I | re.S),
    re.compile(r"we may earn a commission.{0,200}", re.I | re.S),
    re.compile(r"at no (?:extra|additional) cost to you.{0,100}", re.I | re.S),
    re.compile(r"(?:click|tap) here to (?:buy|shop|check).{0,150}", re.I | re.S),
    re.compile(r"(?:buy|shop|check price) (?:it |them )?(?:now |today )?(?:at|on|from) (?:amazon|nike|adidas|ebay|stockx)[^.]*\.?", re.I),
    re.compile(r"subscribe to (?:our|the) (?:newsletter|channel).{0,150}", re.I | re.S),
]


def strip_boilerplate(text: str) -> str:
    for pattern in _BOILERPLATE_PATTERNS:
        text = pattern.sub("", text)
    return re.sub(r"\s{2,}", " ", text).strip()


# ---------------------------------------------------------------------------
# Brand + model normalization
# ---------------------------------------------------------------------------

# canonical brand → phrases that mean it (longest matched first)
BRAND_ALIASES: dict[str, list[str]] = {
    "Jordan": ["air jordan", "jordan brand", "jordan"],
    "Nike": ["nike"],
    "Adidas": ["adidas"],
    "Under Armour": ["under armour", "under armor", "ua "],
    "Puma": ["puma"],
    "New Balance": ["new balance", "nb "],
    "Anta": ["anta"],
    "Li-Ning": ["li-ning", "li ning", "lining", "way of wade"],
    "Reebok": ["reebok"],
    "Converse": ["converse"],
    "361 Degrees": ["361 degrees", "361°", "361"],
    "Peak": ["peak"],
    "Asics": ["asics"],
}

_BRAND_LOOKUP: list[tuple[str, str]] = sorted(
    ((alias, brand) for brand, aliases in BRAND_ALIASES.items() for alias in aliases),
    key=lambda pair: -len(pair[0]),
)


def normalize_brand(text: str) -> str | None:
    s = text.strip().lower()
    for alias, brand in _BRAND_LOOKUP:
        if s == alias.strip() or s.startswith(alias):
            return brand
    return None


def split_brand(display_name: str) -> tuple[str | None, str]:
    """'Nike G.T. Cut 3' → ('Nike', 'G.T. Cut 3'). Brand may be absent."""
    s = display_name.strip()
    lower = s.lower()
    for alias, brand in _BRAND_LOOKUP:
        alias = alias.strip()
        if lower.startswith(alias + " "):
            rest = s[len(alias):].strip()
            # 'Way of Wade' is a line name, keep it in the model
            if alias == "way of wade":
                rest = s
            return brand, rest
    return None, s


_ROMAN = {
    "ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6", "vii": "7",
    "viii": "8", "ix": "9", "x": "10", "xi": "11", "xii": "12",
    "xiii": "13", "xiv": "14", "xx": "20", "xxx": "30",
    "xxxi": "31", "xxxii": "32", "xxxiii": "33", "xxxiv": "34",
    "xxxv": "35", "xxxvi": "36", "xxxvii": "37", "xxxviii": "38",
    "xxxix": "39", "xl": "40",
}

# tokens that vary between sites for the same shoe, or mark a colorway/edition
_DROP_TOKENS = {
    "the", "basketball", "shoe", "shoes", "performance", "review",
    "ep", "pe", "se", "team", "edition",
}

_TOKEN_ALIASES = {
    "zer0": "zero",
    "vol": "volume",
    "don": "don",  # keep as-is (D.O.N. Issue)
}


def model_key(brand: str | None, model: str) -> str:
    """Stable matching key: lowercase, punctuation-free, alias-folded.

    'G.T. Cut 3' and 'GT Cut 3' both → 'gt cut 3'.
    """
    s = model.lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[.'’]", "", s)  # G.T. → GT, D.O.N. → DON
    s = re.sub(r"[^a-z0-9]+", " ", s)
    brand_words = {
        word
        for alias in BRAND_ALIASES.get(brand or "", [])
        for word in alias.split()
    }
    tokens: list[str] = []
    for token in s.split():
        if token in brand_words:
            continue  # brand repeated inside the model name (e.g. 'Air Jordan')
        if token in _DROP_TOKENS:
            continue
        token = _ROMAN.get(token, token)
        token = _TOKEN_ALIASES.get(token, token)
        tokens.append(token)
    return " ".join(tokens)


def slugify(*parts: str) -> str:
    joined = " ".join(p for p in parts if p)
    return re.sub(r"[^a-z0-9]+", "-", joined.lower()).strip("-")


def extract_version(model: str) -> str | None:
    """Trailing edition number: 'GT Cut 3' → '3'. None when unnumbered."""
    if m := re.search(r"(\d+(?:\.\d+)?)\s*$", model_key(None, model)):
        return m.group(1)
    return None


def numeric_signature(key: str) -> tuple[str, ...]:
    """All numeric tokens of a model key, in order.

    Numbers are versioning: keys whose signatures differ are different
    shoes, full stop — 'kobe 4 protro' vs 'kobe 8 protro', and
    'all pro nitro' vs 'all pro nitro 2' (absent != present).
    """
    return tuple(t for t in key.split() if re.fullmatch(r"\d+(?:\.\d+)?", t))


# ---------------------------------------------------------------------------
# Entity resolution
# ---------------------------------------------------------------------------

# Physical-spec priority: manufacturer specs, then lab data, then aggregators.
SOURCE_PRIORITY = [
    "basketballshoespecs",
    "runrepeat",
    "thehoopsgeek",
    "weartesters",
]

FUZZY_REVIEW_THRESHOLD = 0.86  # below: distinct; above: flag for review


@dataclass
class ResolutionReport:
    canonical: list[CanonicalShoe] = field(default_factory=list)
    unmatched: list[dict] = field(default_factory=list)  # single-source or brandless
    ambiguous: list[dict] = field(default_factory=list)  # near-miss keys to review

    def to_dict(self) -> dict:
        return {
            "canonical": [c.to_dict() for c in self.canonical],
            "unmatched": self.unmatched,
            "ambiguous": self.ambiguous,
        }


def _priority(record: SourceRecord) -> int:
    try:
        return SOURCE_PRIORITY.index(record.source)
    except ValueError:
        return len(SOURCE_PRIORITY)


def _merge_group(key: str, records: list[SourceRecord]) -> CanonicalShoe:
    records = sorted(records, key=_priority)
    top = records[0]
    brand = next((r.brand for r in records if r.brand), "unknown")
    model = top.model or top.model_raw
    version = extract_version(model)
    shoe = CanonicalShoe(
        canonical_id=slugify(brand, model_key(brand, model)),
        brand=brand,
        model=model,
        version=version,
    )
    for record in records:
        shoe.sources.append(
            {"source": record.source, "url": record.url, "fetched_at": record.fetched_at}
        )
        if record.scores:
            shoe.metrics[record.source] = record.scores
        shoe.pros.extend({"source": record.source, "text": p} for p in record.pros)
        shoe.cons.extend({"source": record.source, "text": c} for c in record.cons)
        shoe.review_text.extend(
            {"source": record.source, "text": seg} for seg in record.review_text
        )
        for img in record.image_urls:
            if img not in shoe.image_urls:
                shoe.image_urls.append(img)
        # union tags across sources (order = priority)
        for tag in record.position_tags:
            if tag not in shoe.position_tags:
                shoe.position_tags.append(tag)
        for tag in record.playstyle_tags:
            if tag not in shoe.playstyle_tags:
                shoe.playstyle_tags.append(tag)

    # single-valued fields: first non-null wins, in source priority order
    for field_name in MERGEABLE_FIELDS:
        for record in records:
            value = getattr(record, field_name)
            if value is not None:
                setattr(shoe, field_name, value)
                shoe.provenance[field_name] = {
                    "source": record.source,
                    "url": record.url,
                    "fetched_at": record.fetched_at,
                }
                break
    return shoe


def resolve(records: list[SourceRecord]) -> ResolutionReport:
    """Group per-source records into canonical shoes.

    Exact (brand, model_key) matches merge automatically. Keys that are
    *nearly* identical within a brand are reported in ``ambiguous`` for a
    human decision — they are NOT merged. Records with no recognizable brand
    go to ``unmatched``.
    """
    report = ResolutionReport()

    groups: dict[tuple[str, str], list[SourceRecord]] = {}
    for record in records:
        brand = record.brand or split_brand(record.model_raw)[0]
        if brand:
            brand = normalize_brand(brand) or brand
        model = record.model or split_brand(record.model_raw)[1]
        if not brand:
            report.unmatched.append(
                {
                    "reason": "no recognizable brand",
                    "record": record.to_dict(),
                }
            )
            continue
        record.brand = brand
        record.model = model
        groups.setdefault((brand, model_key(brand, model)), []).append(record)

    # near-miss detection between distinct keys of the same brand
    keys_by_brand: dict[str, list[str]] = {}
    for brand, key in groups:
        keys_by_brand.setdefault(brand, []).append(key)
    flagged_pairs: set[tuple[str, str, str]] = set()
    for brand, keys in keys_by_brand.items():
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                # numbers are versioning: any numeric difference (including
                # unnumbered vs numbered) means genuinely different shoes
                if numeric_signature(a) != numeric_signature(b):
                    continue
                ratio = difflib.SequenceMatcher(None, a, b).ratio()
                if ratio >= FUZZY_REVIEW_THRESHOLD:
                    flagged_pairs.add((brand, a, b))

    for (brand, key), group in sorted(groups.items()):
        report.canonical.append(_merge_group(key, group))

    for brand, a, b in sorted(flagged_pairs):
        report.ambiguous.append(
            {
                "reason": "similar model keys — merge manually if same shoe",
                "brand": brand,
                "keys": [a, b],
                "records": [
                    {"source": r.source, "model_raw": r.model_raw, "url": r.url}
                    for k in (a, b)
                    for r in groups[(brand, k)]
                ],
            }
        )

    return report
