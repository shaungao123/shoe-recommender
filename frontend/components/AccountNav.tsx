"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { carryOverQuizAnswers } from "@/lib/preferences";
import { createClient } from "@/lib/supabase/client";
import { isSupabaseConfigured } from "@/lib/supabase/config";

type AuthState = "loading" | "signed-out" | "signed-in";

export function AccountNav() {
  const router = useRouter();
  const configured = isSupabaseConfigured();
  const [state, setState] = useState<AuthState>(configured ? "loading" : "signed-out");

  useEffect(() => {
    if (!configured) return;

    const supabase = createClient();
    let active = true;

    void supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setState(data.session ? "signed-in" : "signed-out");
      if (data.session) void carryOverQuizAnswers();
    });

    const { data: subscription } = supabase.auth.onAuthStateChange((event, session) => {
      setState(session ? "signed-in" : "signed-out");
      // A quiz taken while logged out becomes this account's preferences.
      if (event === "SIGNED_IN") void carryOverQuizAnswers();
    });

    return () => {
      active = false;
      subscription.subscription.unsubscribe();
    };
  }, [configured]);

  const signOut = async () => {
    if (!configured) return;
    const supabase = createClient();
    await supabase.auth.signOut();
    setState("signed-out");
    router.refresh();
  };

  if (!configured) {
    return null;
  }

  if (state === "loading") {
    return <span className="rounded-full px-3.5 py-2.5 text-[13px]/none font-semibold text-faint">…</span>;
  }

  if (state === "signed-out") {
    return (
      <Link
        href="/login"
        className="rounded-full border border-line px-3.5 py-2.5 text-[13px]/none font-semibold text-muted transition-colors hover:border-ink hover:text-ink"
      >
        Sign in
      </Link>
    );
  }

  return (
    <>
      <Link
        href="/profile"
        className="rounded-full px-3.5 py-2.5 text-[13px]/none font-semibold text-muted transition-colors hover:text-ink"
      >
        Profile
      </Link>
      <button
        type="button"
        onClick={() => void signOut()}
        className="cursor-pointer rounded-full border border-line px-3.5 py-2.5 text-[13px]/none font-semibold text-muted transition-colors hover:border-ink hover:text-ink"
      >
        Sign out
      </button>
    </>
  );
}
