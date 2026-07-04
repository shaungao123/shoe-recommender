"""WearTesters — long-form performance reviews (best prose for embedding).

WordPress. Listing = category archive with classic /page/N/ pagination; the
listing cards carry taxonomy classes (low-top / outdoor / budget / brand)
that the detail page does not expose, so ``list_shoes`` records them per URL
for ``parse`` to pick up. Detail = Gutenberg blocks: meta line (release /
price / sizing), Pros & Cons columns, one h2 section per test category, a
reviewer verdict ("Drew 7/10 Total Score"), and a Disclosure section we drop.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from pipeline.normalize import (
    map_cut_height,
    map_length_fit,
    parse_usd_cents,
    strip_boilerplate,
)
from pipeline.schema import SourceRecord
from pipeline.scrapers.base import BaseScraper, ShoeRef

LISTING_URL = "https://weartesters.com/category/performance-reviews/basketball-shoes-reviews/"
MAX_LISTING_PAGES = 40

_SECTION_TITLES = {
    "traction", "cushion", "cushioning", "materials", "material", "fit",
    "support", "summary", "overall", "performance",
}

# listing-card category classes worth keeping
_TAG_CLASSES = {
    "category-low-top-basketball-shoes": "low-top",
    "category-high-top-basketball-shoes": "high-top",
    "category-outdoor-basketball-shoes": "outdoor",
    "category-budget-basketball-shoes": "budget",
    "category-retro-shoe-reviews": "retro",
}


def _clean_title(title: str) -> str:
    return re.sub(r"\s*performance review\s*$|\s*review\s*$", "", title, flags=re.I).strip()


class WearTestersScraper(BaseScraper):
    name = "weartesters"
    base_url = "https://weartesters.com"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._listing_tags: dict[str, list[str]] = {}

    def list_shoes(self) -> list[ShoeRef]:
        refs: list[ShoeRef] = []
        seen: set[str] = set()
        for page in range(1, MAX_LISTING_PAGES + 1):
            url = LISTING_URL if page == 1 else f"{LISTING_URL}page/{page}/"
            result = self.fetcher.get(self.name, url)
            if result is None:  # 404 past the last page
                break
            soup = BeautifulSoup(result.text, "lxml")
            new = 0
            for article in soup.find_all("article"):
                link = article.select_one("h2 a[href], h3 a[href], .cs-entry__title a[href]")
                if link is None:
                    continue
                full = urljoin(self.base_url, link["href"])
                if full in seen:
                    continue
                seen.add(full)
                classes = article.get("class", [])
                tags = [tag for cls, tag in _TAG_CLASSES.items() if cls in classes]
                self._listing_tags[full] = tags
                refs.append(ShoeRef(name=link.get_text(" ", strip=True), url=full))
                new += 1
            if new == 0:
                break
        return refs

    def parse(self, html: str, url: str, fetched_at: str) -> SourceRecord | None:
        soup = BeautifulSoup(html, "lxml")
        h1 = soup.find("h1")
        content = soup.select_one(".entry-content")
        if h1 is None or content is None:
            return None

        record = SourceRecord(
            source=self.name,
            url=url,
            fetched_at=fetched_at,
            model_raw=_clean_title(h1.get_text(" ", strip=True)),
        )

        text = re.sub(r"\s+", " ", content.get_text(" ", strip=True))

        if m := re.search(r"Release Date:\s*(\d{1,2})/(\d{1,2})/(\d{4})", text):
            record.release_year = int(m.group(3))
        if m := re.search(r"Price:\s*\$\s*([\d.]+)", text):
            record.msrp_usd_cents = parse_usd_cents(m.group(1))
        if m := re.search(r"Sizing:\s*([^.$]{3,40}?)(?:\s+Buy|\s+Pros|\s*$)", text):
            record.length_fit = map_length_fit(m.group(1))
            record.extras["sizing_note"] = m.group(1).strip()

        # reviewer verdict: "<name> 7 / 10 Total Score"
        if m := re.search(
            r"([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+){0,2})\s+(\d+(?:\.\d+)?)\s*/\s*10\s+Total Score",
            text,
        ):
            record.scores["reviewer_score"] = float(m.group(2))
            record.extras["reviewer"] = m.group(1).strip()

        # Pros / Cons columns (h4 + ul)
        for which, target in (("pros", record.pros), ("cons", record.cons)):
            heading = content.find(
                lambda tag: tag.name in ("h3", "h4")
                and tag.get_text(strip=True).lower() == which
            )
            if heading is not None:
                ul = heading.find_next("ul")
                if ul is not None:
                    target.extend(li.get_text(" ", strip=True) for li in ul.find_all("li"))

        # prose: intro paragraphs, then one segment per h2 test section
        segments: list[tuple[str, list[str]]] = [("intro", [])]
        for node in content.children:
            name = getattr(node, "name", None)
            if name == "h2":
                title = node.get_text(" ", strip=True)
                key = title.lower()
                if "summary" in key:
                    key = "summary"
                elif key not in _SECTION_TITLES:
                    key = ""  # shoe-name heading, disclosure, etc. → skip
                segments.append((key, []))
            elif name == "p" and segments[-1][0]:
                segments[-1][1].append(node.get_text(" ", strip=True))
        for key, paragraphs in segments:
            body = strip_boilerplate(" ".join(p for p in paragraphs if p))
            if body and len(body) > 40:
                record.review_text.append(f"[{key}] {body}")

        # taxonomy tags recorded from the listing card
        tags = self._listing_tags.get(url, [])
        if tags:
            record.extras["categories"] = tags
        if "low-top" in tags:
            record.cut_height = "low"
        elif "high-top" in tags:
            record.cut_height = "high"
        if "outdoor" in tags:
            record.outdoor_suitability = "good"

        # cut height stated in the model name beats the listing tag
        if m := re.search(r"\b(low|mid|high)\b", record.model_raw, re.I):
            record.cut_height = map_cut_height(m.group(1))

        og = soup.find("meta", property="og:image")
        if og is not None and og.get("content"):
            record.image_urls = [og["content"]]

        return record
