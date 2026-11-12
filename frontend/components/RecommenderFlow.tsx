"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

import { AccountNav } from "@/components/AccountNav";
import { ErrorScreen } from "@/components/screens/ErrorScreen";
import { HomeScreen } from "@/components/screens/HomeScreen";
import {
  answerSummary,
  budgetValue,
  EMPTY_INTAKE,
  furthestStep,
  IntakeScreen,
  knownAnswers,
  stepName,
  type IntakeState,
} from "@/components/screens/IntakeScreen";
import { LoadingScreen } from "@/components/screens/LoadingScreen";
import { NoResultsScreen } from "@/components/screens/NoResultsScreen";
import { ResultsScreen } from "@/components/screens/ResultsScreen";
import { getRecommendations, sendFeedback, trackEvent } from "@/lib/api";
import { MOCK_LATENCY_MS } from "@/lib/mockData";
import { rememberQuizAnswers } from "@/lib/preferences";
import { getAnonymousSessionId } from "@/lib/session";
import type {
  FeedbackReason,
  FeedbackVote,
  RecommendRequest,
  RecommendedShoe,
} from "@/lib/types";

type Screen = "home" | "intake" | "loading" | "error" | "no-results" | "results";

function buildRequest(intake: IntakeState): RecommendRequest {
  const playstyleParts = [
    knownAnswers(intake.positions).join(", "),
    knownAnswers(intake.styles).join(", "),
    intake.freeText.trim(),
    intake.note.trim(),
  ].filter(Boolean);
  return {
    playstyle: playstyleParts.join(" — "),
    budget: budgetValue(intake.budget),
    aesthetic: null,
    court: intake.court,
    priorities: intake.priorities,
    foot_width: intake.footWidth,
    preferred_brand: intake.brand,
    preferred_cut: intake.cut,
  };
}

export function RecommenderFlow() {
  const [screen, setScreen] = useState<Screen>("home");
  const [step, setStep] = useState(0);
  const [intake, setIntake] = useState<IntakeState>(EMPTY_INTAKE);
  const [stage, setStage] = useState(0);
  const [shoes, setShoes] = useState<RecommendedShoe[]>([]);
  const [feedback, setFeedback] = useState<Record<number, FeedbackVote | null>>(
    {},
  );

  const timersRef = useRef<number[]>([]);
  const requestSeq = useRef(0);

  const clearTimers = useCallback(() => {
    timersRef.current.forEach((t) => clearTimeout(t));
    timersRef.current = [];
  }, []);

  useEffect(() => clearTimers, [clearTimers]);

  /** Moves to a screen as a browser history entry, so Back retraces the quiz. */
  const navigate = useCallback((nextScreen: Screen, nextStep = 0) => {
    window.history.pushState({ screen: nextScreen, step: nextStep }, "");
    setScreen(nextScreen);
    setStep(nextStep);
    window.scrollTo(0, 0);
  }, []);

  useEffect(() => {
    const restore = (event: PopStateEvent) => {
      requestSeq.current++; // abandon any in-flight request
      clearTimers();
      setScreen(event.state?.screen ?? "home");
      setStep(event.state?.step ?? 0);
    };
    window.addEventListener("popstate", restore);
    return () => window.removeEventListener("popstate", restore);
  }, [clearTimers]);

  const logEvent = useCallback(
    (
      name:
        | "quiz_started"
        | "quiz_step_completed"
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
      const seq = ++requestSeq.current;
      const request = buildRequest(intake);
      const startedAt = Date.now();
      logEvent("quiz_submitted", {
        position_count: knownAnswers(intake.positions).length,
        style_count: knownAnswers(intake.styles).length,
        court: intake.court,
        priority_count: intake.priorities.length,
        has_budget: Boolean(intake.budget),
        has_extras: Boolean(
          intake.footWidth || intake.brand || intake.cut || intake.note.trim(),
        ),
      });
      if (!simulateFailure) void rememberQuizAnswers(intake);
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
          navigate("no-results");
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
        navigate("results");
      } catch {
        if (seq !== requestSeq.current) return;
        clearTimers();
        logEvent("recommendation_error", {
          duration_ms: Date.now() - startedAt,
          simulated: simulateFailure,
        });
        navigate("error");
      }
    },
    [clearTimers, intake, logEvent, navigate],
  );

  const startOver = useCallback(() => {
    requestSeq.current++;
    clearTimers();
    setIntake(EMPTY_INTAKE);
    setStage(0);
    setShoes([]);
    setFeedback({});
    navigate("home");
  }, [clearTimers, navigate]);

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

  // History can outlive React state after a refresh: never show an entry whose
  // data is gone, or a step whose earlier required answers are missing.
  const visibleScreen = screen === "results" && shoes.length === 0 ? "home" : screen;
  const visibleStep = Math.min(step, furthestStep(intake));

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
        <div className="flex items-center gap-1 sm:gap-3">
          <Link
            href="/catalog"
            className="rounded-full px-3.5 py-2.5 text-[13px]/none font-semibold text-muted transition-colors hover:text-ink"
          >
            Browse catalog
          </Link>
          {visibleScreen === "results" && (
            <button
              type="button"
              onClick={startOver}
              className="cursor-pointer rounded-full border border-line px-3.5 py-2.5 text-[13px]/none font-semibold text-muted transition-colors hover:border-ink hover:text-ink"
            >
              Start over
            </button>
          )}
          <AccountNav />
        </div>
      </header>

      {visibleScreen === "home" && (
        <HomeScreen
          onStart={() => {
            logEvent("quiz_started");
            navigate("intake", 0);
          }}
        />
      )}
      {visibleScreen === "intake" && (
        <IntakeScreen
          intake={intake}
          onChange={setIntake}
          step={visibleStep}
          editing={shoes.length > 0}
          onBack={() => navigate("intake", visibleStep - 1)}
          onNext={() => {
            logEvent("quiz_step_completed", {
              step: visibleStep + 1,
              step_name: stepName(visibleStep),
            });
            navigate("intake", visibleStep + 1);
          }}
          onSubmit={() => runRequest()}
          onSimulateError={() => runRequest(true)}
        />
      )}
      {visibleScreen === "loading" && <LoadingScreen stage={stage} />}
      {visibleScreen === "error" && (
        <ErrorScreen onRetry={() => runRequest()} onStartOver={startOver} />
      )}
      {visibleScreen === "no-results" && (
        <NoResultsScreen onAdjust={() => navigate("intake", 3)} />
      )}
      {visibleScreen === "results" && (
        <ResultsScreen
          answers={answerSummary(intake)}
          onEditStep={(editStep) => navigate("intake", editStep)}
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
