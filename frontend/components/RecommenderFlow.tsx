"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

import { ErrorScreen } from "@/components/screens/ErrorScreen";
import { HomeScreen } from "@/components/screens/HomeScreen";
import { IntakeScreen, type IntakeState } from "@/components/screens/IntakeScreen";
import { LoadingScreen } from "@/components/screens/LoadingScreen";
import { NoResultsScreen } from "@/components/screens/NoResultsScreen";
import { ResultsScreen } from "@/components/screens/ResultsScreen";
import { getRecommendations, sendFeedback, trackEvent } from "@/lib/api";
import { MOCK_LATENCY_MS } from "@/lib/mockData";
import { getAnonymousSessionId } from "@/lib/session";
import type {
  AestheticPreferences,
  FeedbackReason,
  FeedbackVote,
  RecommendRequest,
  RecommendedShoe,
} from "@/lib/types";

type Screen = "home" | "intake" | "loading" | "error" | "no-results" | "results";

const EMPTY_AESTHETIC_PREFERENCES: AestheticPreferences = {
  brand: null,
  color_family: null,
  visual_direction: null,
  silhouette: null,
};

const EMPTY_INTAKE: IntakeState = {
  position: null,
  styles: [],
  freeText: "",
  budget: null,
  aesthetic: "",
  aestheticPreferences: EMPTY_AESTHETIC_PREFERENCES,
};

/** Map the "$180+" chip to no cap; the others to their dollar value. */
function parseBudget(label: string | null): number | null {
  if (!label || label.endsWith("+")) return null;
  return Number(label.replace(/\D/g, ""));
}

function buildRequest(intake: IntakeState): RecommendRequest {
  const playstyleParts = [
    intake.position,
    intake.styles.join(", "),
    intake.freeText.trim(),
  ].filter(Boolean);
  return {
    playstyle: playstyleParts.join(" — "),
    budget: parseBudget(intake.budget),
    aesthetic: intake.aesthetic.trim() || null,
    aesthetic_preferences: intake.aestheticPreferences,
  };
}

function hasMeaningfulIntake(intake: IntakeState): boolean {
  return Boolean(
    intake.position ||
      intake.styles.length ||
      intake.freeText.trim() ||
      intake.budget,
  );
}

