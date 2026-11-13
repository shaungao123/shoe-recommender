"""Shopper profiles with hand-labeled good and bad fits.

Labels are basketball judgment, independent of the review scores the ranker
uses, and are regexes over "Brand Name". An unmatched shoe is simply unlabeled.
A pick matching both lists counts as bad. DRAFT: written from general hoops
knowledge and awaiting review by someone who plays in these shoes.
"""

from dataclasses import dataclass, field
from typing import Any

FLAGSHIP_LEBRON = r"Nike LeBron \d{2}\b"
QUICK_GUARD = (
    r"Kyrie (?:[3-8]\b|Low|Infinity|S1)|Kobe (?:AD|\d)|G\.?T\.? Cut|Sabrina|Nike Ja [1-4]|Book [12]"
    r"|Curry (?:[3-9]\b|1[0-3]\b)|Hesi Low|Adizero Select|D\.?O\.?N\.? Issue|Dame (?:[3-9]\b|X)"
    r"|Trae Young|MB\.0[1-5]|Kai \d|Speed \d|Ultra Light"
)
BIG_SUPPORT = (
    FLAGSHIP_LEBRON + r"|Zion [1-4]|Embiid|Joker [12]|G\.?T\.? Jump|Kawhi|Hyperdunk|Marquee Boost"
    r"|Exhibit A"
)
WING_VERSATILE = (
    r"KD 1\d|Tatum|Freak|Kawhi|Book [12]|PG ?\d|A\.?E\.? ?[12]|Anthony Edwards|Luka [1-5]"
    r"|KD Trey|KT \d|Jimmy Butler|JB ?\d"
)
LOW_MINIMAL = r"Kyrie (?:Low|[3-6]\b)|Kobe [45] Protro|Adizero Select|Ultra Light|Sabrina"
OUTDOOR_TOUGH = (
    r"All City|KT Outdoor|Shock the Game|Precision [5-8]|Giannis Immortality|Witness"
    r"|Renew Elevate|Kyrie Flytrap|Harden Stepback|Dame Certified|One Take|Lockdown"
)
OUTDOOR_FRAGILE = r"Kobe .*Protro|G\.?T\.? Cut(?! Academy| Cross)|Kobe AD NXT|Adapt BB|Huarache"
PLUSH = (
    FLAGSHIP_LEBRON + r"|Zion [12]|Way of Wade \d|Wade 808|Kawhi|G\.?T\.? Jump|KD 1[3-9]"
    r"|Crazy BYW|Fresh Foam|KT [89]|Harden Vol"
)
THIN_CUSHION = r"Kyrie [3-6]\b|Kobe [45] Protro|Adizero Select"
GRIPPY = (
    r"Kyrie|Kobe|Curry (?:[4-9]\b|1\d)|Sabrina|G\.?T\.? Cut|Book [12]|Nike Ja [1-4]|All.Pro Nitro"
)
LIGHT = r"Adizero Select|Ultra Light|Kobe AD|Sabrina|Curry|Nike Ja|Speed \d|Air Go LWP"
# Leapers: bouncy, springy cushioning (Zoom Strobel, ZoomX, Boom, Jet Boost, Nitro).
LEAPER = (
    r"G\.?T\.? Jump|Way of Wade (?:9|1\d)|Wade 808|Anthony Edwards|A\.?E\.? ?[12]\b"
    r"|Harden Vol(?:ume)?\.? ?(?:[7-9]|10)\b|All.Pro Nitro|KT (?:9|10)\b|Zion [1-4]\b"
    r"|LeBron (?:19|2[0-3])\b|KD 1[5-8]\b"
)
HEAVY = FLAGSHIP_LEBRON + r"|Zion|Adapt BB|Shox"
BUDGET_PERFORMER = (
    r"Precision|Giannis Immortality|Kyrie Flytrap|Renew Elevate|Witness|Dame Certified"
    r"|Trae Unlimited|One Take|Spawn|Lockdown|Court Rider|Harden Stepback|KD Trey|G\.?T\.? \w+ Academy"
)
# Lifestyle or decades-old retros: fine sneakers, poor picks to play in today.
NOT_FOR_PLAY = (
    r"Yeezy|Jordan Air Jordan .*Retro|Jordan 1 Low|Air Force 1|Chuck 70|Foamposite"
    r"|Jordan (?:[3-7]|1[0-3])(?: |$)|Air Penny|More Uptempo|Max Uptempo|Shox"
)


@dataclass(frozen=True)
class Case:
    id: str
    request: dict[str, Any]
    good: tuple[str, ...]
    bad: tuple[str, ...] = field(default=())


