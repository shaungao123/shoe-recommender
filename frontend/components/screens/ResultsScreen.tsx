"use client";

import { ShoeCard } from "@/components/ShoeCard";
import type { FeedbackReason, FeedbackVote, RecommendedShoe } from "@/lib/types";

interface ResultsScreenProps {
  /** Ranked best-first. */
  shoes: RecommendedShoe[];
  feedback: Record<number, FeedbackVote | null>;
  onVote: (
    shoeId: number,
    vote: FeedbackVote,
    details?: { reason?: FeedbackReason; comment?: string },
  ) => void;
  onBuyIntent: (shoeId: number, hasAffiliateLink: boolean) => void;
}

/** On desktop the top pick sits center podium: rank 2, rank 1, rank 3. */
const PODIUM_ORDER = ["lg:order-2", "lg:order-1", "lg:order-3"];

export function ResultsScreen({ shoes, feedback, onVote, onBuyIntent }: ResultsScreenProps) {
  return (
    <div className="mt-6 w-full max-w-[1080px]">
      <div className="mb-8">
        <h1 className="mb-2 text-[32px]/tight font-extrabold tracking-[-.01em]">
          Your top 3
        </h1>
        <p className="font-serif text-base/normal text-muted">
          Ranked for how you actually play, not just the specs sheet.
        </p>
      </div>
      <div className="grid grid-cols-1 items-start gap-[22px] lg:grid-cols-[1fr_1.14fr_1fr]">
        {shoes.map((shoe, i) => (
          <div key={shoe.id} className={PODIUM_ORDER[i] ?? ""}>
            <ShoeCard
              shoe={shoe}
              isTop={i === 0}
              vote={feedback[shoe.id] ?? null}
              onVote={(v, details) => onVote(shoe.id, v, details)}
              onBuyIntent={() => onBuyIntent(shoe.id, Boolean(shoe.affiliate_url))}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
