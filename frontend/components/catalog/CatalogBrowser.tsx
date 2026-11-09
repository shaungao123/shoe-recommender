"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { CatalogCard } from "@/components/catalog/CatalogCard";
import { CATALOG_SORT_OPTIONS, catalogFiltersFromUrl, catalogUrlQuery, EMPTY_CATALOG_FILTERS, getCatalog, rememberCatalogView, type CatalogFilters, type CatalogShoe } from "@/lib/catalog";
import { trackEvent } from "@/lib/api";
import { getAnonymousSessionId } from "@/lib/session";

const PAGE_SIZE = 24;
const MAX_RESTORED_SHOES = 100; // API limit for a single request
const SEARCH_DEBOUNCE_MS = 300;
const OPTIONS = {
  brand: ["Nike", "Jordan", "Adidas", "Li-Ning", "Under Armour", "Puma", "Anta", "New Balance", "361 Degrees", "Converse", "Reebok", "Peak", "Asics", "Xtep"],
  position: ["guard", "wing", "big"],
  playstyle: ["all-around", "slasher", "shooter"], // only tags the corpus has today
  outdoor: ["good", "fair", "bad"],
  cut: ["low", "mid", "high"],
  width: ["narrow", "standard", "wide"],
};

const label = (value: string) => (value === "bad" ? "not recommended" : value.replaceAll("-", " "));

