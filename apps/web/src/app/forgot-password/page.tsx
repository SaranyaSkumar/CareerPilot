"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { AuthShell, authField } from "@/components/auth-shell";
import { createClient } from "@/lib/supabase/client";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);

  async function sendReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    const supabase = createClient();
    if (!supabase) {
      setError("Authentication is not configured.");
      return;
    }
    setPending(true);
    const { error: resetError } = await supabase.auth.resetPasswordForEmail(email.trim(), {
      redirectTo: `${window.location.origin}/auth/callback?next=/reset-password`,
    });
    setPending(false);
    if (resetError) {
      setError(resetError.message);
      return;
    }
    setMessage("If that email has an account, a reset link is on its way.");
  }

  return (
    <AuthShell title="Reset your password" subtitle="We'll email you a link to choose a new password.">
      <form onSubmit={sendReset} className="space-y-4">
        <label className="block text-sm font-medium">
          Email address
          <input className={authField} type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
        </label>
        <button type="submit" disabled={pending} className="inline-flex h-11 w-full items-center justify-center rounded-xl bg-[var(--brand)] text-sm font-semibold text-white hover:bg-[var(--brand-dark)] disabled:opacity-60">
          {pending ? "Sending…" : "Send reset link"}
        </button>
      </form>
      {error && <p role="alert" className="mt-4 text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="mt-4 text-sm text-[var(--brand)]">{message}</p>}
      <p className="mt-6 text-sm">
        <Link href="/login" className="font-medium text-[var(--brand)]">Back to sign in</Link>
      </p>
    </AuthShell>
  );
}
