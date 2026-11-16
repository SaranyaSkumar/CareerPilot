import Link from "next/link";
import { BriefcaseBusiness, FileUser, Gauge, Search, Target, TrendingUp } from "lucide-react";

const items = [
  { href: "/", label: "Overview", icon: Gauge },
  { href: "/profile", label: "Career profile", icon: Target },
  { href: "/cv", label: "CV Studio", icon: FileUser },
  { href: "/jobs", label: "Discover jobs", icon: Search },
  { href: "/applications", label: "Applications", icon: BriefcaseBusiness },
];

export function WorkspaceNav({ active }: { active: string }) {
  return (
    <aside className="fixed inset-y-0 left-0 z-20 hidden w-[248px] flex-col border-r border-[var(--line)] bg-white px-5 py-7 lg:flex">
      <Link href="/" className="flex items-center gap-3 px-2 no-underline">
        <span className="grid size-10 place-items-center rounded-xl bg-[var(--brand)] text-white"><TrendingUp size={21} /></span>
        <span><span className="block text-lg font-bold tracking-tight text-[var(--foreground)]">CareerPilot</span><span className="text-xs text-[var(--muted)]">Your career workspace</span></span>
      </Link>
      <div className="mt-12 px-3 text-[10px] font-semibold uppercase tracking-[.16em] text-[var(--muted)]">Workspace</div>
      <nav className="mt-3 space-y-1 text-sm">
        {items.map(({ href, label, icon: Icon }) => <Link key={href} href={href} className={`flex items-center gap-3 rounded-xl px-3 py-2.5 no-underline ${active === href ? "bg-[var(--brand-soft)] font-semibold text-[var(--brand)]" : "text-slate-600 hover:bg-slate-50"}`}><Icon size={17} />{label}</Link>)}
      </nav>
      <div className="mt-auto rounded-2xl bg-[var(--brand)] p-4 text-white">
        <p className="text-sm font-semibold">A clearer next step starts here.</p>
        <p className="mt-1 text-xs leading-5 text-white/70">Build your profile to get more relevant job matches.</p>
        <Link href="/profile" className="mt-4 inline-flex text-xs font-semibold text-white no-underline">Complete profile ↗</Link>
      </div>
    </aside>
  );
}

export function WorkspaceHeader() {
  return <header className="flex h-[76px] items-center justify-between border-b border-[var(--line)] bg-white/80 px-6 backdrop-blur md:px-10"><Link href="/" className="font-bold text-[var(--brand)] no-underline lg:hidden">CareerPilot</Link><span className="hidden text-sm text-[var(--muted)] lg:block">Your personal career workspace</span><span className="text-sm text-slate-600">Personal workspace</span></header>;
}
