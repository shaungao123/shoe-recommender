"""Source registry — add new scrapers here and nowhere else."""

from pipeline.scrapers.base import BaseScraper, Fetcher


def get_scrapers() -> dict[str, type[BaseScraper]]:
    # imported lazily so one broken source module can't kill the registry
    from pipeline.scrapers.basketballshoespecs import BasketballShoeSpecsScraper
    from pipeline.scrapers.runrepeat import RunRepeatScraper
    from pipeline.scrapers.thehoopsgeek import TheHoopsGeekScraper
    from pipeline.scrapers.weartesters import WearTestersScraper

    return {
        scraper.name: scraper
        for scraper in (
            BasketballShoeSpecsScraper,
            RunRepeatScraper,
            TheHoopsGeekScraper,
            WearTestersScraper,
        )
    }


__all__ = ["BaseScraper", "Fetcher", "get_scrapers"]
