"""RunRepeat — independent lab data + CoreScore.

NOTE: RunRepeat sells an official data export / REST API (CSV/JSON/SQL, see
https://runrepeat.com/retailers and /science-use) — it is paid/contact-sales.
If we ever license it, replace this scraper's fetch step with that feed and
keep ``parse``-level field mapping. Until then we politely scrape the shoe
detail pages, which their robots.txt allows (only /search and filter query
params are disallowed).

Page anatomy (server-rendered Nuxt, no JS needed):
* JSON-LD ``Product`` → name / brand / images
* ``.corescore`` element → CoreScore (1–100)
* a comparison table whose FIRST data column is this shoe's lab sheet
* ~26 small "<shoe> vs Average" tables → numeric lab facts
* "Our verdict" list → category sub-scores (cushioning/speed/stability/outdoor)
* Pros / Cons lists and verdict prose
"""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from pipeline.normalize import (
    map_cut_height,
    map_length_fit,
    map_width_fit,
    parse_mm,
    parse_usd_cents,
    parse_weight_oz,
    strip_boilerplate,
)
from pipeline.schema import SourceRecord
from pipeline.scrapers.base import BaseScraper, ShoeRef

CATALOG_URL = "https://runrepeat.com/catalog/basketball-shoes"
MAX_CATALOG_PAGES = 10

# comparison-table rows lifted into canonical fields; everything else in the
# table becomes a per-source score under its slugified label.
_PROSE_HEADINGS = ("our verdict", "who should buy", "who should not buy")


