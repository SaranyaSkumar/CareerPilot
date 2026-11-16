import { ArrowUpRight, BriefcaseBusiness, FileUser, Gauge, Search, Sparkles, Target, TrendingUp } from "lucide-react";

const quickActions = [
  { icon: FileUser, title: "Build your CV", description: "Create an ATS-friendly CV from your career profile", href: "#cv" },
  { icon: Search, title: "Find opportunities", description: "Discover roles that fit your skills and goals", href: "#jobs" },
  { icon: Target, title: "Review job fit", description: "Understand strengths, gaps, and next steps", href: "#matching" },
];

const stages = ["Interested", "Preparing", "Applied", "Interview"];

export default function Home() {
  return (
    <main className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 hidden w-[248px] flex-col border-r border-[var(--line)] bg-white px-5 py-7 lg:flex">
        <a href="#" className="flex items-center gap-3 px-2 no-underline">
          <span className="grid size-10 place-items-center rounded-xl bg-[var(--brand)] text-white"><TrendingUp size={21} /></span>
          <span><span className="block text-lg font-bold tracking-tight text-[var(--foreground)]">CareerPilot</span><span className="text-xs text-[var(--muted)]">Your career workspace</span></span>
        </a>
        <div className="mt-12 px-3 text-[10px] font-semibold uppercase tracking-[.16em] text-[var(--muted)]">Workspace</div>
        <nav className="mt-3 space-y-1 text-sm">
          {[
            ["Overview", Gauge, true], ["Discover jobs", Search, false], ["CV Studio", FileUser, false],
            ["Applications", BriefcaseBusiness, false], ["Career profile", Target, false],
          ].map(([label, Icon, active]) => {
            const ItemIcon = Icon as typeof Gauge;
            return <a key={label as string} href="#" className={`flex items-center gap-3 rounded-xl px-3 py-2.5 no-underline ${active ? "bg-[var(--brand-soft)] font-semibold text-[var(--brand)]" : "text-slate-600 hover:bg-slate-50"}`}><ItemIcon size={17} />{label as string}</a>;
          })}
        </nav>
        <div className="mt-auto rounded-2xl bg-[var(--brand)] p-4 text-white">
          <Sparkles size={18} className="text-[#e6c58d]" />
          <p className="mt-3 text-sm font-semibold">A clearer next step starts here.</p>
          <p className="mt-1 text-xs leading-5 text-white/70">Build your profile to get more relevant job matches.</p>
          <a href="#profile" className="mt-4 inline-flex items-center gap-2 text-xs font-semibold text-white no-underline">Complete profile <ArrowUpRight size={14} /></a>
        </div>
      </aside>

      <div className="lg:pl-[248px]">
        <header className="flex h-[76px] items-center justify-between border-b border-[var(--line)] bg-white/80 px-6 backdrop-blur md:px-10">
          <div className="lg:hidden flex items-center gap-2 font-bold"><span className="grid size-8 place-items-center rounded-lg bg-[var(--brand)] text-white"><TrendingUp size={17} /></span>CareerPilot</div>
          <div className="hidden text-sm text-[var(--muted)] lg:block">Tuesday, 17 November 2026</div>
          <div className="flex items-center gap-3"><span className="hidden text-sm text-slate-600 sm:block">Your personal career workspace</span><span className="grid size-9 place-items-center rounded-full bg-[#e8eee8] text-sm font-semibold text-[var(--brand)]">S</span></div>
        </header>

        <div className="mx-auto max-w-[1180px] px-6 py-9 md:px-10 md:py-12">
          <section className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
            <div><p className="text-sm font-semibold text-[var(--brand)]">YOUR CAREER, IN ONE PLACE</p><h1 className="mt-3 text-3xl font-semibold tracking-tight md:text-[38px]">Make your next move count.</h1><p className="mt-2 max-w-xl text-sm leading-6 text-[var(--muted)]">Discover the right opportunities, put your experience forward, and keep your job search moving.</p></div>
            <button className="inline-flex h-11 items-center justify-center gap-2 self-start rounded-xl bg-[var(--brand)] px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-[var(--brand-dark)] md:self-auto"> <Sparkles size={16} /> Start with your profile</button>
          </section>

          <section className="mt-9 grid gap-4 md:grid-cols-3">
            {quickActions.map(({ icon: Icon, title, description, href }) => <a key={title} href={href} className="group rounded-2xl border border-[var(--line)] bg-white p-5 no-underline transition hover:-translate-y-0.5 hover:shadow-md"><span className="grid size-10 place-items-center rounded-xl bg-[var(--brand-soft)] text-[var(--brand)]"><Icon size={19} /></span><span className="mt-5 flex items-center justify-between text-base font-semibold text-[var(--foreground)]">{title}<ArrowUpRight size={16} className="text-[var(--muted)] transition group-hover:-translate-y-0.5 group-hover:translate-x-0.5" /></span><span className="mt-1 block text-sm leading-5 text-[var(--muted)]">{description}</span></a>)}
          </section>

          <section className="mt-9 grid gap-5 lg:grid-cols-[1.4fr_1fr]">
            <div className="rounded-2xl border border-[var(--line)] bg-white p-6">
              <div className="flex items-center justify-between"><div><h2 className="font-semibold">Your job search</h2><p className="mt-1 text-sm text-[var(--muted)]">A snapshot of your application pipeline</p></div><BriefcaseBusiness size={19} className="text-[var(--muted)]" /></div>
              <div className="mt-7 grid grid-cols-2 gap-3 sm:grid-cols-4">{stages.map((stage, index) => <div key={stage} className="rounded-xl bg-[#f7f8f5] p-3"><p className="text-xs text-[var(--muted)]">{stage}</p><p className="mt-2 text-2xl font-semibold tabular-nums">—</p><p className="mt-1 text-[10px] text-[var(--muted)]">{index === 0 ? "Saved roles" : index === 1 ? "In progress" : index === 2 ? "Submitted" : "Upcoming"}</p></div>)}</div>
              <div className="mt-6 rounded-xl border border-dashed border-[var(--line)] px-4 py-5 text-center"><p className="text-sm font-medium">Your pipeline will appear here</p><p className="mt-1 text-xs text-[var(--muted)]">Save a role to start tracking your progress.</p></div>
            </div>
            <div className="rounded-2xl border border-[var(--line)] bg-white p-6">
              <div className="flex items-center gap-2"><Gauge size={18} className="text-[var(--brand)]" /><h2 className="font-semibold">Profile readiness</h2></div>
              <p className="mt-1 text-sm text-[var(--muted)]">A strong profile helps us assess job fit accurately.</p>
              <div className="mt-6 flex items-end justify-between"><span className="text-3xl font-semibold">—</span><span className="text-xs text-[var(--muted)]">Not assessed yet</span></div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-[#edf0eb]"><div className="h-full w-0 rounded-full bg-[var(--brand)]" /></div>
              <ul className="mt-5 space-y-3 text-sm text-slate-600"><li className="flex items-center gap-2"><span className="size-1.5 rounded-full bg-[#c6cec6]" />Career history</li><li className="flex items-center gap-2"><span className="size-1.5 rounded-full bg-[#c6cec6]" />Skills and strengths</li><li className="flex items-center gap-2"><span className="size-1.5 rounded-full bg-[#c6cec6]" />Career preferences</li></ul>
              <a href="#profile" className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-[var(--brand)] no-underline">Set up your profile <ArrowUpRight size={15} /></a>
            </div>
          </section>

          <footer className="mt-10 flex flex-col justify-between gap-2 border-t border-[var(--line)] pt-5 text-xs text-[var(--muted)] sm:flex-row"><span>CareerPilot · Your next career move, guided by AI.</span><span>AI suggestions stay under your control.</span></footer>
        </div>
      </div>
    </main>
  );
}
