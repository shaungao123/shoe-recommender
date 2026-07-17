"use client";

interface ChipProps {
  label: string;
  selected: boolean;
  onClick: () => void;
}

export function Chip({ label, selected, onClick }: ChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`cursor-pointer rounded-full border-[1.5px] px-5 py-3 text-sm/none font-semibold transition-colors hover:border-ink ${
        selected ? "border-ink bg-ink text-white" : "border-line bg-white text-ink"
      }`}
    >
      {label}
    </button>
  );
}
