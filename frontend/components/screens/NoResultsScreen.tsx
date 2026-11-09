"use client";

import Link from "next/link";

interface NoResultsScreenProps {
  onAdjust: () => void;
}

export function NoResultsScreen({ onAdjust }: NoResultsScreenProps) {
  return (
    <div className="mt-30 flex w-full max-w-[520px] flex-col items-center text-center">
      <div className="mb-7 flex size-16 items-center justify-center rounded-full border-2 border-line bg-paper text-[26px]/none font-extrabold text-fainter">
        0
      </div>
      <h2 className="mb-2.5 text-2xl/[1.3] font-extrabold">
        Nothing matched that exact ask
      </h2>
      <p className="mb-7 font-serif text-[15px]/[1.6] text-muted">
        Your preferences are valid — our current catalog just doesn&apos;t have a
        confident match yet. Try a wider budget or fewer constraints, or browse
        the full catalog.
      </p>
      <div className="flex flex-wrap justify-center gap-3">
        <button
          type="button"
          onClick={onAdjust}
          className="cursor-pointer rounded-full bg-accent px-[26px] py-3.5 text-sm/none font-bold text-white transition-colors hover:bg-accent-deep"
        >
          Adjust my picks
        </button>
        <Link
          href="/catalog"
          className="rounded-full border-[1.5px] border-line px-[22px] py-3.5 text-sm/none font-semibold text-muted transition-colors hover:border-ink hover:text-ink"
        >
          Browse catalog
        </Link>
      </div>
    </div>
  );
}
