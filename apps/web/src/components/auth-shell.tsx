import type { ReactNode } from "react";
import Link from "next/link";
import { TrendingUp } from "lucide-react";

export const authField =
  "mt-1 w-full rounded-xl border border-[var(--line)] bg-white px-3.5 py-3 text-sm text-[var(--foreground)] outline-none transition focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand-soft)]";

export function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <main className="min-h-screen px-6 py-16">
      <div className="mx-auto w-full max-w-md">
        <Link href="/login" className="flex items-center gap-3 no-underline">
          <span className="grid size-10 place-items-center rounded-xl bg-[var(--brand)] text-white">
            <TrendingUp size={21} />
          </span>
          <span>
            <span className="block text-lg font-bold tracking-tight text-[var(--foreground)]">CareerPilot</span>
            <span className="text-xs text-[var(--muted)]">Your career workspace</span>
          </span>
        </Link>
        <h1 className="mt-10 text-3xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-2 text-sm leading-6 text-[var(--muted)]">{subtitle}</p>
        <div className="mt-8 rounded-2xl border border-[var(--line)] bg-white p-6 md:p-8">{children}</div>
      </div>
    </main>
  );
}
