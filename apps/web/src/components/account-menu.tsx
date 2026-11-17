"use client";

import { useEffect, useState } from "react";
import { clearLocalDrafts } from "@/lib/draft-storage";
import { createClient } from "@/lib/supabase/client";

export function AccountMenu() {
  const [email, setEmail] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    const supabase = createClient();
    if (!supabase) return;
    void supabase.auth.getClaims().then(({ data }) => {
      const value = data?.claims?.email;
      if (typeof value === "string") setEmail(value);
    });
  }, []);

  async function signOut() {
    setPending(true);
    clearLocalDrafts();
    const supabase = createClient();
    if (supabase) await supabase.auth.signOut();
    window.location.assign("/login");
  }

  return (
    <div className="flex items-center gap-3">
      {email && <span className="hidden max-w-48 truncate text-sm text-slate-600 sm:inline">{email}</span>}
      <button
        type="button"
        onClick={signOut}
        disabled={pending}
        className="rounded-xl border border-[var(--line)] px-3 py-2 text-sm font-semibold text-[var(--foreground)] hover:bg-slate-50 disabled:opacity-60"
      >
        {pending ? "Signing out…" : "Sign out"}
      </button>
    </div>
  );
}
