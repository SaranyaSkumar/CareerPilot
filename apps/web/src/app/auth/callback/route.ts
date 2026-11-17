import { NextResponse } from "next/server";
import { safeNext } from "@/lib/safe-next";
import { createClient } from "@/lib/supabase/server";

const OTP_TYPES = ["signup", "invite", "magiclink", "recovery", "email", "email_change"] as const;

type OtpType = (typeof OTP_TYPES)[number];

function isOtpType(value: string): value is OtpType {
  return (OTP_TYPES as readonly string[]).includes(value);
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const next = safeNext(url.searchParams.get("next"));
  const supabase = await createClient();
  if (!supabase) {
    return NextResponse.redirect(new URL("/login?error=config", url.origin));
  }

  const code = url.searchParams.get("code");
  if (code) {
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) return NextResponse.redirect(new URL(next, url.origin));
  }

  const tokenHash = url.searchParams.get("token_hash");
  const type = url.searchParams.get("type");
  if (tokenHash && type && isOtpType(type)) {
    const { error } = await supabase.auth.verifyOtp({ token_hash: tokenHash, type });
    if (!error) return NextResponse.redirect(new URL(next, url.origin));
  }

  return NextResponse.redirect(new URL("/login?error=auth", url.origin));
}
