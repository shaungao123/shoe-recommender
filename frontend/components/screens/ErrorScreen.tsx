"use client";

interface ErrorScreenProps {
  onRetry: () => void;
  onStartOver: () => void;
}

export function ErrorScreen({ onRetry, onStartOver }: ErrorScreenProps) {
  return (
    <div className="mt-30 flex w-full max-w-[420px] flex-col items-center text-center">
      <div className="mb-7 flex size-16 items-center justify-center rounded-full border-2 border-line bg-paper text-[26px]/none font-extrabold text-fainter">
        !
      </div>
      <h2 className="mb-2.5 text-2xl/[1.3] font-extrabold">
        Couldn&apos;t reach the bench
      </h2>
      <p className="mb-7 font-serif text-[15px]/[1.6] text-muted">
        Check your connection and try again — your picks are still waiting.
      </p>
      <div className="flex gap-3">
        <button
          type="button"
          onClick={onRetry}
          className="cursor-pointer rounded-full bg-accent px-[26px] py-3.5 text-sm/none font-bold text-white transition-colors hover:bg-accent-deep"
        >
          Try again
        </button>
        <button
          type="button"
          onClick={onStartOver}
          className="cursor-pointer rounded-full border-[1.5px] border-line px-[22px] py-3.5 text-sm/none font-semibold text-muted transition-colors hover:border-ink hover:text-ink"
        >
          Start over
        </button>
      </div>
    </div>
  );
}
