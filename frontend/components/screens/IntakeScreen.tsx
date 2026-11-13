"use client";

import { Chip } from "@/components/Chip";
import { isMockApi } from "@/lib/api";
import type { Court, Cut, FootWidth, Priority } from "@/lib/types";

export const NOT_SURE = "Not sure";
export const POSITIONS = ["Guard", "Wing", "Big"] as const;
export const STYLE_TAGS = [
  "Slasher",
  "Shooter",
  "All-around",
  "Post",
  "Defender",
  "Speedster",
  "Leaper",
] as const;
export const COURTS: [Court, string][] = [
  ["indoor", "Indoor"],
  ["outdoor", "Outdoor"],
  ["both", "Both"],
];
export const PRIORITIES: [Priority, string][] = [
  ["traction", "Traction"],
  ["cushion", "Cushion"],
  ["support", "Ankle support"],
  ["lightweight", "Light weight"],
];
export const NO_LIMIT = "No limit";
export const BUDGETS = ["$100", "$120", "$140", "$160", "$180", NO_LIMIT] as const;
export const FOOT_WIDTHS: [FootWidth, string][] = [
  ["narrow", "Narrow"],
  ["standard", "Standard"],
  ["wide", "Wide"],
];
export const BRANDS = [
  "Nike",
  "Jordan",
  "Adidas",
  "Under Armour",
  "Puma",
  "New Balance",
  "Converse",
  "Reebok",
  "Asics",
  "Li-Ning",
  "Anta",
  "361 Degrees",
  "Peak",
  "Xtep",
] as const;
export const CUTS: [Cut, string][] = [
  ["low", "Low"],
  ["mid", "Mid"],
  ["high", "High"],
];

export interface IntakeState {
  positions: string[];
  styles: string[];
  freeText: string;
  court: Court | null;
  priorities: Priority[];
  budget: string | null;
  footWidth: FootWidth | null;
  brand: string | null;
  cut: Cut | null;
  note: string;
}

export const EMPTY_INTAKE: IntakeState = {
  positions: [],
  styles: [],
  freeText: "",
  court: null,
  priorities: [],
  budget: null,
  footWidth: null,
  brand: null,
  cut: null,
  note: "",
};

const STEPS = [
  {
    name: "game",
    title: "How do you play?",
    subtitle: "Pick everything that fits. Not sure is a fine answer.",
    hint: "Pick a position and a style, or describe your game.",
  },
  {
    name: "court",
    title: "Where do you play?",
    subtitle: "Rough courts wear shoes out quickly, so this changes the picks.",
    hint: "Pick one to continue.",
  },
  {
    name: "priorities",
    title: "What matters most?",
    subtitle: "Pick up to two, or skip this if you want a balanced shoe.",
    hint: null,
  },
  {
    name: "budget",
    title: "What's the most you'd spend?",
    subtitle: "We won't show you anything priced above this.",
    hint: null,
  },
  {
    name: "extras",
    title: "Anything else?",
    subtitle: "All optional. These nudge the picks without ruling shoes out.",
    hint: null,
  },
] as const;

export const LAST_STEP = STEPS.length - 1;

export function stepName(step: number): string {
  return STEPS[step].name;
}

function canAdvance(intake: IntakeState, step: number): boolean {
  if (step === 0) {
    return (
      intake.positions.length > 0 &&
      (intake.styles.length > 0 || Boolean(intake.freeText.trim()))
    );
  }
  return step !== 1 || intake.court !== null;
}

/** The furthest step reachable with these answers, e.g. after a refresh clears them. */
export function furthestStep(intake: IntakeState): number {
  const blocked = STEPS.findIndex((_, step) => !canAdvance(intake, step));
  return blocked === -1 ? LAST_STEP : blocked;
}

/** Selected values with the "Not sure" placeholder removed. */
export function knownAnswers(values: string[]): string[] {
  return values.filter((value) => value !== NOT_SURE);
}

/** Parses a budget chip into dollars; null means no cap. */
export function budgetValue(label: string | null): number | null {
  if (!label || label === NO_LIMIT) return null;
  return Number(label.replace(/\D/g, ""));
}

