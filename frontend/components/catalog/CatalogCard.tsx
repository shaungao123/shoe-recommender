import Link from "next/link";

import type { CatalogShoe } from "@/lib/catalog";

function priceLabel(shoe: CatalogShoe) {
  return shoe.price === null ? "Price unavailable" : `$${Math.round(shoe.price)}`;
}

export function CatalogCard({ shoe }: { shoe: CatalogShoe }) {
  const chips = [shoe.cut_height && `${shoe.cut_height} cut`, shoe.cushioning_tech, ...shoe.playstyle_tags]
    .filter((chip): chip is string => Boolean(chip))
    .slice(0, 3);
  return (
    <Link href={`/catalog/${shoe.id}`} className="group overflow-hidden rounded-2xl border border-line bg-white transition hover:-translate-y-0.5 hover:border-ink hover:shadow-[0_12px_30px_rgba(0,0,0,.08)]">
      {shoe.image_url ? (
        // eslint-disable-next-line @next/next/no-img-element -- catalog sources supply varying remote image hosts
        <img src={shoe.image_url} alt={`${shoe.brand} ${shoe.name}`} className="h-52 w-full bg-paper object-cover" />
      ) : (
        <div className="hatch flex h-52 items-center justify-center text-xs font-bold tracking-[.08em] text-faint uppercase">Catalog image unavailable</div>
      )}
      <div className="p-5">
        <div className="mb-1 text-[11px]/none font-bold tracking-[.07em] text-accent uppercase">{shoe.brand}</div>
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-lg/tight font-extrabold text-ink group-hover:underline">{shoe.name}</h2>
          <span className="shrink-0 text-sm font-bold">{priceLabel(shoe)}</span>
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {chips.map((chip) => <span key={chip} className="rounded-full bg-paper px-2 py-1 text-[11px] font-semibold text-muted">{chip}</span>)}
        </div>
      </div>
    </Link>
  );
}
