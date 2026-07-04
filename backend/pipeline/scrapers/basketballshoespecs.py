"""BasketballShoeSpecs — manufacturer-published structured specs.

Cleanest source (~100 shoes): one ``table.spec-table`` of th/td rows per
shoe. No MSRP in body copy, only a price band; live prices come from the
affiliate feed later, so we keep the band in ``extras``.
"""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from pipeline.normalize import (
    parse_mm,
    parse_weight_oz,
    map_cut_height,
    map_width_fit,
    map_positions,
    map_playstyles,
)
from pipeline.schema import SourceRecord
from pipeline.scrapers.base import BaseScraper, ShoeRef


def _map_surface(surface: str) -> str | None:
    """BSS rates the intended surface; translate to outdoor suitability."""
    s = surface.lower()
    has_outdoor = "outdoor" in s
    has_indoor = "indoor" in s
    if has_outdoor and not has_indoor:
        return "good"
    if has_outdoor and has_indoor:
        return "fair"
    if has_indoor:
        return "bad"
    return None


class BasketballShoeSpecsScraper(BaseScraper):
    name = "basketballshoespecs"
    base_url = "https://www.basketballshoespecs.com"

    def list_shoes(self) -> list[ShoeRef]:
        listing_url = f"{self.base_url}/shoes/"
        result = self.fetcher.get(self.name, listing_url)
        if result is None:
            return []
        soup = BeautifulSoup(result.text, "lxml")
        refs: list[ShoeRef] = []
        seen: set[str] = set()
        for card in soup.select("article"):
            link = card.select_one("h3 a[href]")
            if link is None:
                continue
            url = urljoin(self.base_url, link["href"])
            if url in seen or url.rstrip("/").endswith("/shoes"):
                continue
            seen.add(url)
            refs.append(ShoeRef(name=link.get_text(strip=True), url=url))
        return refs

    def parse(self, html: str, url: str, fetched_at: str) -> SourceRecord | None:
        soup = BeautifulSoup(html, "lxml")
        table = soup.select_one("table.spec-table")
        h1 = soup.find("h1")
        if table is None or h1 is None:
            return None

        specs: dict[str, str] = {}
        for row in table.select("tr"):
            th, td = row.find("th"), row.find("td")
            if th and td:
                specs[th.get_text(strip=True).lower()] = td.get_text(strip=True)

        record = SourceRecord(
            source=self.name,
            url=url,
            fetched_at=fetched_at,
            model_raw=h1.get_text(strip=True),
            brand=specs.get("brand"),
            model=specs.get("model"),
            signature_player=specs.get("signature"),
            cushioning_tech=specs.get("cushioning"),
            traction_pattern=specs.get("traction"),
        )

        if year := specs.get("year"):
            if year.isdigit():
                record.release_year = int(year)
        if weight := specs.get("weight"):
            record.weight_oz, record.weight_g = parse_weight_oz(weight)
        if drop := specs.get("drop"):
            record.drop_mm = parse_mm(drop)
        if cut := specs.get("cut height"):
            record.cut_height = map_cut_height(cut)
        if width := specs.get("width fit"):
            record.width_fit = map_width_fit(width)
        if surface := specs.get("surface"):
            record.outdoor_suitability = _map_surface(surface)
            record.extras["surface"] = surface
        if positions := specs.get("best position"):
            record.position_tags = map_positions(positions)
            record.extras["positions_raw"] = positions
        if styles := specs.get("best play style"):
            record.playstyle_tags = map_playstyles(styles)
        if band := specs.get("price band"):
            record.extras["price_band"] = band.lower()

        hero = soup.select_one("main img[src]")
        if hero is not None:
            record.image_urls = [urljoin(self.base_url, hero["src"])]

        # "Build notes" is colorway/build trivia, not review prose.
        for heading in soup.find_all("h2"):
            if "build notes" in heading.get_text(strip=True).lower():
                para = heading.find_next("p")
                if para is not None:
                    record.extras["build_notes"] = para.get_text(strip=True)
                break

        return record
