"use client";

import { trendingPlaceholder } from "@/lib/mockData";

interface HomeScreenProps {
  onStart: () => void;
}

export function HomeScreen({ onStart }: HomeScreenProps) {
  return (
    <div className="w-full max-w-[1080px]">
      <div className="relative mt-5 flex flex-col items-start overflow-hidden rounded-3xl bg-ink px-8 py-14 sm:px-14 sm:py-20">
        <div className="mb-[18px] text-xs/none font-bold tracking-[.08em] text-accent uppercase">
          The Assist
        </div>
        <h1 className="mb-5 max-w-[640px] text-[40px]/[1.05] font-extrabold tracking-[-.02em] text-white sm:text-[56px]/[1.05]">
          Find your ideal shoe. Now.
        </h1>
        <p className="mb-9 max-w-[480px] font-serif text-lg/[1.6] text-[#c9c6bd]">
          Tell us how you play, what you&apos;ll spend, and what you&apos;re
          into — we&apos;ll read the reviews and hand you three shoes worth
          trying.
        </p>
        <button
          type="button"
          onClick={onStart}
          className="cursor-pointer rounded-full bg-white px-8 py-[18px] text-base/none font-bold text-ink transition-colors hover:bg-paper"
        >
          Find my shoe
        </button>
      </div>

      <div className="mt-14 mb-6">
        <h2 className="mb-1.5 text-[22px]/tight font-extrabold tracking-[-.01em]">
          Trending with players right now
        </h2>
        <p className="font-serif text-[15px]/normal text-muted">
          A general pulse-check, not personalized to you — take the quiz above
          for picks built around your game.
        </p>
      </div>
      <div className="mb-5 grid grid-cols-1 gap-[18px] sm:grid-cols-2 lg:grid-cols-4">
        {trendingPlaceholder.map((t) => (
          <div
            key={`${t.brand} ${t.model}`}
            className="overflow-hidden rounded-2xl border border-line bg-white"
          >
            <div className="hatch flex h-40 items-center justify-center text-center font-mono text-[11px]/[1.4] font-medium text-faint">
              SHOE PHOTO
            </div>
            <div className="px-4 pt-4 pb-[18px]">
              <div className="mb-[5px] text-[10px]/none font-bold tracking-[.06em] text-accent uppercase">
                {t.brand}
              </div>
              <div className="mb-2 flex items-baseline justify-between gap-2">
                <div className="text-[15px]/tight font-extrabold text-ink">
                  {t.model}
                </div>
                <div className="text-[13px]/none font-bold whitespace-nowrap text-ink">
                  {t.price}
                </div>
              </div>
              <div className="font-serif text-[12.5px]/normal text-muted">
                {t.blurb}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
