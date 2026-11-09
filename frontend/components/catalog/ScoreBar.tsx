interface ScoreBarProps {
  label: string;
  value: number | null;
  max?: number;
  suffix?: string;
}

/** A labelled rating. Renders nothing when the reviewer didn't rate this attribute. */
export function ScoreBar({ label, value, max = 10, suffix = "" }: ScoreBarProps) {
  if (value === null) return null;
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-2 text-xs/none font-semibold text-muted">
        <span>{label}</span>
        <span className="font-bold text-ink tabular-nums">
          {max === 10 ? value.toFixed(1) : value}
          {suffix}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-paper">
        <div className="h-full rounded-full bg-accent" style={{ width: `${Math.min(100, (value / max) * 100)}%` }} />
      </div>
    </div>
  );
}