CASES = [
    Case("guard-slasher-outdoor-traction", {"playstyle": "Guard, Slasher", "budget": 140, "court": "outdoor", "priorities": ["traction"]}, (OUTDOOR_TOUGH,), (OUTDOOR_FRAGILE,)),
    Case("guard-slasher-indoor-traction", {"playstyle": "Guard, Slasher", "budget": 160, "court": "indoor", "priorities": ["traction"]}, (QUICK_GUARD, GRIPPY), (HEAVY,)),
    Case("guard-slasher-indoor-cushion", {"playstyle": "Guard, Slasher", "budget": 140, "court": "indoor", "priorities": ["cushion"]}, (PLUSH,), (THIN_CUSHION,)),
    Case("guard-speedster-light", {"playstyle": "Guard, Speedster", "budget": 140, "court": "indoor", "priorities": ["lightweight"]}, (QUICK_GUARD, LIGHT), (HEAVY,)),
    Case("guard-shooter-indoor", {"playstyle": "Guard, Shooter", "court": "indoor"}, (QUICK_GUARD,), (HEAVY,)),
    Case("guard-shooter-no-limit", {"playstyle": "Guard, Shooter", "court": "indoor", "priorities": ["traction", "lightweight"]}, (QUICK_GUARD,), (HEAVY,)),
    Case("guard-budget-both", {"playstyle": "Guard, Slasher", "budget": 100, "court": "both"}, (BUDGET_PERFORMER,), (OUTDOOR_FRAGILE,)),
    Case("guard-budget-outdoor", {"playstyle": "Guard, All-around", "budget": 100, "court": "outdoor", "priorities": ["traction"]}, (OUTDOOR_TOUGH, BUDGET_PERFORMER), (OUTDOOR_FRAGILE,)),
    Case("guard-nike-preference", {"playstyle": "Guard, Slasher", "budget": 160, "court": "indoor", "preferred_brand": "Nike"}, (QUICK_GUARD,), (HEAVY,)),
    Case("guard-minor-brand-preference", {"playstyle": "Guard, Shooter", "budget": 160, "court": "indoor", "preferred_brand": "Puma"}, (QUICK_GUARD,), (HEAVY,)),
    Case("wing-allaround-outdoor", {"playstyle": "Wing, All-around", "budget": 180, "court": "outdoor", "priorities": ["cushion", "support"]}, (OUTDOOR_TOUGH,), (OUTDOOR_FRAGILE,)),
    Case("wing-allaround-indoor", {"playstyle": "Wing, All-around", "budget": 160, "court": "indoor"}, (WING_VERSATILE,), ()),
    Case("wing-defender-support", {"playstyle": "Wing, Defender", "budget": 180, "court": "indoor", "priorities": ["support"]}, (WING_VERSATILE, BIG_SUPPORT), (LOW_MINIMAL,)),
    Case("wing-slasher-cushion", {"playstyle": "Wing, Slasher", "budget": 160, "court": "indoor", "priorities": ["cushion"]}, (WING_VERSATILE, PLUSH), (THIN_CUSHION,)),
    Case("wing-jordan-preference", {"playstyle": "Wing, Shooter", "budget": 160, "court": "indoor", "preferred_brand": "Jordan"}, (WING_VERSATILE,), ()),
    Case("big-post-indoor-support", {"playstyle": "Big, Post", "court": "indoor", "priorities": ["support"]}, (BIG_SUPPORT,), (LOW_MINIMAL,)),
    Case("big-post-cushion", {"playstyle": "Big, Post", "budget": 180, "court": "indoor", "priorities": ["cushion", "support"]}, (BIG_SUPPORT, PLUSH), (LOW_MINIMAL,)),
    Case("big-post-wide-adidas-high", {"playstyle": "Big, Post", "court": "indoor", "priorities": ["support"], "foot_width": "wide", "preferred_brand": "Adidas", "preferred_cut": "high"}, (BIG_SUPPORT,), (LOW_MINIMAL,)),
    Case("big-budget", {"playstyle": "Big, Post", "budget": 120, "court": "both", "priorities": ["support"]}, (BIG_SUPPORT, BUDGET_PERFORMER), (LOW_MINIMAL,)),
    Case("big-defender-outdoor", {"playstyle": "Big, Defender", "budget": 180, "court": "outdoor", "priorities": ["cushion"]}, (OUTDOOR_TOUGH, BIG_SUPPORT), (OUTDOOR_FRAGILE, LOW_MINIMAL)),
    Case("not-sure-indoor", {"playstyle": "", "budget": 140, "court": "indoor"}, (QUICK_GUARD, WING_VERSATILE), ()),
    Case("guard-leaper-indoor", {"playstyle": "Guard, Leaper", "budget": 180, "court": "indoor"}, (LEAPER,), (LOW_MINIMAL, THIN_CUSHION)),
    Case("wing-leaper-cushion", {"playstyle": "Wing, Leaper", "budget": 180, "court": "indoor", "priorities": ["cushion"]}, (LEAPER,), (LOW_MINIMAL, THIN_CUSHION)),
    Case("big-leaper-support", {"playstyle": "Big, Leaper", "court": "indoor", "priorities": ["support"]}, (LEAPER, BIG_SUPPORT), (LOW_MINIMAL,)),
    Case("guard-leaper-budget", {"playstyle": "Guard, Leaper", "budget": 120, "court": "both"}, (LEAPER,), (LOW_MINIMAL, THIN_CUSHION)),
    Case("free-text-ankle-injury", {"playstyle": "Wing. Recovering from an ankle sprain, need stability", "budget": 180, "court": "indoor", "priorities": ["support"]}, (BIG_SUPPORT, WING_VERSATILE), (LOW_MINIMAL,)),
]