def _slug_key(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def _jsonld(soup: BeautifulSoup, type_name: str) -> dict | None:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("@type") == type_name:
                return item
    return None


class RunRepeatScraper(BaseScraper):
    name = "runrepeat"
    base_url = "https://runrepeat.com"

    def list_shoes(self) -> list[ShoeRef]:
        refs: list[ShoeRef] = []
        seen: set[str] = set()
        for page in range(1, MAX_CATALOG_PAGES + 1):
            url = CATALOG_URL if page == 1 else f"{CATALOG_URL}?page={page}"
            result = self.fetcher.get(self.name, url)
            if result is None:
                break
            item_list = _jsonld(BeautifulSoup(result.text, "lxml"), "ItemList")
            items = (item_list or {}).get("itemListElement", [])
            new = 0
            for item in items:
                if item.get("url") and item["url"] not in seen:
                    seen.add(item["url"])
                    refs.append(ShoeRef(name=item.get("name", ""), url=item["url"]))
                    new += 1
            if new == 0:  # past the last page
                break
        return refs

    # -- parse helpers ----------------------------------------------------

    def _comparison_column(self, soup: BeautifulSoup) -> dict[str, str]:
        """label → this shoe's value (first data column of the compare table)."""
        for table in soup.find_all("table"):
            text = table.get_text(" ", strip=True)
            if "Our score" in text and "Ranking" in text:
                out: dict[str, str] = {}
                for row in table.find_all("tr"):
                    cells = row.find_all(["th", "td"])
                    if len(cells) >= 2:
                        label = cells[0].get_text(" ", strip=True)
                        value = cells[1].get_text(" ", strip=True)
                        if label and value:
                            out[label] = value
                return out
        return {}

    def _fact_tables(self, soup: BeautifulSoup) -> dict[str, str]:
        """The small '<shoe> N | Average M' tables → {fact: shoe value}."""
        facts: dict[str, str] = {}
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if not 2 <= len(rows) <= 3:
                continue
            texts = [
                [c.get_text(" ", strip=True) for c in r.find_all(["td", "th"])]
                for r in rows
            ]
            avg_rows = [t for t in texts if t and t[0].lower() == "average"]
            shoe_rows = [t for t in texts if t and t[0].lower() != "average"]
            if not avg_rows or not shoe_rows or len(shoe_rows[0]) < 2:
                continue
            heading = table.find_previous(["h2", "h3"])
            if heading is None:
                continue
            facts.setdefault(
                _slug_key(heading.get_text(strip=True)), shoe_rows[0][1]
            )
        return facts

    def _verdict_subscores(self, soup: BeautifulSoup) -> dict[str, int]:
        for h in soup.find_all(["h2", "h3"]):
            if h.get_text(strip=True).lower() == "our verdict":
                ul = h.find_next("ul")
                if ul is None:
                    return {}
                scores: dict[str, int] = {}
                for li in ul.find_all("li"):
                    if m := re.match(r"(.+?)\s+(\d{1,3})$", li.get_text(" ", strip=True)):
                        scores[_slug_key(m.group(1))] = int(m.group(2))
                return scores
        return {}

    def _pros_cons(self, soup: BeautifulSoup, which: str) -> list[str]:
        for h in soup.find_all(["h2", "h3"]):
            if h.get_text(strip=True).lower() == which:
                ul = h.find_next("ul")
                if ul is not None:
                    return [li.get_text(" ", strip=True) for li in ul.find_all("li")]
        return []

    def _prose(self, soup: BeautifulSoup) -> list[str]:
        segments: list[str] = []
        for h in soup.find_all(["h2", "h3"]):
            title = h.get_text(strip=True).lower()
            if title not in _PROSE_HEADINGS:
                continue
            parts: list[str] = []
            for sib in h.find_all_next(["p", "ul", "div", "h2", "h3"]):
                if sib.name in ("h2", "h3"):
                    break
                classes = sib.get("class") or []
                if any("good-bad" in c for c in classes):
                    break
                if sib.name == "p":
                    parts.append(sib.get_text(" ", strip=True))
                elif sib.name == "div" and not classes and sib.find("div") is None:
                    # the verdict paragraph is a bare leaf <div>, not a <p>
                    text = sib.get_text(" ", strip=True)
                    if len(text) > 80:
                        parts.append(text)
                elif sib.name == "ul" and title.startswith("who"):
                    parts.extend(
                        "- " + li.get_text(" ", strip=True) for li in sib.find_all("li")
                    )
            text = strip_boilerplate("\n".join(p for p in parts if p))
            if text:
                segments.append(f"[{title}] {text}")
        return segments

    # -- main parse --------------------------------------------------------

    def parse(self, html: str, url: str, fetched_at: str) -> SourceRecord | None:
        soup = BeautifulSoup(html, "lxml")
        product = _jsonld(soup, "Product")
        if product is None:
            return None

        brand = None
        if isinstance(product.get("brand"), dict):
            brand = product["brand"].get("name")

        record = SourceRecord(
            source=self.name,
            url=url,
            fetched_at=fetched_at,
            model_raw=product.get("name", ""),
            brand=brand,
        )
        images = product.get("image") or []
        if isinstance(images, str):
            images = [images]
        record.image_urls = images[:1]  # variants of the same photo

        col = self._comparison_column(soup)
        if score := col.get("Our score"):
            if m := re.match(r"(\d{1,3})", score):
                record.scores["corescore"] = int(m.group(1))
        if price := col.get("Price"):
            record.msrp_usd_cents = parse_usd_cents(price)
        if sig := col.get("Signature"):
            record.signature_player = sig
        if weight := col.get("Weight lab"):
            record.weight_oz, record.weight_g = parse_weight_oz(weight)
        if drop := col.get("Drop lab"):
            record.drop_mm = parse_mm(drop)
        if heel := col.get("Heel stack lab"):
            record.stack_heel_mm = parse_mm(heel)
        if forefoot := col.get("Forefoot"):
            record.stack_forefoot_mm = parse_mm(forefoot)
        if size := col.get("Size"):
            record.length_fit = map_length_fit(size)
        if width := col.get("Width / fit"):
            record.width_fit = map_width_fit(width)
        if top := col.get("Top"):  # 'Top: Low' == low-top
            record.cut_height = map_cut_height(top)

        # qualitative lab calls from the compare table → per-source scores
        for label in (
            "Shock absorption", "Energy return", "Traction", "Breathability",
            "Outsole durability", "Midsole softness", "Stiffness",
            "Torsional rigidity", "Heel counter stiffness", "Toebox width",
            "Outsole hardness", "Outsole thickness",
        ):
            if value := col.get(label):
                record.scores[_slug_key(label)] = value

        # numeric lab facts (shoe vs catalog average) override the qualitative
        for fact, value in self._fact_tables(soup).items():
            record.scores[fact] = value

        subscores = self._verdict_subscores(soup)
        for name, value in subscores.items():
            record.scores[f"score_{name}"] = value
        if outdoor := subscores.get("outdoor"):
            record.outdoor_suitability = (
                "good" if outdoor >= 75 else "fair" if outdoor >= 55 else "bad"
            )

        record.pros = self._pros_cons(soup, "pros")
        record.cons = self._pros_cons(soup, "cons")
        record.review_text = self._prose(soup)
        return record