/** One short summary per answered step, used for the editable chips on results. */
export function answerSummary(intake: IntakeState): { step: number; label: string }[] {
  const labelOf = <T extends string>(options: [T, string][], value: T) =>
    options.find(([option]) => option === value)?.[1] ?? value;
  const game =
    knownAnswers([...intake.positions, ...intake.styles]).join(" · ") ||
    (intake.freeText.trim() ? "Your own words" : NOT_SURE);
  const extras = [
    intake.footWidth && `${labelOf(FOOT_WIDTHS, intake.footWidth)} foot`,
    intake.brand,
    intake.cut && `${labelOf(CUTS, intake.cut)} cut`,
    intake.note.trim() && "Your note",
  ].filter(Boolean);
  const budget =
    intake.budget && (intake.budget === NO_LIMIT ? NO_LIMIT : `Up to ${intake.budget}`);
  return [
    { step: 0, label: game },
    { step: 1, label: intake.court ? labelOf(COURTS, intake.court) : "" },
    { step: 2, label: intake.priorities.map((p) => labelOf(PRIORITIES, p)).join(" · ") },
    { step: 3, label: budget ?? "" },
    { step: 4, label: extras.join(" · ") },
  ].filter((answer) => answer.label);
}

function toggleWithNotSure(values: string[], label: string): string[] {
  if (values.includes(label)) return values.filter((value) => value !== label);
  return label === NOT_SURE ? [NOT_SURE] : [...knownAnswers(values), label];
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-3.5 text-xs/none font-bold tracking-[.06em] text-ink uppercase">
      {children}
    </div>
  );
}

function SingleChoice<T extends string>({
  options,
  value,
  onSelect,
}: {
  options: [T, string][];
  value: T | null;
  onSelect: (value: T | null) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2.5">
      {options.map(([option, label]) => (
        <Chip
          key={option}
          label={label}
          selected={value === option}
          onClick={() => onSelect(value === option ? null : option)}
        />
      ))}
    </div>
  );
}

const inputClass =
  "w-full rounded-xl border-[1.5px] border-line bg-white px-4 py-3.5 text-[15px]/[1.4] outline-none focus:border-ink";

interface IntakeScreenProps {
  intake: IntakeState;
  onChange: (intake: IntakeState) => void;
  step: number;
  /** True when revising answers that already produced results. */
  editing: boolean;
  onBack: () => void;
  onNext: () => void;
  onSubmit: () => void;
  onSimulateError: () => void;
}

