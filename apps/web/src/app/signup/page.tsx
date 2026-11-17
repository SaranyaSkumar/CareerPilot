"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { AuthShell, authField } from "@/components/auth-shell";
import { createClient, isSupabaseConfigured } from "@/lib/supabase/client";

export default function SignUpPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  const configured = isSupabaseConfigured();

  async function signUp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    if (password !== confirm) {
      setError("Those passwords do not match.");
      return;
    }
    const supabase = createClient();
    if (!supabase) {
      setError("Authentication is not configured.");
      return;
    }
    setPending(true);
    const { data, error: signUpError } = await supabase.auth.signUp({
      email: email.trim(),
      password,
      options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
    });
    setPending(false);
    if (signUpError) {
      setError(signUpError.message);
      return;
    }
    if (data.session) {
      window.location.assign("/");
      return;
    }
    setMessage("Check your email to confirm this account, then sign in.");
  }

  return (
    <AuthShell title="Create your account" subtitle="Use an email and password. You can also ask for a sign-in link later.">
      {!configured && (
        <p className="mb-4 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY before creating an account.
        </p>
      )}
      <form onSubmit={signUp} className="space-y-4">
        <label className="block text-sm font-medium">
          Email address
          <input className={authField} type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
        </label>
        <label className="block text-sm font-medium">
          Password
          <input className={authField} type="password" autoComplete="new-password" required minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} />
        </label>
        <label className="block text-sm font-medium">
          Confirm password
          <input className={authField} type="password" autoComplete="new-password" required minLength={8} value={confirm} onChange={(event) => setConfirm(event.target.value)} />
        </label>
        <button type="submit" disabled={pending} className="inline-flex h-11 w-full items-center justify-center rounded-xl bg-[var(--brand)] text-sm font-semibold text-white hover:bg-[var(--brand-dark)] disabled:opacity-60">
          {pending ? "Creating account…" : "Create account"}
        </button>
      </form>
      {error && <p role="alert" className="mt-4 text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="mt-4 text-sm text-[var(--brand)]">{message}</p>}
      <p className="mt-6 text-sm text-[var(--muted)]">
        Already have an account? <Link href="/login" className="font-medium text-[var(--brand)]">Sign in</Link>
      </p>
    </AuthShell>
  );
}