export function RecommenderFlow() {
  const [screen, setScreen] = useState<Screen>("home");
  const [intake, setIntake] = useState<IntakeState>(EMPTY_INTAKE);
  const [stage, setStage] = useState(0);
  const [shoes, setShoes] = useState<RecommendedShoe[]>([]);
  const [feedback, setFeedback] = useState<Record<number, FeedbackVote | null>>(
    {},
  );
  const [validationMessage, setValidationMessage] = useState<string | null>(null);

  const timersRef = useRef<number[]>([]);
  const requestSeq = useRef(0);

  const clearTimers = useCallback(() => {
    timersRef.current.forEach((t) => clearTimeout(t));
    timersRef.current = [];
  }, []);

  useEffect(() => clearTimers, [clearTimers]);

  const logEvent = useCallback(
    (
      name:
        | "quiz_started"
        | "quiz_submitted"
        | "recommendations_shown"
        | "recommendation_viewed"
        | "feedback_submitted"
        | "buy_link_intent"
        | "recommendation_error",
      properties?: Record<string, string | number | boolean | null>,
    ) => {
      trackEvent({ session_id: getAnonymousSessionId(), name, properties });
    },
    [],
  );

  const runRequest = useCallback(
    async (simulateFailure = false) => {
      if (!hasMeaningfulIntake(intake)) {
        setValidationMessage(
          "Pick a position or style, describe your game, or set a budget first.",
        );
        return;
      }
      setValidationMessage(null);
      const seq = ++requestSeq.current;
      const request = buildRequest(intake);
      const startedAt = Date.now();
      logEvent("quiz_submitted", {
        has_position: Boolean(intake.position),
        style_count: intake.styles.length,
        has_budget: Boolean(intake.budget),
        has_aesthetic_preference: Boolean(
          intake.aesthetic.trim() ||
            intake.aestheticPreferences.brand ||
            intake.aestheticPreferences.color_family ||
            intake.aestheticPreferences.visual_direction ||
            intake.aestheticPreferences.silhouette,
        ),
      });
      setScreen("loading");
      setStage(0);
      clearTimers();
      // The stage ticker is presentational; the real gate is the API response.
      timersRef.current.push(window.setTimeout(() => setStage(1), 1400));
      timersRef.current.push(window.setTimeout(() => setStage(2), 3200));
      try {
        const response = simulateFailure
          ? await new Promise<never>((_, reject) =>
              timersRef.current.push(
                window.setTimeout(
                  () => reject(new Error("simulated")),
                  MOCK_LATENCY_MS,
                ),
              ),
            )
          : await getRecommendations(request);
        if (seq !== requestSeq.current) return; // superseded by start over/retry
        clearTimers();
        setShoes(response.recommendations);
        setFeedback({});
        if (response.recommendations.length === 0) {
          logEvent("recommendations_shown", {
            result_count: 0,
            duration_ms: Date.now() - startedAt,
          });
          setScreen("no-results");
          return;
        }
        logEvent("recommendations_shown", {
          result_count: response.recommendations.length,
          duration_ms: Date.now() - startedAt,
        });
        response.recommendations.forEach((shoe, index) =>
          logEvent("recommendation_viewed", {
            shoe_id: shoe.id,
            rank: index + 1,
          }),
        );
        setScreen("results");
      } catch {
        if (seq !== requestSeq.current) return;
        clearTimers();
        logEvent("recommendation_error", {
          duration_ms: Date.now() - startedAt,
          simulated: simulateFailure,
        });
        setScreen("error");
      }
    },
    [clearTimers, intake, logEvent],
  );

  const startOver = useCallback(() => {
    requestSeq.current++;
    clearTimers();
    setIntake(EMPTY_INTAKE);
    setStage(0);
    setShoes([]);
    setFeedback({});
    setValidationMessage(null);
    setScreen("home");
  }, [clearTimers]);

  const vote = useCallback(
    (
      shoeId: number,
      v: FeedbackVote,
      details?: { reason?: FeedbackReason; comment?: string },
    ) => {
      setFeedback((prev) => ({ ...prev, [shoeId]: v }));
      sendFeedback({
        session_id: getAnonymousSessionId(),
        shoe_id: shoeId,
        vote: v,
        request: buildRequest(intake),
        reason: details?.reason,
        comment: details?.comment,
      });
      logEvent("feedback_submitted", {
        shoe_id: shoeId,
        vote: v,
        reason: details?.reason ?? null,
        has_comment: Boolean(details?.comment),
      });
    },
    [intake, logEvent],
  );

  return (
    <div className="flex min-h-screen flex-col items-center px-6 pb-20">
      <header className="flex w-full max-w-[1080px] items-center justify-between px-1 pt-7 pb-2">
        <button
          type="button"
          onClick={startOver}
          className="cursor-pointer text-lg/none font-extrabold tracking-[-.01em]"
        >
          The Assist
        </button>
        <div className="flex items-center gap-3">
          <Link
            href="/catalog"
            className="rounded-full px-3.5 py-2.5 text-[13px]/none font-semibold text-muted transition-colors hover:text-ink"
          >
            Browse catalog
          </Link>
          {screen === "results" && (
            <button
              type="button"
              onClick={startOver}
              className="cursor-pointer rounded-full border border-line px-3.5 py-2.5 text-[13px]/none font-semibold text-muted transition-colors hover:border-ink hover:text-ink"
            >
              Start over
            </button>
          )}
        </div>
      </header>

      {screen === "home" && (
        <HomeScreen
          onStart={() => {
            logEvent("quiz_started");
            setScreen("intake");
          }}
        />
      )}
      {screen === "intake" && (
        <IntakeScreen
          intake={intake}
          onChange={setIntake}
          onSubmit={() => runRequest()}
          onSimulateError={() => runRequest(true)}
          validationMessage={validationMessage}
        />
      )}
      {screen === "loading" && <LoadingScreen stage={stage} />}
      {screen === "error" && (
        <ErrorScreen onRetry={() => runRequest()} onStartOver={startOver} />
      )}
      {screen === "no-results" && (
        <NoResultsScreen onAdjust={() => setScreen("intake")} />
      )}
      {screen === "results" && (
        <ResultsScreen
          shoes={shoes}
          feedback={feedback}
          onVote={vote}
          onBuyIntent={(shoeId, hasAffiliateLink) =>
            logEvent("buy_link_intent", {
              shoe_id: shoeId,
              has_affiliate_link: hasAffiliateLink,
            })
          }
        />
      )}
    </div>
  );
}
