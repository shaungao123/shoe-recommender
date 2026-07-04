"""Each scraper parsed against saved HTML fixtures — never the network."""

import pytest

from tests.pipeline.conftest import FETCHED_AT, load_fixture

from pipeline.scrapers.basketballshoespecs import BasketballShoeSpecsScraper
from pipeline.scrapers.runrepeat import RunRepeatScraper
from pipeline.scrapers.thehoopsgeek import TheHoopsGeekScraper
from pipeline.scrapers.weartesters import WearTestersScraper


# -- BasketballShoeSpecs -----------------------------------------------


def test_bss_list(fake_fetcher):
    scraper = BasketballShoeSpecsScraper(
        fake_fetcher({"https://www.basketballshoespecs.com/shoes/": "bss_list.html"})
    )
    refs = scraper.list_shoes()
    assert len(refs) > 80
    assert all(ref.url.startswith("https://www.basketballshoespecs.com/shoes/") for ref in refs)
    assert len({ref.url for ref in refs}) == len(refs)  # deduped


def test_bss_parse_specs():
    scraper = BasketballShoeSpecsScraper.__new__(BasketballShoeSpecsScraper)
    record = scraper.parse(load_fixture("bss_detail.html"), "http://x", FETCHED_AT)
    assert record.model_raw == "Nike GT Cut 3"
    assert record.brand == "Nike"
    assert record.release_year == 2024
    assert record.weight_oz == 13.9
    assert record.weight_g == pytest.approx(394.1, abs=0.5)
    assert record.drop_mm == 8.0
    assert record.cut_height == "low"
    assert record.width_fit == "standard"
    assert record.cushioning_tech == "Zoom Air Strobel + ZoomX"
    assert record.traction_pattern == "Multi-Direction"
    assert record.outdoor_suitability == "bad"  # indoor-only surface
    assert record.position_tags == ["guard"]
    assert record.playstyle_tags == ["slasher", "shooter"]
    assert record.extras["price_band"] == "premium"
    assert record.image_urls


def test_bss_parse_signature():
    scraper = BasketballShoeSpecsScraper.__new__(BasketballShoeSpecsScraper)
    record = scraper.parse(load_fixture("bss_detail_ae1.html"), "http://x", FETCHED_AT)
    assert record.signature_player == "Anthony Edwards"


# -- RunRepeat ---------------------------------------------------------


def test_runrepeat_list_paginates(fake_fetcher):
    fetcher = fake_fetcher(
        {"https://runrepeat.com/catalog/basketball-shoes": "rr_list.html"}
    )
    scraper = RunRepeatScraper(fetcher)
    refs = scraper.list_shoes()
    assert len(refs) == 30  # one JSON-LD ItemList page
    assert "https://runrepeat.com/catalog/basketball-shoes?page=2" in fetcher.requested


def test_runrepeat_parse_lab_data():
    scraper = RunRepeatScraper.__new__(RunRepeatScraper)
    record = scraper.parse(load_fixture("rr_detail.html"), "http://x", FETCHED_AT)
    assert record.model_raw == "Adidas D.O.N. Issue #6"
    assert record.brand == "Adidas"
    assert record.signature_player == "Donovan Mitchell"
    assert record.msrp_usd_cents == 12000
    assert record.weight_oz == 12.9
    assert record.drop_mm == 8.0
    assert record.stack_heel_mm == 28.9
    assert record.stack_forefoot_mm == 20.9
    assert record.cut_height == "low"
    assert record.length_fit == "true_to_size"
    assert record.scores["corescore"] == 94
    assert record.scores["traction_test"] == "0.99"  # traction CoF
    assert record.scores["score_outdoor"] == 64
    assert record.pros and record.cons
    assert any(seg.startswith("[our verdict]") for seg in record.review_text)


# -- The Hoops Geek ----------------------------------------------------


def test_thg_list_paginates(fake_fetcher):
    fetcher = fake_fetcher({"https://www.thehoopsgeek.com/shoe-reviews/": "thg_list.html"})
    scraper = TheHoopsGeekScraper(fetcher)
    refs = scraper.list_shoes()
    assert len(refs) > 20
    assert "https://www.thehoopsgeek.com/shoe-reviews/?pg=2" in fetcher.requested


def test_thg_parse_aggregated_scores():
    scraper = TheHoopsGeekScraper.__new__(TheHoopsGeekScraper)
    record = scraper.parse(load_fixture("thg_detail.html"), "http://x", FETCHED_AT)
    assert record.model_raw == "ANTA KAI 3"
    assert record.release_year == 2026
    assert record.signature_player == "Kyrie Irving"
    assert record.msrp_usd_cents == 13500
    assert record.cut_height == "low"
    assert record.length_fit == "true_to_size"
    assert record.outdoor_suitability == "fair"  # 75%
    assert record.scores["overall"] == 8.6
    assert record.scores["expert_review_count"] == 6
    assert record.scores["traction"] == 8.8
    assert record.scores["support"] == 9.1
    assert record.pros and record.cons
    assert any(seg.startswith("[summary]") for seg in record.review_text)
    assert "best_for" in record.extras


# -- WearTesters -------------------------------------------------------


def test_wt_list_records_category_tags(fake_fetcher):
    url = "https://weartesters.com/category/performance-reviews/basketball-shoes-reviews/"
    fetcher = fake_fetcher({url: "wt_list.html"})
    scraper = WearTestersScraper(fetcher)
    refs = scraper.list_shoes()
    assert len(refs) > 20
    tagged = [u for u, tags in scraper._listing_tags.items() if "outdoor" in tags]
    assert tagged  # listing classes captured for parse()


def test_wt_parse_review_prose():
    scraper = WearTestersScraper.__new__(WearTestersScraper)
    scraper._listing_tags = {"http://x": ["low-top", "outdoor"]}
    record = scraper.parse(load_fixture("wt_detail.html"), "http://x", FETCHED_AT)
    assert record.model_raw == "Nike Kobe 3 Low Protro"
    assert record.release_year == 2026
    assert record.msrp_usd_cents == 18000
    assert record.length_fit == "true_to_size"
    assert record.cut_height == "low"
    assert record.outdoor_suitability == "good"
    assert record.scores["reviewer_score"] == 7.0
    assert record.extras["reviewer"] == "Drew"
    assert record.pros and record.cons
    sections = {seg.split("]")[0].lstrip("[") for seg in record.review_text}
    assert {"traction", "cushion", "materials", "fit", "support", "summary"} <= sections
    # disclosure/affiliate boilerplate never reaches the corpus
    assert not any("affiliate" in seg.lower() for seg in record.review_text)
    assert not any("purchased a pair" in seg.lower() for seg in record.review_text)
