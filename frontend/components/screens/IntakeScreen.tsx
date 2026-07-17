"use client";

import { Chip } from "@/components/Chip";
import { isMockApi } from "@/lib/api";

export const POSITIONS = ["Guard", "Wing", "Big"] as const;
export const STYLE_TAGS = [
  "Slasher",
  "Shooter",
  "All-around",
  "Post",
  "Defender",
  "Speedster",
] as const;
export const BUDGETS = ["$100", "$140", "$180+"] as const;

export interface IntakeState {
  position: string | null;
  styles: string[];
  freeText: string;
  budget: string | null;
  aesthetic: string;
}

interface IntakeScreenProps {
  intake: IntakeState;
  onChange: (intake: IntakeState) => void;
  onSubmit: () => void;
  onSimulateError: () => void;
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-3.5 text-xs/none font-bold tracking-[.06em] text-ink uppercase">
      {children}
    </div>
  );
}

export function IntakeScreen({
  intake,
  onChange,
  onSubmit,
  onSimulateError,
}: IntakeScreenProps) {
  const toggleStyle = (label: string) =>
    onChange({
      ...intake,
      styles: intake.styles.includes(label)
        ? intake.styles.filter((s) => s !== label)
        : [...intake.styles, label],
    });

  const inputClass =
    "w-full rounded-xl border-[1.5px] border-line bg-white px-4 py-3.5 text-[15px]/[1.4] outline-none focus:border-ink";

  return (
    <div className="mt-7 w-full max-w-[640px]">
      <h1 className="mb-2.5 text-[40px]/[1.15] font-extrabold tracking-[-.02em]">
        What should you play in?
      </h1>
      <p className="mb-10 max-w-[520px] font-serif text-[17px]/[1.6] text-muted">
        Three quick taps. We&apos;ll read the reviews and hand you three shoes
        worth trying — no storefront, no scrolling.
      </p>

      <div className="mb-9">
        <SectionLabel>Position</SectionLabel>
        <div className="flex flex-wrap gap-2.5">
          {POSITIONS.map((label) => (
            <Chip
              key={label}
              label={label}
              selected={intake.position === label}
              onClick={() => onChange({ ...intake, position: label })}
            />
          ))}
        </div>
      </div>

      <div className="mb-9">
        <SectionLabel>Style — pick any that fit</SectionLabel>
        <div className="mb-4 flex flex-wrap gap-2.5">
          {STYLE_TAGS.map((label) => (
            <Chip
              key={label}
              label={label}
              selected={intake.styles.includes(label)}
              onClick={() => toggleStyle(label)}
            />
          ))}
        </div>
        <input
          value={intake.freeText}
          onChange={(e) => onChange({ ...intake, freeText: e.target.value })}
          placeholder="Optional — describe your game in your own words"
          className={inputClass}
        />
      </div>

      <div className="mb-9">
        <SectionLabel>Budget cap</SectionLabel>
        <div className="flex flex-wrap gap-2.5">
          {BUDGETS.map((label) => (
            <Chip
              key={label}
              label={label}
              selected={intake.budget === label}
              onClick={() => onChange({ ...intake, budget: label })}
            />
          ))}
        </div>
      </div>

      <div className="mb-9">
        <SectionLabel>Aesthetic — optional</SectionLabel>
        <input
          value={intake.aesthetic}
          onChange={(e) => onChange({ ...intake, aesthetic: e.target.value })}
          placeholder="What should they look like? e.g. clean colorways, loud and bold, all-black..."
          className={inputClass}
        />
      </div>

      <button
        type="button"
        onClick={onSubmit}
        className="w-full cursor-pointer rounded-full bg-accent p-[18px] text-[15px]/none font-bold text-white shadow-[0_10px_24px_rgba(255,90,31,.28)] transition-colors hover:bg-accent-deep"
      >
        Get my picks
      </button>
      {isMockApi && (
        <button
          type="button"
          onClick={onSimulateError}
          className="mt-4 w-full cursor-pointer text-center text-xs/none font-medium text-fainter"
        >
          preview: simulate connection error
        </button>
      )}
    </div>
  );
}
