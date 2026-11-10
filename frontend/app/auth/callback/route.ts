import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { AUTH_NEXT_COOKIE, safeNextPath } from "@/lib/auth-redirect";
import { createClient } from "@/lib/supabase/server";

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const cookieStore = await cookies();
  const next = safeNextPath(
    searchParams.get("next") ?? cookieStore.get(AUTH_NEXT_COOKIE)?.value ?? null,
  );

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      const response = NextResponse.redirect(`${origin}${next}`);
      response.cookies.set(AUTH_NEXT_COOKIE, "", { path: "/", maxAge: 0 });
      return response;
    }
  }

  return NextResponse.redirect(`${origin}/login?error=auth`);
}
