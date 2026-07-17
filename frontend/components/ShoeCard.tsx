"use client";

import type { FeedbackVote, RecommendedShoe } from "@/lib/types";

interface ShoeCardProps {
  shoe: RecommendedShoe;
  isTop: boolean;
  vote: FeedbackVote | null;
  onVote: (vote: FeedbackVote) => void;
}

function formatPrice(price: number | null): string {
  return price !== null ? `$${Math.round(price)}` : "—";
}

export function ShoeCard({ shoe, isTop, vote, onVote }: ShoeCardProps) {
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
          className="h-[260px] w-full bg-paper object-cover"
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

        <div className="mb-3.5">
          {shoe.affiliate_url ? (
            <a
              href={shoe.affiliate_url}
              target="_blank"
              rel="sponsored noopener"
              className="block rounded-full bg-accent p-[13px] text-center text-[13px]/none font-bold text-white transition-colors hover:bg-accent-deep"
            >
              Shop this shoe
            </a>
          ) : (
            <div className="rounded-full border-[1.5px] border-dashed border-line p-[13px] text-center text-[13px]/none font-bold text-faint">
              Buy links coming soon
            </div>
          )}
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
                onClick={() => onVote(v)}
                className={`flex size-[38px] cursor-pointer items-center justify-center rounded-full border-[1.5px] text-[15px] ${
                  vote === v ? "border-ink bg-ink" : "border-line bg-white"
                }`}
              >
                {v === "up" ? "👍" : "👎"}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
