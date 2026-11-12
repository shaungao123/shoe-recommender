"use client";

import Link from "next/link";
import { useState } from "react";

import { SaveShoeButton } from "@/components/SaveShoeButton";
import { isMockApi } from "@/lib/api";
import { shopLink } from "@/lib/shop";
import type { FeedbackReason, FeedbackVote, RecommendedShoe } from "@/lib/types";

interface ShoeCardProps {
  shoe: RecommendedShoe;
  isTop: boolean;
  vote: FeedbackVote | null;
  onVote: (vote: FeedbackVote, details?: { reason?: FeedbackReason; comment?: string }) => void;
  onBuyIntent: () => void;
}

const DOWNVOTE_REASONS: { value: FeedbackReason; label: string }[] = [
  { value: "not_my_playstyle", label: "Doesn’t fit my game" },
  { value: "too_expensive", label: "Too expensive" },
  { value: "not_my_style", label: "Not my style" },
  { value: "fit_or_comfort", label: "Fit or comfort concern" },
  { value: "other", label: "Something else" },
];

function formatPrice(price: number | null): string {
  return price !== null ? `$${Math.round(price)}` : "—";
}

export function ShoeCard({ shoe, isTop, vote, onVote, onBuyIntent }: ShoeCardProps) {
  const [showFeedbackForm, setShowFeedbackForm] = useState(false);
  const [reason, setReason] = useState<FeedbackReason | null>(null);
  const [comment, setComment] = useState("");
  const shop = shopLink(shoe.brand, shoe.model, shoe.affiliate_url);

  const submitDownvote = () => {
    if (!reason) return;
    onVote("down", { reason, comment: comment.trim() || undefined });
    setShowFeedbackForm(false);
  };

  return (
    <div
      className={`relative flex flex-col overflow-hidden rounded-[18px] border border-line bg-white ${
        isTop
          ? "lg:-translate-y-2.5 shadow-[0_24px_48px_rgba(0,0,0,.14)]"
          : "shadow-[0_4px_14px_rgba(0,0,0,.05)]"
      }`}
    >
      {isTop && (
        <div className="absolute top-4 left-4 z-[2] rounded-full bg-accent px-[13px] py-2 text-[11px]/none font-bold tracking-[.06em] text-white uppercase">
          Top Pick
        </div>
      )}

      {shoe.image_url ? (
        // eslint-disable-next-line @next/next/no-img-element -- remote image domains aren't known ahead of time
        <img
          src={shoe.image_url}
          alt={`${shoe.brand} ${shoe.model}`}
          className="h-[260px] w-full bg-white object-contain p-4"
        />
      ) : (
        <div className="flex h-[260px] flex-col items-center justify-center gap-2.5 bg-ink">
          <div className="flex size-[52px] items-center justify-center rounded-full border-2 border-[#444038] text-lg/none font-bold text-paper">
            {shoe.brand.charAt(0)}
          </div>
          <div className="text-[11px]/none font-medium tracking-[.04em] text-[#7a7568] uppercase">
            Photo coming soon
          </div>
        </div>
      )}

      <div className="flex flex-1 flex-col px-5 pt-[22px] pb-6">
        <div className="mb-1.5 text-[11px]/none font-bold tracking-[.07em] text-accent uppercase">
          {shoe.brand}
        </div>
        <div className="mb-3.5 flex items-baseline justify-between gap-2.5">
          <div className="text-[21px]/tight font-extrabold tracking-[-.01em] text-ink">
            {shoe.model}
          </div>
          <div className="text-base/none font-bold whitespace-nowrap text-ink">
            {formatPrice(shoe.price)}
          </div>
        </div>

        {shoe.match_reasons && shoe.match_reasons.length > 0 && (
          <ul aria-label="Why this shoe matched" className="mb-2.5 flex flex-wrap gap-[7px]">
            {shoe.match_reasons.map((reason) => (
              <li
                key={reason}
                className="rounded-full bg-accent/10 px-2.5 py-1.5 text-[11px]/none font-bold text-accent-deep"
              >
                {reason}
              </li>
            ))}
          </ul>
        )}

        <div className="mb-4 flex flex-wrap gap-[7px]">
          {shoe.specs.map((spec) => (
            <span
              key={spec}
              className="rounded-full bg-paper px-2.5 py-1.5 text-[11px]/none font-semibold text-muted"
            >
              {spec}
            </span>
          ))}
        </div>

        <p className="mb-5 flex-1 font-serif text-[14.5px]/[1.62] text-body">
          {shoe.explanation}
        </p>

        {shoe.evidence && shoe.evidence.length > 0 && (
          <details className="mb-5 rounded-xl bg-paper px-3.5 py-3">
            <summary className="cursor-pointer text-[13px]/none font-bold text-ink">
              See the review evidence
            </summary>
            <div className="mt-3 space-y-3">
              {shoe.evidence.slice(0, 2).map((excerpt, index) => (
                <blockquote
                  key={`${excerpt.source ?? "source"}-${index}`}
                  className="border-l-2 border-accent pl-3 font-serif text-[13px]/[1.5] text-muted"
                >
                  “{excerpt.text}”
                  {excerpt.source && (
                    <footer className="mt-1 font-sans text-[10px]/none font-bold tracking-[.06em] text-faint uppercase">
                      {excerpt.source}
                    </footer>
                  )}
                </blockquote>
              ))}
            </div>
          </details>
        )}

        {!isMockApi && (
          // New tab: leaving this page would lose the user's results.
          <Link
            href={`/catalog/${shoe.id}`}
            target="_blank"
            className="mb-4 text-[13px]/none font-bold text-ink underline underline-offset-4 hover:text-accent-deep"
          >
            See full scores and specs
          </Link>
        )}

        <SaveShoeButton shoeId={shoe.id} className="mb-3.5 w-full" />

        <div className="mb-3.5">
          <a
            href={shop.href}
            target="_blank"
            rel={shop.rel}
            onClick={onBuyIntent}
            className="block rounded-full bg-accent p-[13px] text-center text-[13px]/none font-bold text-white transition-colors hover:bg-accent-deep"
          >
            {shop.label}
          </a>
        </div>

        <div className="flex items-center justify-between">
          <div className="text-xs/none font-medium text-faint">
            {vote === "up" ? "Thanks — noted" : vote === "down" ? "Got it, noted" : ""}
          </div>
          <div className="flex gap-1.5">
            {(["up", "down"] as const).map((v) => (
              <button
                key={v}
                type="button"
                aria-label={v === "up" ? "Good recommendation" : "Bad recommendation"}
                aria-pressed={vote === v}
                onClick={() => {
                  if (v === "down") {
                    setShowFeedbackForm((open) => !open);
                    return;
                  }
                  onVote("up");
                }}
                className={`flex size-[38px] cursor-pointer items-center justify-center rounded-full border-[1.5px] text-[15px] ${
                  vote === v ? "border-ink bg-ink" : "border-line bg-white"
                }`}
              >
                {v === "up" ? "👍" : "👎"}
              </button>
            ))}
          </div>
        </div>
        {showFeedbackForm && (
          <div className="mt-4 rounded-xl border border-line bg-paper p-3.5">
            <p className="mb-3 text-[13px]/tight font-bold text-ink">
              What missed the mark?
            </p>
            <div className="flex flex-wrap gap-2">
              {DOWNVOTE_REASONS.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => setReason(item.value)}
                  className={`cursor-pointer rounded-full border px-3 py-2 text-xs/none font-semibold transition-colors ${
                    reason === item.value
                      ? "border-ink bg-ink text-white"
                      : "border-line bg-white text-muted hover:border-ink"
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
            <label className="mt-3 block text-xs font-semibold text-muted" htmlFor={`feedback-${shoe.id}`}>
              Anything else? <span className="font-normal">Optional</span>
            </label>
            <textarea
              id={`feedback-${shoe.id}`}
              value={comment}
              onChange={(event) => setComment(event.target.value)}
              maxLength={500}
              rows={2}
              className="mt-1.5 w-full resize-y rounded-lg border border-line bg-white px-3 py-2 text-sm outline-none focus:border-ink"
              placeholder="Tell us what would have made this better"
            />
            <button
              type="button"
              disabled={!reason}
              onClick={submitDownvote}
              className="mt-3 cursor-pointer rounded-full bg-ink px-4 py-2 text-xs/none font-bold text-white disabled:cursor-not-allowed disabled:opacity-40"
            >
              Send feedback
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
