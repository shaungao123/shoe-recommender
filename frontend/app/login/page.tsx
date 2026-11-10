"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState } from "react";

import { authCallbackUrl, rememberAuthNext, safeNextPath } from "@/lib/auth-redirect";
import { createClient } from "@/lib/supabase/client";
import { isSupabaseConfigured } from "@/lib/supabase/config";

type Mode = "sign-in" | "sign-up" | "check-email";

const inputClass =
  "w-full rounded-xl border-[1.5px] border-line bg-white px-4 py-3.5 text-[15px]/[1.4] outline-none focus:border-ink";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextPath = searchParams.get("next");
  const authError = searchParams.get("error") === "auth";

  const [mode, setMode] = useState<Mode>("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(authError ? "Sign-in didn’t finish. Try again." : null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!isSupabaseConfigured()) return;
    const supabase = createClient();
    void supabase.auth.getSession().then(({ data }) => {
      if (data.session) {
        router.replace(safeNextPath(nextPath));
      }
    });
  }, [nextPath, router]);

  if (!isSupabaseConfigured()) {
    return (
      <main className="mx-auto flex w-full max-w-[480px] flex-col px-6 py-16">
        <div className="rounded-2xl border border-line bg-white p-8 text-center">
          <h1 className="text-2xl font-extrabold tracking-[-.01em]">Sign-in isn’t set up yet</h1>
          <p className="mt-3 font-serif text-[15px]/normal text-muted">
            Add NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY to enable accounts.
          </p>
        </div>
      </main>
    );
  }

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const supabase = createClient();
    const next = safeNextPath(nextPath);
    rememberAuthNext(next);

    try {
      if (mode === "sign-in") {
        const { error: signInError } = await supabase.auth.signInWithPassword({ email, password });
        if (signInError) throw signInError;
        router.replace(next);
        router.refresh();
        return;
      }

      const { data, error: signUpError } = await supabase.auth.signUp({
        email,
        password,
        options: {
          // Exact allow-listed URL — no query string.
          emailRedirectTo: authCallbackUrl(),
          data: displayName.trim() ? { display_name: displayName.trim(), full_name: displayName.trim() } : undefined,
        },
      });
      if (signUpError) throw signUpError;
      if (!data.session) {
        setMode("check-email");
        return;
      }
      router.replace(next);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  const onGoogle = async () => {
    setBusy(true);
    setError(null);
    rememberAuthNext(safeNextPath(nextPath));
    const supabase = createClient();
    const { error: oauthError } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        // Must match Redirect URLs exactly (no ?next=…), or Supabase sends
        // the user to the production Site URL instead.
        redirectTo: authCallbackUrl(),
      },
    });
    if (oauthError) {
      setError(oauthError.message);
      setBusy(false);
    }
  };

  if (mode === "check-email") {
    return (
      <main className="mx-auto flex w-full max-w-[480px] flex-col px-6 py-16">
        <div className="rounded-2xl border border-line bg-white p-8 text-center">
          <div className="mx-auto mb-7 flex size-16 items-center justify-center rounded-full border-2 border-line bg-paper text-[26px]/none font-extrabold text-fainter">
            @
          </div>
          <h1 className="text-2xl font-extrabold tracking-[-.01em]">Check your email</h1>
          <p className="mt-3 font-serif text-[15px]/normal text-muted">
            We sent a confirmation link to {email}. Open it to finish creating your account.
          </p>
          <button
            type="button"
            onClick={() => setMode("sign-in")}
            className="mt-6 cursor-pointer rounded-full border-[1.5px] border-line px-[22px] py-3.5 text-sm/none font-semibold text-muted transition-colors hover:border-ink hover:text-ink"
          >
            Back to sign in
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto flex w-full max-w-[480px] flex-col px-6 py-12 pb-20">
      <div className="rounded-2xl border border-line bg-white p-8 sm:p-10">
        <div className="mb-2 text-xs/none font-bold tracking-[.08em] text-accent uppercase">The Assist</div>
        <h1 className="text-[28px]/tight font-extrabold tracking-[-.02em] text-ink">
          {mode === "sign-in" ? "Welcome back" : "Create your account"}
        </h1>
        <p className="mt-2 font-serif text-[15px]/normal text-muted">
          {mode === "sign-in"
            ? "Sign in to save shoes and keep your wishlist."
            : "Save shoes you like and come back to them anytime."}
        </p>

        <form onSubmit={(event) => void onSubmit(event)} className="mt-8 space-y-4">
          {mode === "sign-up" && (
            <label className="block">
              <span className="mb-2 block text-xs font-bold tracking-[.05em] text-muted uppercase">Display name</span>
              <input
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                className={inputClass}
                placeholder="What should we call you?"
                maxLength={80}
                autoComplete="name"
              />
            </label>
          )}
          <label className="block">
            <span className="mb-2 block text-xs font-bold tracking-[.05em] text-muted uppercase">Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={inputClass}
              placeholder="you@example.com"
              autoComplete="email"
            />
          </label>
          <label className="block">
            <span className="mb-2 block text-xs font-bold tracking-[.05em] text-muted uppercase">Password</span>
            <input
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className={inputClass}
              placeholder="At least 6 characters"
              autoComplete={mode === "sign-in" ? "current-password" : "new-password"}
            />
          </label>

          {error && (
            <div className="rounded-xl border border-line bg-paper px-4 py-3 text-sm font-semibold text-ink">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full cursor-pointer rounded-full bg-accent p-[18px] text-[15px]/none font-bold text-white shadow-[0_10px_24px_rgba(255,90,31,.28)] transition-colors hover:bg-accent-deep disabled:cursor-not-allowed disabled:opacity-40"
          >
            {mode === "sign-in" ? "Sign in" : "Create account"}
          </button>
        </form>

        <div className="my-5 flex items-center gap-3">
          <div className="h-px flex-1 bg-line" />
          <span className="text-xs font-bold tracking-[.05em] text-faint uppercase">or</span>
          <div className="h-px flex-1 bg-line" />
        </div>

        <button
          type="button"
          disabled={busy}
          onClick={() => void onGoogle()}
          className="w-full cursor-pointer rounded-full border border-line px-3.5 py-3.5 text-[13px]/none font-semibold text-muted transition-colors hover:border-ink hover:text-ink disabled:cursor-not-allowed disabled:opacity-40"
        >
          Continue with Google
        </button>

        <p className="mt-6 text-center text-sm text-muted">
          {mode === "sign-in" ? (
            <>
              New here?{" "}
              <button
                type="button"
                onClick={() => {
                  setMode("sign-up");
                  setError(null);
                }}
                className="cursor-pointer font-semibold text-muted underline decoration-line underline-offset-4 transition-colors hover:text-ink"
              >
                Create an account
              </button>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <button
                type="button"
                onClick={() => {
                  setMode("sign-in");
                  setError(null);
                }}
                className="cursor-pointer font-semibold text-muted underline decoration-line underline-offset-4 transition-colors hover:text-ink"
              >
                Sign in
              </button>
            </>
          )}
        </p>
      </div>
      <p className="mt-6 text-center text-sm text-muted">
        <Link href="/catalog" className="font-semibold underline decoration-line underline-offset-4 hover:text-ink">
          Back to catalog
        </Link>
      </p>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <main className="mx-auto w-full max-w-[480px] px-6 py-16">
          <div className="h-80 animate-pulse rounded-2xl border border-line bg-white" />
        </main>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
