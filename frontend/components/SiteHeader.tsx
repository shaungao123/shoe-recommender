import Link from "next/link";

import { AccountNav } from "@/components/AccountNav";

export function SiteHeader() {
  return (
    <header className="mx-auto flex w-full max-w-[1180px] items-center justify-between px-6 pt-7 pb-2">
      <Link href="/" className="text-lg/none font-extrabold tracking-[-.01em]">
        The Assist
      </Link>
      <nav className="flex items-center gap-1">
        <Link
          href="/catalog"
          className="rounded-full px-3.5 py-2.5 text-[13px]/none font-semibold text-muted transition-colors hover:text-ink"
        >
          Catalog
        </Link>
        <Link
          href="/"
          className="rounded-full border border-line px-3.5 py-2.5 text-[13px]/none font-semibold text-muted transition-colors hover:border-ink hover:text-ink"
        >
          Find my shoe
        </Link>
        <AccountNav />
      </nav>
    </header>
  );
}
