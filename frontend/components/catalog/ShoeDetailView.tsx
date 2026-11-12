"use client";
/* eslint-disable @next/next/no-img-element -- catalog sources supply varying remote image hosts */

import Link from "next/link";
import { useEffect, useState } from "react";

import { ScoreBar } from "@/components/catalog/ScoreBar";
import { VerdictBox } from "@/components/catalog/VerdictBox";
import { SaveShoeButton } from "@/components/SaveShoeButton";
import {
  catalogReturnPath,
  getShoe,
  reviewHighlights,
  sourceName,
  type AttributedExcerpt,
  type ShoeDetail,
  type SourceLink,
} from "@/lib/catalog";
import { trackEvent } from "@/lib/api";
import { getAnonymousSessionId } from "@/lib/session";
import { shopLink } from "@/lib/shop";

const MAX_PROS_CONS = 5;
const OUTBOUND_REL = "noopener noreferrer";

const humanize = (value: unknown) => {
  const text = String(value).replaceAll("_", " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
};
const withUnit = (unit: string) => (value: unknown) => `${value} ${unit}`;
const OUTDOOR_LABELS: Record<string, string> = { good: "Good", fair: "Fair", bad: "Not recommended" };

const SPEC_ROWS: { key: string; label: string; format?: (value: unknown) => string }[] = [
  { key: "release_year", label: "Released", format: String },
  { key: "signature_player", label: "Signature player", format: String },
  { key: "weight_oz", label: "Weight", format: withUnit("oz") },
  { key: "cut_height", label: "Cut" },
  { key: "width_fit", label: "Width" },
  { key: "length_fit", label: "Length" },
  { key: "cushioning_tech", label: "Cushioning", format: String },
  { key: "traction_pattern", label: "Traction pattern", format: String },
  { key: "outdoor_suitability", label: "Outdoor use", format: (value) => OUTDOOR_LABELS[String(value)] ?? humanize(value) },
  { key: "drop_mm", label: "Heel-to-toe drop", format: withUnit("mm") },
  { key: "stack_heel_mm", label: "Heel stack", format: withUnit("mm") },
  { key: "stack_forefoot_mm", label: "Forefoot stack", format: withUnit("mm") },
];

function SourceCredit({ source, links }: { source: string; links: SourceLink[] }) {
  const url = links.find((link) => link.source === source)?.url;
  const name = sourceName(source);
  return url ? <a href={url} target="_blank" rel={OUTBOUND_REL} className="underline underline-offset-2 hover:text-ink">{name}</a> : <>{name}</>;
}

function ReviewHighlights({ excerpts, links }: { excerpts: AttributedExcerpt[]; links: SourceLink[] }) {
  if (excerpts.length === 0) return null;
  return (
    <section className="mt-8">
      <h2 className="mb-3 text-xl font-extrabold">What reviewers said</h2>
      <div className="space-y-3">
        {excerpts.map((excerpt) => (
          <blockquote key={excerpt.source} className="rounded-xl border-l-4 border-accent bg-white p-4 font-serif text-[15px]/[1.55] text-body">
            <p>“{excerpt.text}”</p>
            <footer className="mt-2 font-sans text-xs font-bold text-muted">
              <SourceCredit source={excerpt.source} links={links} />
            </footer>
          </blockquote>
        ))}
      </div>
    </section>
  );
}

function ProsCons({ title, items }: { title: string; items: AttributedExcerpt[] }) {
  const seen = new Set<string>();
  const unique = items.filter(({ text }) => {
    const key = text.trim().toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  if (unique.length === 0) return null;
  return (
    <div className="rounded-2xl border border-line bg-white p-5">
      <h2 className="mb-3 text-lg font-extrabold">{title}</h2>
      <ul className="space-y-2.5">
        {unique.slice(0, MAX_PROS_CONS).map((item) => (
          <li key={item.text} className="text-sm/[1.45] text-body">
            {item.text} <span className="text-xs font-semibold whitespace-nowrap text-faint">{sourceName(item.source)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Scorecard({ shoe }: { shoe: ShoeDetail }) {
  const { scores } = shoe;
  const corescore = shoe.extra_metadata.metrics.runrepeat?.corescore;
  const reviewerScore = shoe.extra_metadata.metrics.weartesters?.reviewer_score;
  const others = [
    typeof corescore === "number" && { label: "RunRepeat CoreScore", value: `${corescore} / 100` },
    typeof reviewerScore === "number" && { label: "WearTesters reviewer score", value: `${reviewerScore} / 10` },
  ].filter((item): item is { label: string; value: string } => Boolean(item));
  if (!scores && others.length === 0) return null;
  return (
    <section className="mt-10 rounded-2xl border border-line bg-white p-6">
      <h2 className="mb-5 text-xl font-extrabold">How it scores</h2>
      {scores && (
        <div className="grid gap-6 sm:grid-cols-[auto_1fr] sm:gap-10">
          {scores.overall !== null && (
            <div>
              <div className="text-5xl/none font-extrabold tracking-[-.02em] tabular-nums">{scores.overall.toFixed(1)}</div>
              <div className="mt-2 text-xs font-semibold text-muted">
                out of 10
                {scores.expert_review_count ? <><br />{scores.expert_review_count} expert review{scores.expert_review_count === 1 ? "" : "s"}</> : null}
              </div>
            </div>
          )}
          <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
            <ScoreBar label="Traction" value={scores.traction} />
            <ScoreBar label="Cushion" value={scores.cushion} />
            <ScoreBar label="Support" value={scores.support} />
            <ScoreBar label="Fit" value={scores.fit} />
            <ScoreBar label="Materials" value={scores.materials} />
            <ScoreBar label="Outdoor durability" value={scores.outdoor_pct} max={100} suffix="%" />
          </div>
        </div>
      )}
      {others.length > 0 && (
        <dl className={`flex flex-wrap gap-x-10 gap-y-3 ${scores ? "mt-6 border-t border-line pt-4" : ""}`}>
          {others.map((item) => (
            <div key={item.label}>
              <dt className="text-xs font-semibold text-muted">{item.label}</dt>
              <dd className="mt-1 text-lg/none font-extrabold tabular-nums">{item.value}</dd>
            </div>
          ))}
        </dl>
      )}
      {scores && (
        <p className="mt-5 text-xs text-muted">
          Ratings from <SourceCredit source={scores.source} links={shoe.extra_metadata.sources} />. Other reviewers use their own scales, so their scores are shown separately.
        </p>
      )}
    </section>
  );
}

export function ShoeDetailView({ id }: { id: number }) {
  const [shoe, setShoe] = useState<ShoeDetail | null>(null);
  const [status, setStatus] = useState<"loading" | "error" | "missing" | "ready">("loading");
  const [backHref, setBackHref] = useState("/catalog");

  useEffect(() => {
    const controller = new AbortController();
    void getShoe(id, controller.signal)
      .then((result) => {
        setShoe(result);
        setBackHref(catalogReturnPath());
        setStatus("ready");
        trackEvent({ session_id: getAnonymousSessionId(), name: "shoe_detail_viewed", properties: { shoe_id: id } });
      })
      .catch((error: Error) => {
        if (!controller.signal.aborted) setStatus(error.message.includes("404") ? "missing" : "error");
      });
    return () => controller.abort();
  }, [id]);

  if (status === "loading") {
    return <main className="mx-auto w-full max-w-[900px] px-6 py-12"><div className="h-[500px] animate-pulse rounded-3xl bg-white" /></main>;
  }
  if (status !== "ready" || !shoe) {
    return (
      <main className="mx-auto w-full max-w-[900px] px-6 py-20 text-center">
        <h1 className="text-3xl font-extrabold">{status === "missing" ? "That shoe isn’t in the catalog." : "We couldn’t load that shoe."}</h1>
        <Link href="/catalog" className="mt-5 inline-block rounded-full bg-ink px-5 py-3 text-sm font-bold text-white">Back to catalog</Link>
      </main>
    );
  }

  const specValues = shoe.specs;
  const specs = SPEC_ROWS.filter(({ key }) => specValues[key] !== null && specValues[key] !== undefined && specValues[key] !== "");
  const chips = [...shoe.position_tags, ...shoe.playstyle_tags];
  const sources = shoe.extra_metadata.sources.filter((link, index, all) => all.findIndex((other) => other.url === link.url) === index);

  return (
    <main className="mx-auto w-full max-w-[1000px] px-6 py-8 pb-20">
      <Link href={backHref} className="text-sm font-bold text-muted hover:text-ink">← Back to catalog</Link>
      <div className="mt-6 grid gap-8 lg:grid-cols-[1.05fr_.95fr]">
        {shoe.image_url ? (
          <img src={shoe.image_url} alt={`${shoe.brand} ${shoe.name}`} className="h-[360px] w-full rounded-3xl bg-white object-contain p-6" />
        ) : (
          <div className="hatch flex h-[360px] items-center justify-center rounded-3xl text-sm font-bold tracking-[.08em] text-faint uppercase">Catalog image unavailable</div>
        )}
        <div>
          <p className="text-xs font-bold tracking-[.08em] text-accent uppercase">{shoe.brand}</p>
          <h1 className="mt-2 text-4xl/[1.05] font-extrabold tracking-[-.02em]">{shoe.name}</h1>
          <p className="mt-5 text-2xl font-bold">{shoe.price === null ? "Price unavailable" : `$${Math.round(shoe.price)}`}</p>
          <p className="mt-1 text-sm text-muted">Latest catalog price; price may vary.</p>
          <div className="mt-6 flex flex-wrap gap-2">
            {chips.map((item) => <span key={item} className="rounded-full bg-white px-3 py-1.5 text-xs font-bold text-muted">{item}</span>)}
          </div>
          <VerdictBox shoeId={shoe.id} />
          <div className="mt-6">
            <SaveShoeButton shoeId={shoe.id} />
          </div>
          {(() => {
            const shop = shopLink(shoe.brand, shoe.name, shoe.affiliate_url);
            return (
              <a
                href={shop.href}
                target="_blank"
                rel={shop.rel}
                onClick={() => trackEvent({ session_id: getAnonymousSessionId(), name: "buy_link_intent", properties: { shoe_id: id, has_affiliate_link: shop.isAffiliate } })}
                className="mt-4 block rounded-full bg-accent p-4 text-center text-sm font-bold text-white transition-colors hover:bg-accent-deep"
              >
                {shop.label}
              </a>
            );
          })()}
        </div>
      </div>

      <Scorecard shoe={shoe} />
      <ReviewHighlights excerpts={reviewHighlights(shoe.extra_metadata.review_text)} links={shoe.extra_metadata.sources} />

      {(shoe.extra_metadata.pros.length > 0 || shoe.extra_metadata.cons.length > 0) && (
        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          <ProsCons title="Strengths" items={shoe.extra_metadata.pros} />
          <ProsCons title="Worth considering" items={shoe.extra_metadata.cons} />
        </div>
      )}

      {specs.length > 0 && (
        <section className="mt-8 rounded-2xl border border-line bg-white p-6">
          <h2 className="mb-4 text-xl font-extrabold">Specs</h2>
          <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
            {specs.map(({ key, label, format = humanize }) => (
              <div key={key} className="border-b border-line pb-3">
                <dt className="text-xs font-bold tracking-[.05em] text-faint uppercase">{label}</dt>
                <dd className="mt-1 text-sm font-semibold text-body">{format(specValues[key])}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {sources.length > 0 && (
        <p className="mt-8 text-sm text-muted">
          Read the full reviews:{" "}
          {sources.map((link, index) => (
            <span key={link.url}>
              {index > 0 && " · "}
              <a href={link.url} target="_blank" rel={OUTBOUND_REL} className="font-semibold underline underline-offset-2 hover:text-ink">{sourceName(link.source)}</a>
            </span>
          ))}
        </p>
      )}
    </main>
  );
}
