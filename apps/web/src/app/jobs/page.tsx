"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  Archive, ArrowUpRight, BriefcaseBusiness, Building2, Check, ExternalLink,
  MapPin, Plus, Search, Trash2, X,
} from "lucide-react";
import { WorkspaceHeader, WorkspaceNav } from "@/components/workspace-nav";

type Job = {
  id: number;
  title: string;
  company: string;
  location: string;
  description: string;
  url: string;
  source: string;
  status: "saved" | "archived";
  created_at: string;
  updated_at: string;
};

type MatchResult = {
  score: number;
  label: string;
  components: { name: string; score: number; out_of: number; detail: string }[];
  matched_skills: string[];
  not_found_in_profile: string[];
  limitations: string[];
};

type JobDraft = {
  title: string;
  company: string;
  location: string;
  url: string;
  source: string;
  description: string;
};

const emptyDraft: JobDraft = {
  title: "", company: "", location: "New Zealand", url: "",
  source: "Manually added", description: "",
};

const field = "mt-1 w-full rounded-xl border border-[var(--line)] bg-white px-3.5 py-3 text-sm outline-none transition focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand-soft)]";

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("");
  const [filter, setFilter] = useState<"saved" | "archived" | "all">("saved");
  const [draft, setDraft] = useState<JobDraft>(emptyDraft);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");\n  const [matches, setMatches] = useState<Record<number, MatchResult>>({});\n  const [matchingId, setMatchingId] = useState<number | null>(null);

  const loadJobs = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ q: query, location, status: filter });
      const response = await fetch(`/api/v1/jobs?${params.toString()}`, { cache: "no-store" });
      if (!response.ok) throw new Error("Could not load your saved jobs.");
      setJobs(await response.json() as Job[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load your saved jobs.");
    } finally {
      setLoading(false);
    }
  }, [query, location, filter]);

  useEffect(() => { void loadJobs(); }, [loadJobs]);

  function updateDraft<K extends keyof JobDraft>(key: K, value: JobDraft[K]) {
    setDraft(current => ({ ...current, [key]: value }));
  }

  async function addJob(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.title.trim()) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch("/api/v1/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draft),
      });
      const body = await response.json().catch(() => null) as { detail?: string } | null;
      if (!response.ok) throw new Error(body?.detail || "Could not save this job.");
      setDraft(emptyDraft);
      setShowForm(false);
      setFilter("saved");
      setQuery("");
      setLocation("");
      setNotice("Job saved to your opportunities.");
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save this job.");
    } finally {
      setSaving(false);
    }
  }

  async function changeStatus(job: Job, status: "saved" | "archived") {
    setError("");
    try {
      const response = await fetch(`/api/v1/jobs/${job.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (!response.ok) throw new Error("Could not update this job.");
      setNotice(status === "archived" ? "Job moved to your archive." : "Job restored to saved opportunities.");
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update this job.");
    }
  }

  async function matchJob(job: Job) {
    setMatchingId(job.id);
    setError("");
    try {
      const response = await fetch(`/api/v1/jobs/${job.id}/match`, { cache: "no-store" });
      const body = await response.json().catch(() => null) as MatchResult | { detail?: string } | null;
      if (!response.ok) throw new Error(body && "detail" in body ? body.detail || "Could not compare this job." : "Could not compare this job.");
      setMatches(current => ({ ...current, [job.id]: body as MatchResult }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not compare this job.");
    } finally {
      setMatchingId(null);
    }
  }

  async function removeJob(job: Job) {
    if (!window.confirm(`Delete "${job.title}" from CareerPilot?`)) return;
    try {
      const response = await fetch(`/api/v1/jobs/${job.id}`, { method: "DELETE" });
      if (!response.ok) throw new Error("Could not delete this job.");
      setNotice("Job deleted.");
      await loadJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete this job.");
    }
  }

  return (
    <main className="min-h-screen">
      <WorkspaceNav active="/jobs" />
      <div className="lg:pl-[248px]">
        <WorkspaceHeader />
        <div className="mx-auto max-w-6xl px-6 py-9 md:px-10">
          <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
            <div>
              <p className="text-sm font-semibold text-[var(--brand)]">NEW ZEALAND FIRST</p>
              <h1 className="mt-1 text-3xl font-semibold tracking-tight">Discover opportunities</h1>
              <p className="mt-2 max-w-xl text-sm leading-6 text-[var(--muted)]">Keep interesting roles in one place. Add a vacancy from a careers page or paste its details to start building your shortlist.</p>
            </div>
            <button onClick={() => { setShowForm(value => !value); setError(""); }} className="inline-flex items-center justify-center gap-2 rounded-xl bg-[var(--brand)] px-4 py-3 text-sm font-semibold text-white hover:bg-[var(--brand-dark)]">
              {showForm ? <X size={17}/> : <Plus size={17}/>} {showForm ? "Close form" : "Add a job"}
            </button>
          </div>

          <div className="mt-7 grid gap-3 sm:grid-cols-3">
            <div className="rounded-2xl border border-[var(--line)] bg-white p-4"><p className="text-xs text-[var(--muted)]">Results in this view</p><p className="mt-1 text-2xl font-semibold tabular-nums">{jobs.length}</p></div>
            <div className="rounded-2xl border border-[var(--line)] bg-white p-4"><p className="text-xs text-[var(--muted)]">Showing</p><p className="mt-1 text-2xl font-semibold">{filter === "saved" ? "Shortlist" : filter === "archived" ? "Archive" : "All jobs"}</p></div>
            <div className="rounded-2xl border border-[var(--line)] bg-white p-4"><p className="text-xs text-[var(--muted)]">Built for</p><p className="mt-1 text-2xl font-semibold">New Zealand</p></div>
          </div>

          {showForm && (
            <form onSubmit={addJob} className="mt-6 rounded-2xl border border-[var(--line)] bg-white p-5 md:p-7">
              <div className="flex items-start justify-between gap-3">
                <div><h2 className="font-semibold">Save a job opportunity</h2><p className="mt-1 text-sm text-[var(--muted)]">Paste the vacancy details or add a link to the original listing.</p></div>
                <span className="rounded-lg bg-[var(--brand-soft)] p-2 text-[var(--brand)]"><BriefcaseBusiness size={18}/></span>
              </div>
              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <label className="text-sm font-medium">Job title <span className="text-red-600">*</span><input required maxLength={200} className={field} value={draft.title} onChange={e => updateDraft("title", e.target.value)} placeholder="e.g. Software Engineer"/></label>
                <label className="text-sm font-medium">Company<input maxLength={200} className={field} value={draft.company} onChange={e => updateDraft("company", e.target.value)} placeholder="Company name"/></label>
                <label className="text-sm font-medium">Location<input maxLength={200} className={field} value={draft.location} onChange={e => updateDraft("location", e.target.value)} placeholder="Auckland, New Zealand"/></label>
                <label className="text-sm font-medium">Original job URL<input type="url" maxLength={2000} className={field} value={draft.url} onChange={e => updateDraft("url", e.target.value)} placeholder="https://company.co.nz/careers/job"/></label>
                <label className="text-sm font-medium md:col-span-2">Source<input maxLength={120} className={field} value={draft.source} onChange={e => updateDraft("source", e.target.value)} placeholder="Company careers page, SEEK, Trade Me Jobs…"/></label>
                <label className="text-sm font-medium md:col-span-2">Job description<textarea maxLength={20000} rows={7} className={field + " resize-y"} value={draft.description} onChange={e => updateDraft("description", e.target.value)} placeholder="Paste the job description here. Keep the original wording so matching can use it later."/></label>
              </div>
              <div className="mt-5 flex flex-wrap items-center gap-3"><button type="submit" disabled={saving || !draft.title.trim()} className="inline-flex items-center gap-2 rounded-xl bg-[var(--brand)] px-5 py-3 text-sm font-semibold text-white disabled:opacity-60">{saving ? "Saving…" : <><Check size={16}/>Save opportunity</>}</button><button type="button" onClick={() => { setDraft(emptyDraft); setShowForm(false); }} className="rounded-xl border border-[var(--line)] px-4 py-3 text-sm font-medium">Cancel</button></div>
            </form>
          )}

          <div className="mt-7 rounded-2xl border border-[var(--line)] bg-white p-4 md:p-5">
            <div className="grid gap-3 md:grid-cols-[1fr_220px]">
              <label className="relative block"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]" size={17}/><input aria-label="Search saved jobs" className={field + " pl-10"} value={query} onChange={e => setQuery(e.target.value)} placeholder="Search job title, company or skills…"/></label>
              <label className="relative block"><MapPin className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]" size={17}/><input aria-label="Filter by location" className={field + " pl-10"} value={location} onChange={e => setLocation(e.target.value)} placeholder="Filter by location"/></label>
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              {(["saved", "archived", "all"] as const).map(value => <button key={value} onClick={() => setFilter(value)} className={`rounded-full px-4 py-2 text-xs font-semibold capitalize ${filter === value ? "bg-[var(--brand)] text-white" : "bg-[var(--background)] text-[var(--muted)] hover:bg-[var(--brand-soft)]"}`}>{value === "saved" ? "Saved" : value === "archived" ? "Archived" : "All jobs"}</button>)}
              <span className="ml-auto text-xs text-[var(--muted)]">{jobs.length} {jobs.length === 1 ? "result" : "results"}</span>
            </div>
          </div>

          {(error || notice) && <div role="status" className={`mt-4 rounded-xl px-4 py-3 text-sm ${error ? "bg-red-50 text-red-700" : "bg-[var(--brand-soft)] text-[var(--brand)]"}`}>{error || notice}</div>}

          <div className="mt-5 space-y-3">
            {loading ? <div className="rounded-2xl border border-[var(--line)] bg-white p-10 text-center text-sm text-[var(--muted)]">Loading your opportunities…</div> :
              jobs.length === 0 ? <div className="rounded-2xl border border-dashed border-[var(--line)] bg-white px-6 py-14 text-center"><span className="mx-auto grid size-12 place-items-center rounded-2xl bg-[var(--brand-soft)] text-[var(--brand)]"><Search size={22}/></span><h2 className="mt-4 font-semibold">{query || location ? "No matching jobs" : filter === "archived" ? "Nothing in your archive" : "Your shortlist starts here"}</h2><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[var(--muted)]">{query || location ? "Try another keyword or location." : "When you find a role on a careers page, add its link and description here. Your saved opportunities will be ready for matching and application tracking."}</p>{!query && filter !== "archived" && <button onClick={() => setShowForm(true)} className="mt-5 inline-flex items-center gap-2 rounded-xl bg-[var(--brand)] px-4 py-3 text-sm font-semibold text-white"><Plus size={16}/>Add your first job</button>}</div> :
              jobs.map(job => <article key={job.id} className="rounded-2xl border border-[var(--line)] bg-white p-5 md:p-6">
                <div className="flex flex-col justify-between gap-4 sm:flex-row">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2"><span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${job.status === "saved" ? "bg-[var(--brand-soft)] text-[var(--brand)]" : "bg-slate-100 text-slate-500"}`}>{job.status}</span><span className="text-xs text-[var(--muted)]">{job.source}</span></div>
                    <h2 className="mt-3 text-lg font-semibold">{job.title}</h2>
                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-[var(--muted)]"><span className="inline-flex items-center gap-1.5"><Building2 size={14}/>{job.company || "Company not specified"}</span><span className="inline-flex items-center gap-1.5"><MapPin size={14}/>{job.location}</span></div>
                    {job.description && <p className="mt-4 whitespace-pre-line text-sm leading-6 text-slate-600">{job.description.length > 420 ? job.description.slice(0, 420).trimEnd() + "…" : job.description}</p>}
                    <p className="mt-3 text-xs text-[var(--muted)]">Added {new Date(job.created_at).toLocaleDateString()}</p>
                    <div className="mt-4">
                      <button onClick={() => void matchJob(job)} disabled={matchingId === job.id} className="rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-semibold text-[var(--brand)] disabled:opacity-60">{matchingId === job.id ? "Comparing…" : matches[job.id] ? "Refresh match" : "Compare with my profile"}</button>
                      {matches[job.id] && <div className="mt-3 rounded-xl bg-[var(--background)] p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2"><div><p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Indicative match</p><p className="mt-1 text-sm font-semibold">{matches[job.id].label}</p></div><p className="text-2xl font-semibold tabular-nums">{matches[job.id].score}<span className="text-sm text-[var(--muted)]">/100</span></p></div>
                        <div className="mt-3 space-y-2">{matches[job.id].components.map(item => <div key={item.name}><div className="flex justify-between gap-3 text-xs"><span className="font-medium">{item.name}</span><span className="tabular-nums text-[var(--muted)]">{item.score}/{item.out_of}</span></div><p className="mt-0.5 text-xs leading-5 text-[var(--muted)]">{item.detail}</p></div>)}</div>
                        {matches[job.id].matched_skills.length > 0 && <p className="mt-3 text-xs"><span className="font-semibold">Found in your profile/CV:</span> {matches[job.id].matched_skills.join(", ")}</p>}
                        {matches[job.id].not_found_in_profile.length > 0 && <p className="mt-2 text-xs"><span className="font-semibold">Not found in saved profile/CV:</span> {matches[job.id].not_found_in_profile.join(", ")}</p>}
                        <ul className="mt-3 list-disc space-y-1 pl-4 text-[11px] leading-4 text-[var(--muted)]">{matches[job.id].limitations.map((item, index) => <li key={index}>{item}</li>)}</ul>
                      </div>}
                    </div>
                  </div>
                  <div className="flex shrink-0 flex-row flex-wrap items-start gap-2 sm:flex-col">
                    {job.url && <a href={job.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-semibold text-[var(--foreground)] no-underline hover:bg-[var(--background)]">Original listing <ExternalLink size={13}/></a>}
                    <button onClick={() => void changeStatus(job, job.status === "saved" ? "archived" : "saved")} className="inline-flex items-center gap-2 rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-semibold text-[var(--muted)] hover:bg-[var(--background)]">{job.status === "saved" ? <><Archive size={13}/>Archive</> : <><ArrowUpRight size={13}/>Restore</>}</button>
                    <button onClick={() => void removeJob(job)} className="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold text-slate-400 hover:bg-red-50 hover:text-red-600"><Trash2 size={13}/>Delete</button>
                  </div>
                </div>
              </article>)
            }
          </div>
          <p className="mt-6 text-xs leading-5 text-[var(--muted)]">This first release saves job links and descriptions you provide. It does not scrape job boards or claim to show live vacancies. Automated source integrations will be added only where permitted by each provider.</p>
        </div>
      </div>
    </main>
  );
}
