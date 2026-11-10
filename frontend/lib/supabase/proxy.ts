import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

/** Refresh the auth cookie and rewrite OAuth codes that land on `/` to `/auth/callback`. */
export async function updateSession(request: NextRequest) {
  const url = request.nextUrl.clone();

  // Supabase falls back to Site URL (often production `/`) when redirectTo is
  // missing from the allow list. Forward the code to our PKCE handler.
  if (url.pathname === "/" && url.searchParams.has("code")) {
    url.pathname = "/auth/callback";
    return NextResponse.redirect(url);
  }

  let supabaseResponse = NextResponse.next({ request });

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!supabaseUrl || !anonKey) {
    return supabaseResponse;
  }

  const supabase = createServerClient(supabaseUrl, anonKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet, headers) {
        for (const { name, value } of cookiesToSet) {
          request.cookies.set(name, value);
        }
        supabaseResponse = NextResponse.next({ request });
        for (const { name, value, options } of cookiesToSet) {
          supabaseResponse.cookies.set(name, value, options);
        }
        Object.entries(headers).forEach(([key, value]) => {
          supabaseResponse.headers.set(key, value);
        });
      },
    },
  });

  // Refreshes the session cookie when needed so client nav stays signed in.
  await supabase.auth.getClaims();

  return supabaseResponse;
}
