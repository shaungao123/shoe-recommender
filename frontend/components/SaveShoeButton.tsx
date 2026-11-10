"use client";

import { useCallback, useEffect, useState, type MouseEvent } from "react";

import { createClient } from "@/lib/supabase/client";
import { isSupabaseConfigured } from "@/lib/supabase/config";
import { addToWishlist, getWishlist, removeFromWishlist } from "@/lib/wishlist";

interface SaveShoeButtonProps {
  shoeId: number;
  /** When known from a parent that already loaded the wishlist. */
  initiallySaved?: boolean;
  /** When false, hide the control entirely (signed-out browsing). */
  visible?: boolean;
  className?: string;
  compact?: boolean;
  onChange?: (saved: boolean) => void;
}

export function SaveShoeButton({
  shoeId,
  initiallySaved,
  visible,
  className = "",
  compact = false,
  onChange,
}: SaveShoeButtonProps) {
  const configured = isSupabaseConfigured();
  const parentOwnsState = initiallySaved !== undefined;
  const parentControlsVisibility = visible !== undefined;

  const [signedIn, setSignedIn] = useState(parentControlsVisibility ? Boolean(visible) : false);
  const [authReady, setAuthReady] = useState(parentControlsVisibility || !configured);
  const [fetchedSaved, setFetchedSaved] = useState(false);
  const [ready, setReady] = useState(parentOwnsState || !configured);
  const [localSaved, setLocalSaved] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);

  const show = parentControlsVisibility ? Boolean(visible) : signedIn;
  const saved = localSaved ?? (parentOwnsState ? Boolean(initiallySaved) : fetchedSaved);

  useEffect(() => {
    if (parentControlsVisibility || !configured) {
      return;
    }

    let active = true;
    const supabase = createClient();
    void supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSignedIn(Boolean(data.session));
      setAuthReady(true);
    });

    const { data: subscription } = supabase.auth.onAuthStateChange((_event, session) => {
      setSignedIn(Boolean(session));
      setAuthReady(true);
    });

    return () => {
      active = false;
      subscription.subscription.unsubscribe();
    };
  }, [configured, parentControlsVisibility]);

  useEffect(() => {
    if (!show || parentOwnsState || !configured) return;

    let active = true;
    void getWishlist()
      .then((wishlist) => {
        if (!active) return;
        setFetchedSaved(wishlist.items.some((item) => item.shoe.id === shoeId));
      })
      .catch(() => {
        if (active) setFetchedSaved(false);
      })
      .finally(() => {
        if (active) setReady(true);
      });

    return () => {
      active = false;
    };
  }, [configured, parentOwnsState, shoeId, show]);

  const onClick = useCallback(
    async (event: MouseEvent) => {
      event.preventDefault();
      event.stopPropagation();
      if (!show || busy || (!parentOwnsState && !ready)) return;

      const wasSaved = saved;
      setBusy(true);
      try {
        if (wasSaved) {
          await removeFromWishlist(shoeId);
          setLocalSaved(false);
          onChange?.(false);
        } else {
          await addToWishlist(shoeId);
          setLocalSaved(true);
          onChange?.(true);
        }
      } catch {
        setLocalSaved(wasSaved);
      } finally {
        setBusy(false);
      }
    },
    [busy, onChange, parentOwnsState, ready, saved, shoeId, show],
  );

  if (!configured || !authReady || !show) {
    return null;
  }

  const label = busy ? "…" : saved ? "Saved" : compact ? "Save" : "Add to wishlist";

  return (
    <button
      type="button"
      onClick={(event) => void onClick(event)}
      aria-pressed={saved}
      aria-label={saved ? "Remove from wishlist" : "Add to wishlist"}
      className={`cursor-pointer rounded-full border-[1.5px] text-[13px]/none font-semibold transition-colors ${
        compact ? "px-3 py-2" : "px-4 py-2.5"
      } ${
        saved ? "border-ink bg-ink text-white" : "border-line bg-white text-ink hover:border-ink"
      } ${className}`}
    >
      {label}
    </button>
  );
}

/** Load saved shoe ids once for a list of cards. */
export function useWishlistIds() {
  const configured = isSupabaseConfigured();
  const [ids, setIds] = useState<Set<number> | null>(() => (configured ? null : new Set()));
  const [signedIn, setSignedIn] = useState(false);
  const [ready, setReady] = useState(!configured);

  useEffect(() => {
    if (!configured) return;

    let active = true;
    const supabase = createClient();
    void supabase.auth.getSession().then(async ({ data }) => {
      if (!active) return;
      if (!data.session) {
        setSignedIn(false);
        setIds(new Set());
        setReady(true);
        return;
      }
      setSignedIn(true);
      try {
        const wishlist = await getWishlist();
        if (!active) return;
        setIds(new Set(wishlist.items.map((item) => item.shoe.id)));
      } catch {
        if (active) setIds(new Set());
      } finally {
        if (active) setReady(true);
      }
    });

    const { data: subscription } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!session) {
        setSignedIn(false);
        setIds(new Set());
        setReady(true);
      }
    });

    return () => {
      active = false;
      subscription.subscription.unsubscribe();
    };
  }, [configured]);

  const markSaved = useCallback((shoeId: number, saved: boolean) => {
    setIds((prev) => {
      const next = new Set(prev ?? []);
      if (saved) next.add(shoeId);
      else next.delete(shoeId);
      return next;
    });
  }, []);

  return { ids, signedIn, markSaved, ready: ready && ids !== null };
}
