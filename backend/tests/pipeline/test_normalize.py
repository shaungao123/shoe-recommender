"""Cleaning + entity-resolution unit tests (no fixtures, no network)."""

from pipeline.normalize import (
    map_cut_height,
    map_length_fit,
    map_playstyles,
    map_positions,
    map_width_fit,
    model_key,
    parse_mm,
    parse_usd_cents,
    parse_weight_oz,
    resolve,
    split_brand,
    strip_boilerplate,
)
from pipeline.schema import SourceRecord


def make_record(**kwargs) -> SourceRecord:
    defaults = dict(source="test", url="http://x", fetched_at="t", model_raw="X")
    defaults.update(kwargs)
    return SourceRecord(**defaults)


# -- units -------------------------------------------------------------


def test_parse_weight_from_oz():
    oz, g = parse_weight_oz("13.9 oz")
    assert oz == 13.9
    assert 393 < g < 395


def test_parse_weight_from_grams():
    oz, g = parse_weight_oz("366g")
    assert g == 366
    assert 12.8 < oz < 13.0


def test_parse_weight_dual_format_prefers_oz():
    oz, _ = parse_weight_oz("12.9 oz / 366g")
    assert oz == 12.9


def test_parse_mm():
    assert parse_mm("8 mm") == 8.0
    assert parse_mm("28.9 mm") == 28.9
    assert parse_mm("no number") is None


def test_parse_usd_cents():
    assert parse_usd_cents("$120") == 12000
    assert parse_usd_cents("129.99") == 12999


# -- enums -------------------------------------------------------------


def test_enum_mappers():
    assert map_cut_height("Low-cut") == "low"
    assert map_cut_height("High Top") == "high"
    assert map_width_fit("Medium") == "standard"
    assert map_width_fit("Fits narrow feet") == "narrow"
    assert map_length_fit("True to size") == "true_to_size"
    assert map_length_fit("Slightly small") == "slightly_small"
    assert map_length_fit("Runs large") == "runs_large"


def test_tag_mappers():
    assert map_positions("PG/SG") == ["guard"]
    assert map_positions("SF, PF") == ["wing", "big"]
    assert map_playstyles("Slasher;Shooter") == ["slasher", "shooter"]


def test_strip_boilerplate():
    text = (
        "Great shoe on court. Some links on this page are affiliate links "
        "and we may earn a commission at no extra cost to you."
    )
    cleaned = strip_boilerplate(text)
    assert "affiliate" not in cleaned
    assert cleaned.startswith("Great shoe on court.")


# -- naming ------------------------------------------------------------


def test_split_brand():
    assert split_brand("Nike G.T. Cut 3") == ("Nike", "G.T. Cut 3")
    assert split_brand("Air Jordan 39") == ("Jordan", "39")
    assert split_brand("Under Armour Curry 12") == ("Under Armour", "Curry 12")
    assert split_brand("Mystery Shoe 5") == (None, "Mystery Shoe 5")


def test_model_key_folds_aliases():
    # the acceptance example: "GT Cut 3" <-> "G.T. Cut 3"
    assert model_key("Nike", "G.T. Cut 3") == model_key("Nike", "GT Cut 3")
    # punctuation and '#' noise
    assert model_key("Adidas", "D.O.N. Issue #6") == model_key("Adidas", "DON Issue 6")
    # roman numerals
    assert model_key("Jordan", "Air Jordan XXXVIII") == model_key("Jordan", "Jordan 38")
    # review-title noise words
    assert model_key("Nike", "KD 19 Performance Review") == model_key("Nike", "KD 19")


# -- resolution --------------------------------------------------------


def test_resolve_merges_across_sources_with_priority_and_provenance():
    bss = make_record(
        source="basketballshoespecs", url="http://bss", model_raw="Nike GT Cut 3",
        brand="Nike", model="GT Cut 3", weight_oz=13.9, cut_height="low",
        scores={},
    )
    rr = make_record(
        source="runrepeat", url="http://rr", model_raw="Nike G.T. Cut 3",
        brand="Nike", weight_oz=13.5, stack_heel_mm=28.0,
        scores={"corescore": 90}, pros=["grips well"],
    )
    report = resolve([bss, rr])
    assert len(report.canonical) == 1
    shoe = report.canonical[0]
    assert shoe.canonical_id == "nike-gt-cut-3"
    assert len(shoe.sources) == 2
    # manufacturer specs win over lab where both exist
    assert shoe.weight_oz == 13.9
    assert shoe.provenance["weight_oz"]["source"] == "basketballshoespecs"
    # fields only one source has still land, with their own provenance
    assert shoe.stack_heel_mm == 28.0
    assert shoe.provenance["stack_heel_mm"]["source"] == "runrepeat"
    # scores stay per-source, never averaged
    assert shoe.metrics == {"runrepeat": {"corescore": 90}}
    assert shoe.pros == [{"source": "runrepeat", "text": "grips well"}]


def test_resolve_distinguishes_versions():
    r1 = make_record(brand="Nike", model="LeBron 21", model_raw="Nike LeBron 21")
    r2 = make_record(brand="Nike", model="LeBron 22", model_raw="Nike LeBron 22")
    report = resolve([r1, r2])
    assert len(report.canonical) == 2
    assert not report.ambiguous  # different versions are not near-misses


def test_resolve_numbers_are_versioning_even_mid_name():
    # non-trailing numbers still distinguish shoes — never flagged as ambiguous
    r1 = make_record(brand="Nike", model="Kobe 4 Protro", model_raw="Nike Kobe 4 Protro")
    r2 = make_record(brand="Nike", model="Kobe 8 Protro", model_raw="Nike Kobe 8 Protro")
    report = resolve([r1, r2])
    assert len(report.canonical) == 2
    assert not report.ambiguous


def test_resolve_unnumbered_vs_numbered_are_different_shoes():
    r1 = make_record(brand="Puma", model="All Pro Nitro", model_raw="Puma All Pro Nitro")
    r2 = make_record(brand="Puma", model="All Pro Nitro 2", model_raw="PUMA All Pro Nitro 2")
    report = resolve([r1, r2])
    assert len(report.canonical) == 2
    assert not report.ambiguous


def test_resolve_flags_near_miss_keys_instead_of_guessing():
    r1 = make_record(brand="Nike", model="Sabrina 2", model_raw="Nike Sabrina 2")
    r2 = make_record(brand="Nike", model="Sabrina II EP", model_raw="Sabrina II EP")
    report = resolve([r1, r2])
    # 'sabrina 2' == 'sabrina 2' after roman/EP folding: exact merge, no flag
    assert len(report.canonical) == 1


def test_resolve_unmatched_without_brand():
    report = resolve([make_record(model_raw="Totally Unknown Shoe 9000")])
    assert not report.canonical
    assert len(report.unmatched) == 1
    assert report.unmatched[0]["reason"] == "no recognizable brand"
