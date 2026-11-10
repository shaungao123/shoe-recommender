"use client";

import Link from "next/link";

import { ScoreBar } from "@/components/catalog/ScoreBar";
import { SaveShoeButton } from "@/components/SaveShoeButton";
import type { CatalogShoe } from "@/lib/catalog";

function priceLabel(shoe: CatalogShoe) {
  return shoe.price === null ? "Price unavailable" : `$${Math.round(shoe.price)}`;
}

export function CatalogCard({
  shoe,
  saved,
  canSave = false,
  onSavedChange,
}: {
  shoe: CatalogShoe;
  saved?: boolean;
  /** Only signed-in users see wishlist controls. */
  canSave?: boolean;
  onSavedChange?: (saved: boolean) => void;
}) {
  const chips = [shoe.cut_height && `${shoe.cut_height} cut`, shoe.cushioning_tech, ...shoe.playstyle_tags]
    .filter((chip): chip is string => Boolean(chip))
    .slice(0, 3);
  const { scores } = shoe;
  return (
    <div className="group relative overflow-hidden rounded-2xl border border-line bg-white transition hover:-translate-y-0.5 hover:border-ink hover:shadow-[0_12px_30px_rgba(0,0,0,.08)]">
      {canSave && (
        <div className="absolute top-3 right-3 z-[2]">
          <SaveShoeButton
            key={`${shoe.id}-${saved ? "1" : "0"}`}
            shoeId={shoe.id}
            initiallySaved={saved}
            visible
            compact
            onChange={onSavedChange}
          />
        </div>
      )}
      <Link href={`/catalog/${shoe.id}`} className="block">
        {shoe.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element -- catalog sources supply varying remote image hosts
          <img src={shoe.image_url} alt={`${shoe.brand} ${shoe.name}`} loading="lazy" className="h-52 w-full bg-white object-contain p-3" />
        ) : (
          <div className="hatch flex h-52 items-center justify-center text-xs font-bold tracking-[.08em] text-faint uppercase">Catalog image unavailable</div>
        )}
        <div className="p-5">
          <div className="mb-1 text-[11px]/none font-bold tracking-[.07em] text-accent uppercase">{shoe.brand}</div>
          <div className="flex items-start justify-between gap-3">
            <h2 className="text-lg/tight font-extrabold text-ink group-hover:underline">{shoe.name}</h2>
            <span className="shrink-0 text-sm font-bold">{priceLabel(shoe)}</span>
          </div>
          {scores && (
            <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3">
              <ScoreBar label="Traction" value={scores.traction} />
              <ScoreBar label="Cushion" value={scores.cushion} />
              <ScoreBar label="Support" value={scores.support} />
              <ScoreBar label="Fit" value={scores.fit} />
            </div>
          )}
          <div className="mt-3 flex flex-wrap gap-1.5">
            {chips.map((chip) => <span key={chip} className="rounded-full bg-paper px-2 py-1 text-[11px] font-semibold text-muted">{chip}</span>)}
          </div>
        </div>
      </Link>
    </div>
  );
}
