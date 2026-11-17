"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { AuthShell, authField } from "@/components/auth-shell";
import { safeNext } from "@/lib/safe-next";
import { createClient, isSupabaseConfigured } from "@/lib/supabase/client";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [nextPath, setNextPath] = useState("/");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState<"password" | "magic" | null>(null);
  const configured = isSupabaseConfigured();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setNextPath(safeNext(params.get("next")));
    if (params.get("error") === "auth") {
      setError("That sign-in link is invalid or has expired. Request a new one.");
    }
    if (params.get("error") === "config") {
      setError("Authentication is not configured.");
    }
  }, []);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    const supabase = createClient();
    if (!supabase) {
      setError("Authentication is not configured.");
      return;
    }
    setPending("password");
    const { error: signInError } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
    setPending(null);
    if (signInError) {
      setError(signInError.message);
      return;
    }
    window.location.assign(nextPath);
  }

  async function sendMagicLink() {
    setError("");
    setMessage("");
    const supabase = createClient();
    if (!supabase) {
      setError("Authentication is not configured.");
      return;
    }
    if (!email.trim()) {
      setError("Enter the email address for the sign-in link.");
      return;
    }
    setPending("magic");
    const { error: otpError } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: { emailRedirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(nextPath)}` },
    });
    setPending(null);
    if (otpError) {
      setError(otpError.message);
      return;
    }
    setMessage("Check your email for a sign-in link.");
  }

  return (
    <AuthShell title="Sign in" subtitle="Your profile, CV, and saved jobs stay private to this account.">
      {!configured && (
        <p className="mb-4 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY before signing in.
        </p>
      )}
      <form onSubmit={signIn} className="space-y-4">
        <label className="block text-sm font-medium">
          Email address
          <input className={authField} type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
        </label>
        <label className="block text-sm font-medium">
          Password
          <input className={authField} type="password" autoComplete="current-password" required minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} />
        </label>
        <button type="submit" disabled={pending !== null} className="inline-flex h-11 w-full items-center justify-center rounded-xl bg-[var(--brand)] text-sm font-semibold text-white hover:bg-[var(--brand-dark)] disabled:opacity-60">
          {pending === "password" ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <button type="button" onClick={sendMagicLink} disabled={pending !== null} className="mt-3 inline-flex h-11 w-full items-center justify-center rounded-xl border border-[var(--line)] text-sm font-semibold text-[var(--foreground)] hover:bg-slate-50 disabled:opacity-60">
        {pending === "magic" ? "Sending link…" : "Email me a sign-in link"}
      </button>
      {error && <p role="alert" className="mt-4 text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="mt-4 text-sm text-[var(--brand)]">{message}</p>}
      <div className="mt-6 flex flex-col gap-2 text-sm">
        <Link href="/forgot-password" className="font-medium text-[var(--brand)]">Forgot your password?</Link>
        <Link href="/signup" className="text-[var(--muted)]">New to CareerPilot? Create an account</Link>
      </div>
    </AuthShell>
  );
}
