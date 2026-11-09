"use client";
/* eslint-disable @next/next/no-img-element -- catalog sources supply varying remote image hosts */

import Link from "next/link";
import { useEffect, useState } from "react";

import { getShoe, type AttributedExcerpt, type ShoeDetail } from "@/lib/catalog";
import { trackEvent } from "@/lib/api";
import { getAnonymousSessionId } from "@/lib/session";

function ExcerptList({ title, excerpts }: { title: string; excerpts: AttributedExcerpt[] }) {
  if (excerpts.length === 0) return null;
  return <section className="mt-8"><h2 className="mb-3 text-xl font-extrabold">{title}</h2><div className="space-y-3">{excerpts.slice(0, 3).map((excerpt, index) => <blockquote key={`${excerpt.source}-${index}`} className="rounded-xl border-l-4 border-accent bg-white p-4 font-serif text-[15px]/[1.55] text-body"><p>“{excerpt.text}”</p><footer className="mt-2 font-sans text-xs font-bold tracking-[.06em] text-muted uppercase">{excerpt.source}</footer></blockquote>)}</div></section>;
}

export function ShoeDetailView({ id }: { id: number }) {
  const [shoe, setShoe] = useState<ShoeDetail | null>(null);
  const [status, setStatus] = useState<"loading" | "error" | "missing" | "ready">("loading");
  useEffect(() => { const controller = new AbortController(); void getShoe(id, controller.signal).then((result) => { setShoe(result); setStatus("ready"); trackEvent({ session_id: getAnonymousSessionId(), name: "shoe_detail_viewed", properties: { shoe_id: id } }); if (!result.affiliate_url) trackEvent({ session_id: getAnonymousSessionId(), name: "buy_link_unavailable", properties: { shoe_id: id } }); }).catch((error: Error) => setStatus(error.message.includes("404") ? "missing" : "error")); return () => controller.abort(); }, [id]);
  if (status === "loading") return <main className="mx-auto w-full max-w-[900px] px-6 py-12"><div className="h-[500px] animate-pulse rounded-3xl bg-white" /></main>;
  if (status !== "ready" || !shoe) return <main className="mx-auto w-full max-w-[900px] px-6 py-20 text-center"><h1 className="text-3xl font-extrabold">{status === "missing" ? "That shoe isn’t in the catalog." : "We couldn’t load that shoe."}</h1><Link href="/catalog" className="mt-5 inline-block rounded-full bg-ink px-5 py-3 text-sm font-bold text-white">Back to catalog</Link></main>;
  const specs = Object.entries(shoe.specs).filter(([, value]) => value !== null && value !== undefined && value !== "" && (!Array.isArray(value) || value.length));
  const chips = [
    ...shoe.position_tags,
    ...shoe.playstyle_tags,
    shoe.cut_height && `${shoe.cut_height} cut`,
    shoe.cushioning_tech,
  ].filter((item): item is string => Boolean(item));
  return <main className="mx-auto w-full max-w-[1000px] px-6 py-8 pb-20"><Link href="/catalog" className="text-sm font-bold text-muted hover:text-ink">← Back to catalog</Link><div className="mt-6 grid gap-8 lg:grid-cols-[1.05fr_.95fr]">{shoe.image_url ? <img src={shoe.image_url} alt={`${shoe.brand} ${shoe.name}`} className="h-[360px] w-full rounded-3xl bg-paper object-cover" /> : <div className="hatch flex h-[360px] items-center justify-center rounded-3xl text-sm font-bold tracking-[.08em] text-faint uppercase">Catalog image unavailable</div>}<div><p className="text-xs font-bold tracking-[.08em] text-accent uppercase">{shoe.brand}</p><h1 className="mt-2 text-4xl/[1.05] font-extrabold tracking-[-.02em]">{shoe.name}</h1><p className="mt-5 text-2xl font-bold">{shoe.price === null ? "Price unavailable" : `$${Math.round(shoe.price)}`}</p><p className="mt-1 text-sm text-muted">Latest catalog price; price may vary.</p><div className="mt-6 flex flex-wrap gap-2">{chips.map((item) => <span key={item} className="rounded-full bg-white px-3 py-1.5 text-xs font-bold text-muted">{item}</span>)}</div><div className="mt-8 rounded-2xl border border-dashed border-line bg-white p-4 text-center text-sm font-bold text-faint">Buy links coming soon</div></div></div><section className="mt-10 rounded-2xl border border-line bg-white p-6"><h2 className="mb-4 text-xl font-extrabold">Specs</h2><dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2">{specs.map(([key, value]) => <div key={key} className="border-b border-line pb-3"><dt className="text-xs font-bold tracking-[.05em] text-faint uppercase">{key.replaceAll("_", " ")}</dt><dd className="mt-1 text-sm font-semibold text-body">{Array.isArray(value) ? value.join(", ") : String(value)}</dd></div>)}</dl></section><ExcerptList title="What reviewers said" excerpts={shoe.extra_metadata.review_text} /><ExcerptList title="Noted strengths" excerpts={shoe.extra_metadata.pros} /><ExcerptList title="Worth considering" excerpts={shoe.extra_metadata.cons} /></main>;
}
