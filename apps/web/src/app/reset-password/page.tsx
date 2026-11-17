"use client";

import { FormEvent, useState } from "react";
import { AuthShell, authField } from "@/components/auth-shell";
import { createClient } from "@/lib/supabase/client";

export default function ResetPasswordPage() {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function updatePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
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
    const { error: updateError } = await supabase.auth.updateUser({ password });
    setPending(false);
    if (updateError) {
      setError(updateError.message);
      return;
    }
    window.location.assign("/");
  }

  return (
    <AuthShell title="Choose a new password" subtitle="Use at least 8 characters. You'll stay signed in afterwards.">
      <form onSubmit={updatePassword} className="space-y-4">
        <label className="block text-sm font-medium">
          New password
          <input className={authField} type="password" autoComplete="new-password" required minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} />
        </label>
        <label className="block text-sm font-medium">
          Confirm password
          <input className={authField} type="password" autoComplete="new-password" required minLength={8} value={confirm} onChange={(event) => setConfirm(event.target.value)} />
        </label>
        <button type="submit" disabled={pending} className="inline-flex h-11 w-full items-center justify-center rounded-xl bg-[var(--brand)] text-sm font-semibold text-white hover:bg-[var(--brand-dark)] disabled:opacity-60">
          {pending ? "Saving…" : "Update password"}
        </button>
      </form>
      {error && <p role="alert" className="mt-4 text-sm text-red-700">{error}</p>}
    </AuthShell>
  );
}
