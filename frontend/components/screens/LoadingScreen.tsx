"use client";

export const LOADING_STAGES = [
  "Matching your playstyle",
  "Reading the reviews",
  "Writing your picks",
] as const;

interface LoadingScreenProps {
  /** Index of the stage currently in progress; stages before it are done. */
  stage: number;
}

export function LoadingScreen({ stage }: LoadingScreenProps) {
  return (
    <div className="mt-30 flex w-full max-w-[480px] flex-col items-center">
      <div className="mb-10 size-14 animate-spin rounded-full border-4 border-line border-t-accent" />
      <div className="flex w-full flex-col gap-[18px]">
        {LOADING_STAGES.map((label, i) => {
          const done = stage > i;
          const active = stage === i;
          return (
            <div key={label} className="flex items-center gap-3.5">
              <div
                className={`flex size-[26px] flex-none items-center justify-center rounded-full border-[1.5px] text-[13px]/none font-bold ${
                  done
                    ? "border-accent bg-accent text-white"
                    : active
                      ? "border-accent bg-white text-faint"
                      : "border-line bg-paper text-faint"
                }`}
              >
                {done ? "✓" : i + 1}
              </div>
              <div
                className={`text-base/[1.3] font-semibold ${
                  done || active ? "text-ink" : "text-faint"
                }`}
              >
                {label}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
