"""The Hoops Geek — scores averaged over many expert reviews (~400 shoes).

Itself an aggregator, so its numbers are kept per-source in ``scores`` and
never averaged into other sources' data. React-rendered but fully
server-side; CSS class names are build-generated, so parsing anchors on
visible label text ("Traction", "Pros", "Released", …), never on classes.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from pipeline.normalize import (
    map_cut_height,
    map_length_fit,
    map_width_fit,
    parse_usd_cents,
    strip_boilerplate,
)
from pipeline.schema import SourceRecord
from pipeline.scrapers.base import BaseScraper, ShoeRef

LISTING_URL = "https://www.thehoopsgeek.com/shoe-reviews/"
MAX_LISTING_PAGES = 30

_CATEGORY_LABELS = ("Traction", "Cushion", "Materials", "Support", "Fit", "Outdoor")


class TheHoopsGeekScraper(BaseScraper):
    name = "thehoopsgeek"
    base_url = "https://www.thehoopsgeek.com"

    def list_shoes(self) -> list[ShoeRef]:
        refs: list[ShoeRef] = []
        seen: set[str] = set()
        for page in range(1, MAX_LISTING_PAGES + 1):
            url = LISTING_URL if page == 1 else f"{LISTING_URL}?pg={page}"
            result = self.fetcher.get(self.name, url)
            if result is None:
                break
            soup = BeautifulSoup(result.text, "lxml")
            new = 0
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if not re.match(r"^/shoe-reviews/[a-z0-9-]+/$", href):
                    continue
                name = a.get_text(" ", strip=True)
                if not name:  # image/thumbnail anchor for the same shoe
                    continue
                full = urljoin(self.base_url, href)
                if full in seen:
                    continue
                seen.add(full)
                refs.append(ShoeRef(name=name, url=full))
                new += 1
            if new == 0:
                break
        return refs

    # -- parse helpers ---------------------------------------------------

    def _category_cards(self, soup: BeautifulSoup) -> dict[str, tuple[str, str]]:
        """{label: (score_text, comment)} from the rating donut cards."""
        cards: dict[str, tuple[str, str]] = {}
        for div in soup.find_all("div"):
            label = div.get_text(strip=True)
            if label not in _CATEGORY_LABELS or div.find("div") is not None:
                continue
            card = div.parent
            score_el = card.find("span")
            comment_el = div.find_next_sibling("div")
            if score_el is None or comment_el is None:
                continue
            cards.setdefault(
                label,
                (score_el.get_text(strip=True), comment_el.get_text(" ", strip=True)),
            )
        return cards

    def _pros_cons(self, soup: BeautifulSoup, which: str) -> list[str]:
        label = soup.find(string=re.compile(rf"^\s*{which}\s*$"))
        if label is None:
            return []
        items: list[str] = []
        for sibling in label.parent.find_next_siblings("div"):
            leaf = sibling.find_all("div")
            if leaf:
                items.append(leaf[-1].get_text(" ", strip=True))
        return [i for i in items if i]

    # -- main parse --------------------------------------------------------

    def parse(self, html: str, url: str, fetched_at: str) -> SourceRecord | None:
        soup = BeautifulSoup(html, "lxml")
        h1 = soup.find("h1")
        if h1 is None:
            return None

        record = SourceRecord(
            source=self.name,
            url=url,
            fetched_at=fetched_at,
            model_raw=h1.get_text(" ", strip=True),
        )

        text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))

        # 'Released 1 / 2026 , Low Top , Kyrie Irving , Add to Favourites'
        if m := re.search(r"Released\s+(\d{1,2})\s*/\s*(\d{4})(.*?)Add to Favourites", text):
            record.release_year = int(m.group(2))
            for token in (t.strip() for t in m.group(3).split(",")):
                if not token:
                    continue
                if re.fullmatch(r"(?:Low|Mid|High)\s*Top", token, re.I):
                    record.cut_height = map_cut_height(token)
                elif re.fullmatch(r"[A-Z][\w.'-]+(?: [A-Z][\w.'-]+){1,2}", token):
                    record.signature_player = token

        if m := re.search(r"Official Retail Price:\s*\$\s*([\d.]+)", text):
            record.msrp_usd_cents = parse_usd_cents(m.group(1))

        if m := re.search(r"([\d.]+)\s+EXPERT RATING\s+(\d+)\s+reviews?", text):
            record.scores["overall"] = float(m.group(1))
            record.scores["expert_review_count"] = int(m.group(2))

        for label, (score, comment) in self._category_cards(soup).items():
            key = label.lower()
            if score.endswith("%"):
                record.scores[key] = score
            else:
                try:
                    record.scores[key] = float(score)
                except ValueError:
                    record.scores[key] = score
            record.review_text.append(f"[{key}] {strip_boilerplate(comment)}")
            if label == "Fit":
                record.length_fit = map_length_fit(comment)
            elif label == "Outdoor" and score.endswith("%"):
                pct = float(score.rstrip("%"))
                record.outdoor_suitability = (
                    "good" if pct >= 80 else "fair" if pct >= 55 else "bad"
                )

        # standalone Width block: 'Width | Fits narrow to regular widths best…'
        width_label = soup.find(string=re.compile(r"^\s*Width\s*$"))
        if width_label is not None:
            comment = width_label.parent.find_next_sibling("div")
            if comment is not None:
                width_text = comment.get_text(" ", strip=True)
                record.extras["width_note"] = width_text
                record.width_fit = map_width_fit(width_text)

        if m := re.search(r"Performance Summary\s+(.{30,400}?)\s+Pros\b", text):
            record.review_text.insert(0, f"[summary] {strip_boilerplate(m.group(1))}")

        if m := re.search(r"Best Suitable For:\s*(.{10,300}?\.)(?:\s|$)", text):
            best_for = strip_boilerplate(m.group(1))
            record.extras["best_for"] = best_for
            record.review_text.append(f"[best for] {best_for}")

        record.pros = self._pros_cons(soup, "Pros")
        record.cons = self._pros_cons(soup, "Cons")

        og = soup.find("meta", property="og:image")
        if og is not None and og.get("content"):
            record.image_urls = [og["content"]]

        return record
