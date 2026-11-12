"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { CatalogCard } from "@/components/catalog/CatalogCard";
import { PreferencesForm } from "@/components/PreferencesForm";
import { createClient } from "@/lib/supabase/client";
import { isSupabaseConfigured } from "@/lib/supabase/config";
import { getMe, getWishlist, updateMe, type UserProfile, type WishlistItem } from "@/lib/wishlist";

const inputClass =
  "w-full rounded-xl border-[1.5px] border-line bg-white px-4 py-3.5 text-[15px]/[1.4] outline-none focus:border-ink";

export default function ProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [items, setItems] = useState<WishlistItem[]>([]);
  const [displayName, setDisplayName] = useState("");
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    if (!isSupabaseConfigured()) {
      router.replace("/login");
      return;
    }

    let active = true;
    void createClient()
      .auth.getSession()
      .then(async ({ data }) => {
        if (!active) return;
        if (!data.session) {
          router.replace("/login?next=/profile");
          return;
        }
        try {
          const [me, wishlist] = await Promise.all([getMe(), getWishlist()]);
          if (!active) return;
          setProfile(me);
          setDisplayName(me.display_name ?? "");
          setItems(wishlist.items);
          setStatus("ready");
        } catch {
          if (active) setStatus("error");
        }
      });

    return () => {
      active = false;
    };
  }, [router, reloadToken]);

  const onSaveName = async (event: FormEvent) => {
    event.preventDefault();
    setSaveState("saving");
    try {
      const updated = await updateMe(displayName.trim() || null);
      setProfile(updated);
      setDisplayName(updated.display_name ?? "");
      setSaveState("saved");
    } catch {
      setSaveState("error");
    }
  };

  if (status === "loading") {
    return (
      <main className="mx-auto w-full max-w-[1180px] px-6 py-12">
        <div className="h-40 animate-pulse rounded-2xl border border-line bg-white" />
        <div className="mt-8 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }, (_, index) => (
            <div key={index} className="h-[335px] animate-pulse rounded-2xl border border-line bg-white" />
          ))}
        </div>
      </main>
    );
  }

  if (status === "error" || !profile) {
    return (
      <main className="mx-auto w-full max-w-[640px] px-6 py-20 text-center">
        <div className="rounded-2xl border border-line bg-white p-10">
          <h1 className="text-xl font-extrabold">We couldn’t load your profile.</h1>
          <p className="mt-2 font-serif text-muted">Check that you’re signed in and try again.</p>
          <button
            type="button"
            onClick={() => {
              setStatus("loading");
              setReloadToken((token) => token + 1);
            }}
            className="mt-5 cursor-pointer rounded-full bg-ink px-5 py-2.5 text-sm font-bold text-white"
          >
            Try again
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-[1180px] px-6 py-8 pb-20">
      <div className="rounded-2xl border border-line bg-white p-6 sm:p-8">
        <div className="mb-1 text-xs/none font-bold tracking-[.08em] text-accent uppercase">Profile</div>
        <h1 className="text-[28px]/tight font-extrabold tracking-[-.02em] text-ink">Your wishlist</h1>
        <p className="mt-2 font-serif text-[15px]/normal text-muted">
          Signed in as {profile.email}. Update your display name and browse shoes you’ve saved.
        </p>
        <form onSubmit={(event) => void onSaveName(event)} className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="block flex-1">
            <span className="mb-2 block text-xs font-bold tracking-[.05em] text-muted uppercase">Display name</span>
            <input
              value={displayName}
              onChange={(event) => {
                setDisplayName(event.target.value);
                setSaveState("idle");
              }}
              className={inputClass}
              maxLength={80}
              placeholder="Your name"
            />
          </label>
          <button
            type="submit"
            disabled={saveState === "saving"}
            className="cursor-pointer rounded-full bg-accent px-6 py-[15px] text-[15px]/none font-bold text-white transition-colors hover:bg-accent-deep disabled:cursor-not-allowed disabled:opacity-40"
          >
            Save name
          </button>
        </form>
        {saveState === "saved" && <p className="mt-2 text-sm font-semibold text-muted">Display name saved.</p>}
        {saveState === "error" && <p className="mt-2 text-sm font-semibold text-ink">Couldn’t save that name. Try again.</p>}
      </div>

      <PreferencesForm />

      <div className="mt-10 mb-4 flex items-end justify-between gap-4">
        <h2 className="text-[22px]/tight font-extrabold tracking-[-.01em]">Saved shoes</h2>
        <span className="text-sm font-semibold text-muted">
          {items.length} {items.length === 1 ? "shoe" : "shoes"}
        </span>
      </div>

      {items.length === 0 ? (
        <div className="rounded-2xl border border-line bg-white p-10 text-center">
          <h2 className="text-xl font-extrabold">No shoes saved yet.</h2>
          <p className="mt-2 font-serif text-muted">Browse the catalog and tap Save on any shoe you want to keep.</p>
          <Link href="/catalog" className="mt-5 inline-block rounded-full bg-ink px-5 py-2.5 text-sm font-bold text-white">
            Browse catalog
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((item) => (
            <CatalogCard
              key={item.shoe.id}
              shoe={item.shoe}
              canSave
              saved
              onSavedChange={(nextSaved) => {
                if (!nextSaved) {
                  setItems((current) => current.filter((row) => row.shoe.id !== item.shoe.id));
                }
              }}
            />
          ))}
        </div>
      )}
    </main>
  );
}