export function IntakeScreen({
  intake,
  onChange,
  step,
  editing,
  onBack,
  onNext,
  onSubmit,
  onSimulateError,
}: IntakeScreenProps) {
  const current = STEPS[step];
  const ready = canAdvance(intake, step);
  const isLast = step === LAST_STEP;
  const submitsNow = isLast || editing;
  const choiceChips = (
    options: readonly string[],
    field: "positions" | "styles",
  ) => (
    <div className="flex flex-wrap gap-2.5">
      {[...options, NOT_SURE].map((label) => (
        <Chip
          key={label}
          label={label}
          selected={intake[field].includes(label)}
          onClick={() =>
            onChange({ ...intake, [field]: toggleWithNotSure(intake[field], label) })
          }
        />
      ))}
    </div>
  );

  const togglePriority = (priority: Priority) => {
    const selected = intake.priorities;
    // Tapping a third replaces the oldest, so the limit never feels like a dead button.
    const priorities = selected.includes(priority)
      ? selected.filter((item) => item !== priority)
      : [...selected.slice(-1), priority];
    onChange({ ...intake, priorities });
  };

  return (
    <div className="mt-7 w-full max-w-[640px]">
      <div className="mb-8">
        <div className="mb-2.5 text-xs/none font-semibold text-muted">
          Step {step + 1} of {STEPS.length}
        </div>
        <div
          role="progressbar"
          aria-label="Quiz progress"
          aria-valuemin={1}
          aria-valuemax={STEPS.length}
          aria-valuenow={step + 1}
          className="h-1.5 w-full overflow-hidden rounded-full bg-line"
        >
          <div
            className="h-full rounded-full bg-accent transition-[width]"
            style={{ width: `${((step + 1) / STEPS.length) * 100}%` }}
          />
        </div>
      </div>

      <h1 className="mb-2.5 text-[36px]/[1.15] font-extrabold tracking-[-.02em]">
        {current.title}
      </h1>
      <p className="mb-9 max-w-[520px] font-serif text-[17px]/[1.6] text-muted">
        {current.subtitle}
      </p>

      {step === 0 && (
        <>
          <div className="mb-8">
            <SectionLabel>Position</SectionLabel>
            {choiceChips(POSITIONS, "positions")}
          </div>
          <div className="mb-9">
            <SectionLabel>Style</SectionLabel>
            <div className="mb-4">{choiceChips(STYLE_TAGS, "styles")}</div>
            <input
              value={intake.freeText}
              onChange={(e) => onChange({ ...intake, freeText: e.target.value })}
              aria-label="Describe your game"
              placeholder="Or describe your game in your own words"
              maxLength={300}
              className={inputClass}
            />
          </div>
        </>
      )}

      {step === 1 && (
        <div className="mb-9">
          <SingleChoice
            options={COURTS}
            value={intake.court}
            onSelect={(court) => onChange({ ...intake, court })}
          />
        </div>
      )}

      {step === 2 && (
        <div className="mb-9 flex flex-wrap gap-2.5">
          {PRIORITIES.map(([priority, label]) => (
            <Chip
              key={priority}
              label={label}
              selected={intake.priorities.includes(priority)}
              onClick={() => togglePriority(priority)}
            />
          ))}
        </div>
      )}

      {step === 3 && (
        <div className="mb-9 flex flex-wrap gap-2.5">
          {BUDGETS.map((label) => (
            <Chip
              key={label}
              label={label}
              selected={intake.budget === label}
              onClick={() =>
                onChange({ ...intake, budget: intake.budget === label ? null : label })
              }
            />
          ))}
        </div>
      )}

      {step === 4 && (
        <>
          <div className="mb-8">
            <SectionLabel>Foot width</SectionLabel>
            <SingleChoice
              options={FOOT_WIDTHS}
              value={intake.footWidth}
              onSelect={(footWidth) => onChange({ ...intake, footWidth })}
            />
          </div>
          <div className="mb-8">
            <SectionLabel>Preferred brand</SectionLabel>
            <SingleChoice
              options={BRANDS.map((brand): [string, string] => [brand, brand])}
              value={intake.brand}
              onSelect={(brand) => onChange({ ...intake, brand })}
            />
          </div>
          <div className="mb-8">
            <SectionLabel>Cut</SectionLabel>
            <SingleChoice
              options={CUTS}
              value={intake.cut}
              onSelect={(cut) => onChange({ ...intake, cut })}
            />
          </div>
          <div className="mb-9">
            <SectionLabel>Anything else we should know?</SectionLabel>
            <input
              value={intake.note}
              onChange={(e) => onChange({ ...intake, note: e.target.value })}
              aria-label="Anything else we should know"
              placeholder="e.g. recovering from an ankle sprain, flat feet"
              maxLength={300}
              className={inputClass}
            />
          </div>
        </>
      )}

      <div className="flex items-center gap-3">
        {step > 0 && (
          <button
            type="button"
            onClick={onBack}
            className="cursor-pointer rounded-full border-[1.5px] border-line px-6 py-[17px] text-[15px]/none font-bold text-ink transition-colors hover:border-ink"
          >
            Back
          </button>
        )}
        <button
          type="button"
          onClick={submitsNow ? onSubmit : onNext}
          disabled={!ready}
          className="flex-1 cursor-pointer rounded-full bg-accent p-[18px] text-[15px]/none font-bold text-white shadow-[0_10px_24px_rgba(255,90,31,.28)] transition-colors hover:bg-accent-deep disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-accent"
        >
          {editing ? "Update my picks" : isLast ? "Get my picks" : "Next"}
        </button>
      </div>
      {!ready && current.hint && (
        <p className="mt-3 text-center text-[13px]/tight text-muted">{current.hint}</p>
      )}
      {editing && !isLast && (
        <button
          type="button"
          onClick={onNext}
          disabled={!ready}
          className="mt-4 w-full cursor-pointer text-center text-[13px]/none font-bold text-ink underline underline-offset-4 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Next question
        </button>
      )}
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
