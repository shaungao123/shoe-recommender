"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ErrorScreen } from "@/components/screens/ErrorScreen";
import { HomeScreen } from "@/components/screens/HomeScreen";
import { IntakeScreen, type IntakeState } from "@/components/screens/IntakeScreen";
import { LoadingScreen } from "@/components/screens/LoadingScreen";
import { ResultsScreen } from "@/components/screens/ResultsScreen";
import { getRecommendations, sendFeedback } from "@/lib/api";
import { MOCK_LATENCY_MS } from "@/lib/mockData";
import type {
  FeedbackVote,
  RecommendRequest,
  RecommendedShoe,
} from "@/lib/types";

type Screen = "home" | "intake" | "loading" | "error" | "results";

const EMPTY_INTAKE: IntakeState = {
  position: null,
  styles: [],
  freeText: "",
  budget: null,
  aesthetic: "",
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
  };
}

export function RecommenderFlow() {
  const [screen, setScreen] = useState<Screen>("home");
  const [intake, setIntake] = useState<IntakeState>(EMPTY_INTAKE);
  const [stage, setStage] = useState(0);
  const [shoes, setShoes] = useState<RecommendedShoe[]>([]);
  const [feedback, setFeedback] = useState<Record<string, FeedbackVote | null>>(
    {},
  );

  const timersRef = useRef<number[]>([]);
  const requestSeq = useRef(0);

  const clearTimers = useCallback(() => {
    timersRef.current.forEach((t) => clearTimeout(t));
    timersRef.current = [];
  }, []);

  useEffect(() => clearTimers, [clearTimers]);

  const runRequest = useCallback(
    async (simulateFailure = false) => {
      const seq = ++requestSeq.current;
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
          : await getRecommendations(buildRequest(intake));
        if (seq !== requestSeq.current) return; // superseded by start over/retry
        clearTimers();
        setShoes(response.recommendations);
        setFeedback({});
        setScreen("results");
      } catch {
        if (seq !== requestSeq.current) return;
        clearTimers();
        setScreen("error");
      }
    },
    [clearTimers, intake],
  );

  const startOver = useCallback(() => {
    requestSeq.current++;
    clearTimers();
    setIntake(EMPTY_INTAKE);
    setStage(0);
    setShoes([]);
    setFeedback({});
    setScreen("home");
  }, [clearTimers]);

  const vote = useCallback(
    (shoeId: string, v: FeedbackVote) => {
      const next = feedback[shoeId] === v ? null : v;
      setFeedback((prev) => ({ ...prev, [shoeId]: next }));
      if (next) sendFeedback({ shoe_id: shoeId, vote: next });
    },
    [feedback],
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
        {screen === "results" && (
          <button
            type="button"
            onClick={startOver}
            className="cursor-pointer rounded-full border border-line px-3.5 py-2.5 text-[13px]/none font-semibold text-muted transition-colors hover:border-ink hover:text-ink"
          >
            Start over
          </button>
        )}
      </header>

      {screen === "home" && <HomeScreen onStart={() => setScreen("intake")} />}
      {screen === "intake" && (
        <IntakeScreen
          intake={intake}
          onChange={setIntake}
          onSubmit={() => runRequest()}
          onSimulateError={() => runRequest(true)}
        />
      )}
      {screen === "loading" && <LoadingScreen stage={stage} />}
      {screen === "error" && (
        <ErrorScreen onRetry={() => runRequest()} onStartOver={startOver} />
      )}
      {screen === "results" && (
        <ResultsScreen shoes={shoes} feedback={feedback} onVote={vote} />
      )}
    </div>
  );
}