function SelectFilter({ title, value, options, onChange }: { title: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return <label className="block text-xs font-bold tracking-[.05em] text-muted uppercase"><span className="mb-2 block">{title}</span><select value={value} onChange={(event) => onChange(event.target.value)} className="w-full rounded-xl border border-line bg-white px-3 py-2.5 text-sm font-medium text-ink normal-case outline-none focus:border-ink"><option value="">Any</option>{options.map((option) => <option key={option} value={option}>{label(option)}</option>)}</select></label>;
}

export function CatalogBrowser() {
  const searchParams = useSearchParams();
  const [filters, setFilters] = useState<CatalogFilters>(() => catalogFiltersFromUrl(searchParams));
  const [searchText, setSearchText] = useState(filters.query);
  const [shoes, setShoes] = useState<CatalogShoe[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(false);
  const hasTrackedView = useRef(false);
  const activeRequest = useRef<AbortController | null>(null);
  // First load after returning from a shoe page refetches everything that was shown.
  const restoreCount = useRef(
    Math.min(Number(searchParams.get("shown")) || PAGE_SIZE, MAX_RESTORED_SHOES),
  );

  const load = useCallback(async (offset = 0, append = false, limit = PAGE_SIZE) => {
    // Only the newest request may update the page; slower older ones are dropped.
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setLoading(!append);
    setLoadingMore(append);
    setError(false);
    try {
      const result = await getCatalog(filters, offset, limit, controller.signal);
      setShoes((current) =>
        append ? [...current, ...result.items] : result.items,
      );
      setTotal(result.total);
    } catch {
      if (!controller.signal.aborted) setError(true);
    } finally {
      if (activeRequest.current === controller) {
        setLoading(false);
        setLoadingMore(false);
      }
    }
  }, [filters]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load(0, false, restoreCount.current);
      restoreCount.current = PAGE_SIZE;
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setFilters((current) => (current.query === searchText ? current : { ...current, query: searchText }));
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [searchText]);
  useEffect(() => {
    const query = catalogUrlQuery(filters, shoes.length, PAGE_SIZE);
    window.history.replaceState(null, "", query ? `?${query}` : window.location.pathname);
    rememberCatalogView(query);
  }, [filters, shoes.length]);
  useEffect(() => {
    if (!hasTrackedView.current) {
      hasTrackedView.current = true;
      trackEvent({ session_id: getAnonymousSessionId(), name: "catalog_viewed" });
      return;
    }
    const timer = window.setTimeout(() => {
      const activeFilters = Object.values(filters).filter(Boolean).length - 1;
      trackEvent({
        session_id: getAnonymousSessionId(),
        name: "catalog_filtered",
        properties: { active_filter_count: activeFilters, sort: filters.sort },
      });
    }, 500);
    return () => window.clearTimeout(timer);
  }, [filters]);
  const update = (key: keyof CatalogFilters, value: string) => setFilters((current) => ({ ...current, [key]: value }));
  const clear = () => {
    setSearchText("");
    setFilters(EMPTY_CATALOG_FILTERS);
  };

  return <main className="mx-auto w-full max-w-[1180px] px-6 py-8 pb-20">
    <div className="mb-8 flex flex-wrap items-end justify-between gap-5">
      <div><p className="mb-2 text-xs font-bold tracking-[.08em] text-accent uppercase">The Assist catalog</p><h1 className="text-4xl font-extrabold tracking-[-.02em]">Find the right starting point.</h1><p className="mt-2 max-w-2xl font-serif text-base text-muted">Browse the shoes in our review-backed catalog. Prices may vary.</p></div>
      <button type="button" onClick={clear} className="rounded-full border border-line px-4 py-2 text-sm font-semibold hover:border-ink">Clear filters</button>
    </div>
    <div className="mb-8 grid gap-4 rounded-2xl border border-line bg-[#eeece6] p-4 sm:grid-cols-2 lg:grid-cols-4">
      <label className="sm:col-span-2 lg:col-span-2 text-xs font-bold tracking-[.05em] text-muted uppercase"><span className="mb-2 block">Search</span><input value={searchText} onChange={(event) => setSearchText(event.target.value)} placeholder="Shoe name or brand" className="w-full rounded-xl border border-line bg-white px-3 py-2.5 text-sm font-medium normal-case outline-none focus:border-ink" /></label>
      <label className="block text-xs font-bold tracking-[.05em] text-muted uppercase"><span className="mb-2 block">Maximum price</span><input type="number" min="0" value={filters.budgetMax} onChange={(event) => update("budgetMax", event.target.value)} placeholder="Any price" className="w-full rounded-xl border border-line bg-white px-3 py-2.5 text-sm font-medium normal-case outline-none focus:border-ink" /></label>
      <label className="block text-xs font-bold tracking-[.05em] text-muted uppercase"><span className="mb-2 block">Sort</span><select value={filters.sort} onChange={(event) => update("sort", event.target.value)} className="w-full rounded-xl border border-line bg-white px-3 py-2.5 text-sm font-medium normal-case outline-none focus:border-ink">{CATALOG_SORT_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
      <SelectFilter title="Brand" value={filters.brand} options={OPTIONS.brand} onChange={(value) => update("brand", value)} />
      <SelectFilter title="Position" value={filters.position} options={OPTIONS.position} onChange={(value) => update("position", value)} />
      <SelectFilter title="Playstyle" value={filters.playstyle} options={OPTIONS.playstyle} onChange={(value) => update("playstyle", value)} />
      <SelectFilter title="Outdoor use" value={filters.outdoor} options={OPTIONS.outdoor} onChange={(value) => update("outdoor", value)} />
      <SelectFilter title="Cut" value={filters.cut} options={OPTIONS.cut} onChange={(value) => update("cut", value)} />
      <SelectFilter title="Width" value={filters.width} options={OPTIONS.width} onChange={(value) => update("width", value)} />
    </div>
    <div className="mb-5 flex items-center justify-between"><h2 className="text-xl font-extrabold">{loading ? "Loading catalog…" : `${total} shoe${total === 1 ? "" : "s"}`}</h2></div>
    {error ? <div className="rounded-2xl border border-line bg-white p-8 text-center"><p className="font-serif text-muted">We couldn’t load the catalog right now.</p><button type="button" onClick={() => void load()} className="mt-4 rounded-full bg-ink px-5 py-2.5 text-sm font-bold text-white">Try again</button></div> : loading ? <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">{Array.from({ length: 6 }, (_, index) => <div key={index} className="h-[335px] animate-pulse rounded-2xl border border-line bg-white" />)}</div> : shoes.length === 0 ? <div className="rounded-2xl border border-line bg-white p-10 text-center"><h2 className="text-xl font-extrabold">No shoes match those filters.</h2><p className="mt-2 font-serif text-muted">Try a higher budget or remove a filter to widen the search.</p><button type="button" onClick={clear} className="mt-5 rounded-full bg-ink px-5 py-2.5 text-sm font-bold text-white">Clear filters</button></div> : <><div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">{shoes.map((shoe) => <CatalogCard key={shoe.id} shoe={shoe} />)}</div>{shoes.length < total && <div className="mt-9 text-center"><button type="button" disabled={loadingMore} onClick={() => void load(shoes.length, true)} className="rounded-full border border-ink px-6 py-3 text-sm font-bold disabled:opacity-50">{loadingMore ? "Loading…" : "Show more shoes"}</button></div>}</>}
  </main>;
}
