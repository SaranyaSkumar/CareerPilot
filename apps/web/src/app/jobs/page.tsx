"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  Archive, ArrowUpRight, BriefcaseBusiness, Building2, Check, ExternalLink,
  MapPin, Plus, Search, Settings2, Sparkles, Trash2, X,
} from "lucide-react";
import { WorkspaceHeader, WorkspaceNav } from "@/components/workspace-nav";
import { workspaceFetch } from "@/lib/workspace-fetch";

type Job = {
  id: number;
  title: string;
  company: string;
  location: string;
  description: string;
  url: string;
  source: string;
  salary: string;
  posted_at: string | null;
  status: "saved" | "archived" | "discovered";
  match_score: number | null;
  created_at: string;
  updated_at: string;
};

type JobDraft = {
  title: string;
  company: string;
  location: string;
  url: string;
  source: string;
  description: string;
};

type LinkDraft = { url: string; title: string; company: string; location: string; description: string };

type ProviderRun = { provider_key: string; label: string; status: string; message: string; fetched: number };
type LinkOut = { provider_key: string; label: string; url: string };
type Attribution = { label: string; url: string };
type DiscoverySettings = {
  search: { keywords: string; location: string; keywords_from_profile: boolean };
  providers: { provider_key: string; label: string; status: string; enabled: boolean }[];
  link_outs: LinkOut[];
  attributions: Attribution[];
};

const emptyDraft: JobDraft = {
  title: "", company: "", location: "New Zealand", url: "",
  source: "Manually added", description: "",
};
const emptyLink: LinkDraft = { url: "", title: "", company: "", location: "New Zealand", description: "" };
const field = "mt-1 w-full rounded-xl border border-[var(--line)] bg-white px-3.5 py-3 text-sm outline-none transition focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand-soft)]";
const sources = ["Adzuna", "Jooble", "SEEK", "LinkedIn", "Indeed", "Trade Me Jobs", "Manually added", "Added from link"];

function sourceClass(source: string): string {
  const key = source.toLowerCase();
  if (key.includes("adzuna")) return "bg-emerald-50 text-emerald-800";
  if (key.includes("jooble")) return "bg-sky-50 text-sky-800";
  if (key.includes("seek")) return "bg-pink-50 text-pink-800";
  if (key.includes("linkedin")) return "bg-blue-50 text-blue-800";
  if (key.includes("indeed")) return "bg-indigo-50 text-indigo-800";
  if (key.includes("trade")) return "bg-orange-50 text-orange-800";
  return "bg-slate-100 text-slate-600";
}

async function readDetail(response: Response): Promise<string> {
  const body = await response.json().catch(() => null) as { detail?: unknown } | null;
  return typeof body?.detail === "string" ? body.detail : "";
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("");
  const [source, setSource] = useState("");
  const [filter, setFilter] = useState<"discovered" | "saved" | "archived" | "all">("all");
  const [draft, setDraft] = useState<JobDraft>(emptyDraft);
  const [linkDraft, setLinkDraft] = useState<LinkDraft>(emptyLink);
  const [showForm, setShowForm] = useState(false);
  const [showLink, setShowLink] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [finding, setFinding] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [runs, setRuns] = useState<ProviderRun[]>([]);
  const [settings, setSettings] = useState<DiscoverySettings | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const requestId = useRef(0);

  const loadJobs = useCallback(async (status = filter) => {
    const id = ++requestId.current;
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ q: query, location, status, sort: "match" });
      if (source) params.set("source", source);
      const response = await workspaceFetch(`/api/v1/jobs?${params.toString()}`);
      if (!response.ok) throw new Error("Could not load your jobs.");
      if (id !== requestId.current) return;
      setJobs(await response.json() as Job[]);
    } catch (err) {
      if (id !== requestId.current) return;
      setError(err instanceof Error ? err.message : "Could not load your jobs.");
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, [query, location, filter, source]);

  const loadSettings = useCallback(async () => {
    const response = await workspaceFetch("/api/v1/jobs/discovery/settings");
    if (!response.ok) return;
    setSettings(await response.json() as DiscoverySettings);
  }, []);

  useEffect(() => { void loadJobs(); }, [loadJobs, refreshKey]);
  useEffect(() => { void loadSettings(); }, [loadSettings]);

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
      const response = await workspaceFetch("/api/v1/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draft),
      });
      if (!response.ok) throw new Error((await readDetail(response)) || "Could not save this job.");
      setDraft(emptyDraft);
      setShowForm(false);
      setFilter("saved");
      setQuery("");
      setLocation("");
      setSource("");
      setNotice("Job saved to your shortlist.");
      setRefreshKey(key => key + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save this job.");
    } finally {
      setSaving(false);
    }
  }

  async function addFromLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!linkDraft.url.trim()) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const response = await workspaceFetch("/api/v1/jobs/from-link", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(linkDraft),
      });
      if (!response.ok) throw new Error((await readDetail(response)) || "Could not add this job.");
      setLinkDraft(emptyLink);
      setShowLink(false);
      setFilter("saved");
      setNotice("Job added from the link.");
      setRefreshKey(key => key + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add this job.");
    } finally {
      setSaving(false);
    }
  }

  async function findJobs() {
    setFinding(true);
    setError("");
    setNotice("");
    try {
      const response = await workspaceFetch("/api/v1/jobs/discovery", { method: "POST" });
      if (!response.ok) throw new Error((await readDetail(response)) || "Jobs could not be found.");
      const body = await response.json() as DiscoverResult;
      setRuns(body.providers);
      setSettings(current => current ? { ...current, link_outs: body.link_outs, attributions: body.attributions, search: body.search } : current);
      setFilter("discovered");
      setQuery("");
      setLocation("");
      setSource("");
      const parts = [`Added ${body.created}.`];
      if (body.duplicates) parts.push(`${body.duplicates} already in your list.`);
      if (body.removed) parts.push(`Removed ${body.removed} that dropped out of this search.`);
      if (body.cached) parts.push("Saved results are still fresh, so the job sites were not called again.");
      setNotice(parts.join(" "));
      setRefreshKey(key => key + 1);
      await loadSettings();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Jobs could not be found.");
    } finally {
      setFinding(false);
    }
  }

  async function changeStatus(job: Job, status: "saved" | "archived") {
    setError("");
    try {
      const response = await workspaceFetch(`/api/v1/jobs/${job.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (!response.ok) throw new Error("Could not update this job.");
      setNotice(status === "archived" ? "Job moved to your archive." : "Job saved to your shortlist.");
      setRefreshKey(key => key + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update this job.");
    }
  }

  async function removeJob(job: Job) {
    if (!window.confirm(`Delete "${job.title}" from CareerPilot?`)) return;
    try {
      const response = await workspaceFetch(`/api/v1/jobs/${job.id}`, { method: "DELETE" });
      if (!response.ok) throw new Error("Could not delete this job.");
      setNotice("Job deleted.");
      setRefreshKey(key => key + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete this job.");
    }
  }

  const configuredApis = settings?.providers.filter(item => item.status === "not_configured") ?? [];

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
              <p className="mt-2 max-w-xl text-sm leading-6 text-[var(--muted)]">
                Find roles from Adzuna and Jooble, open a prefilled search on SEEK, LinkedIn, Indeed, or Trade Me, or paste a job link yourself.
                {settings ? ` Current search: ${settings.search.keywords} in ${settings.search.location}.` : ""}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button onClick={() => void findJobs()} disabled={finding} className="inline-flex items-center justify-center gap-2 rounded-xl bg-[var(--brand)] px-4 py-3 text-sm font-semibold text-white hover:bg-[var(--brand-dark)] disabled:opacity-60">
                <Sparkles size={17} /> {finding ? "Finding jobs…" : "Find jobs"}
              </button>
              <Link href="/jobs/preferences" className="inline-flex items-center justify-center gap-2 rounded-xl border border-[var(--line)] bg-white px-4 py-3 text-sm font-semibold text-[var(--foreground)] no-underline">
                <Settings2 size={17} /> Job sources
              </Link>
            </div>
          </div>

          {configuredApis.length > 0 && (
            <p className="mt-4 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">
              {configuredApis.map(item => item.label).join(" and ")} {configuredApis.length === 1 ? "is" : "are"} not configured, so {configuredApis.length === 1 ? "that source is" : "those sources are"} skipped. Add the API keys on the backend, or use the search buttons below.
            </p>
          )}

          {settings && settings.link_outs.length > 0 && (
            <div className="mt-5 flex flex-wrap gap-2">
              {settings.link_outs.map(item => (
                <a key={item.provider_key} href={item.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-full border border-[var(--line)] bg-white px-4 py-2 text-sm font-semibold text-[var(--foreground)] no-underline hover:bg-[var(--brand-soft)]">
                  {item.label} <ExternalLink size={14} />
                </a>
              ))}
            </div>
          )}
          <p className="mt-2 text-xs leading-5 text-[var(--muted)]">Those buttons open the job site with your search filled in. CareerPilot does not download SEEK, LinkedIn, Indeed, or Trade Me pages.</p>

          {runs.length > 0 && (
            <ul className="mt-4 grid gap-2 sm:grid-cols-2">
              {runs.map(run => (
                <li key={run.provider_key} className="rounded-xl border border-[var(--line)] bg-white px-4 py-3 text-sm">
                  <span className={`mr-2 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${run.status === "not_configured" || run.status === "error" || run.status === "rate_limited" ? "bg-amber-50 text-amber-800" : "bg-[var(--brand-soft)] text-[var(--brand)]"}`}>{run.label}</span>
                  {run.message}
                </li>
              ))}
            </ul>
          )}

          <div className="mt-6 flex flex-wrap gap-2">
            <button onClick={() => { setShowLink(value => !value); setShowForm(false); setError(""); }} className="inline-flex items-center gap-2 rounded-xl border border-[var(--line)] bg-white px-4 py-3 text-sm font-semibold">
              {showLink ? <X size={16} /> : <Plus size={16} />} {showLink ? "Close link form" : "Add job from link"}
            </button>
            <button onClick={() => { setShowForm(value => !value); setShowLink(false); setError(""); }} className="inline-flex items-center gap-2 rounded-xl border border-[var(--line)] bg-white px-4 py-3 text-sm font-semibold">
              {showForm ? <X size={16} /> : <Plus size={16} />} {showForm ? "Close form" : "Add details"}
            </button>
          </div>

          {showLink && (
            <form onSubmit={addFromLink} className="mt-4 rounded-2xl border border-[var(--line)] bg-white p-5 md:p-7">
              <h2 className="font-semibold">Add a job from a link</h2>
              <p className="mt-1 text-sm text-[var(--muted)]">Paste a public job URL. For SEEK, LinkedIn, Indeed, and Trade Me, paste the description as well. CareerPilot does not download those pages.</p>
              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <label className="text-sm font-medium md:col-span-2">Job URL <span className="text-red-600">*</span>
                  <input required type="url" maxLength={2000} className={field} value={linkDraft.url} onChange={event => setLinkDraft(current => ({ ...current, url: event.target.value }))} placeholder="https://company.co.nz/careers/job" />
                </label>
                <label className="text-sm font-medium">Title<input maxLength={200} className={field} value={linkDraft.title} onChange={event => setLinkDraft(current => ({ ...current, title: event.target.value }))} placeholder="Optional if the page can be read" /></label>
                <label className="text-sm font-medium">Company<input maxLength={200} className={field} value={linkDraft.company} onChange={event => setLinkDraft(current => ({ ...current, company: event.target.value }))} /></label>
                <label className="text-sm font-medium md:col-span-2">Job description<textarea maxLength={20000} rows={6} className={field + " resize-y"} value={linkDraft.description} onChange={event => setLinkDraft(current => ({ ...current, description: event.target.value }))} placeholder="Required for SEEK, LinkedIn, Indeed, and Trade Me." /></label>
              </div>
              <button type="submit" disabled={saving || !linkDraft.url.trim()} className="mt-5 inline-flex items-center gap-2 rounded-xl bg-[var(--brand)] px-5 py-3 text-sm font-semibold text-white disabled:opacity-60">{saving ? "Saving…" : <><Check size={16} /> Save job</>}</button>
            </form>
          )}

          {showForm && (
            <form onSubmit={addJob} className="mt-4 rounded-2xl border border-[var(--line)] bg-white p-5 md:p-7">
              <div className="flex items-start justify-between gap-3">
                <div><h2 className="font-semibold">Save a job opportunity</h2><p className="mt-1 text-sm text-[var(--muted)]">Paste the vacancy details or add a link to the original listing.</p></div>
                <span className="rounded-lg bg-[var(--brand-soft)] p-2 text-[var(--brand)]"><BriefcaseBusiness size={18} /></span>
              </div>
              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <label className="text-sm font-medium">Job title <span className="text-red-600">*</span><input required maxLength={200} className={field} value={draft.title} onChange={event => updateDraft("title", event.target.value)} placeholder="e.g. Software Engineer" /></label>
                <label className="text-sm font-medium">Company<input maxLength={200} className={field} value={draft.company} onChange={event => updateDraft("company", event.target.value)} placeholder="Company name" /></label>
                <label className="text-sm font-medium">Location<input maxLength={200} className={field} value={draft.location} onChange={event => updateDraft("location", event.target.value)} placeholder="Auckland, New Zealand" /></label>
                <label className="text-sm font-medium">Original job URL<input type="url" maxLength={2000} className={field} value={draft.url} onChange={event => updateDraft("url", event.target.value)} placeholder="https://company.co.nz/careers/job" /></label>
                <label className="text-sm font-medium md:col-span-2">Source<input maxLength={120} className={field} value={draft.source} onChange={event => updateDraft("source", event.target.value)} placeholder="Company careers page" /></label>
                <label className="text-sm font-medium md:col-span-2">Job description<textarea maxLength={20000} rows={7} className={field + " resize-y"} value={draft.description} onChange={event => updateDraft("description", event.target.value)} placeholder="Paste the job description here." /></label>
              </div>
              <div className="mt-5 flex flex-wrap items-center gap-3">
                <button type="submit" disabled={saving || !draft.title.trim()} className="inline-flex items-center gap-2 rounded-xl bg-[var(--brand)] px-5 py-3 text-sm font-semibold text-white disabled:opacity-60">{saving ? "Saving…" : <><Check size={16} /> Save opportunity</>}</button>
                <button type="button" onClick={() => { setDraft(emptyDraft); setShowForm(false); }} className="rounded-xl border border-[var(--line)] px-4 py-3 text-sm font-medium">Cancel</button>
              </div>
            </form>
          )}

          <div className="mt-7 rounded-2xl border border-[var(--line)] bg-white p-4 md:p-5">
            <div className="grid gap-3 md:grid-cols-[1fr_220px_200px]">
              <label className="relative block"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]" size={17} /><input aria-label="Search jobs" className={field + " pl-10"} value={query} onChange={event => setQuery(event.target.value)} placeholder="Search job title, company or skills…" /></label>
              <label className="relative block"><MapPin className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]" size={17} /><input aria-label="Filter by location" className={field + " pl-10"} value={location} onChange={event => setLocation(event.target.value)} placeholder="Filter by location" /></label>
              <label className="text-sm font-medium">Source
                <select aria-label="Filter by source" className={field} value={source} onChange={event => setSource(event.target.value)}>
                  <option value="">All sources</option>
                  {sources.map(item => <option key={item} value={item}>{item}</option>)}
                </select>
              </label>
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              {(["all", "discovered", "saved", "archived"] as const).map(value => (
                <button key={value} onClick={() => setFilter(value)} className={`rounded-full px-4 py-2 text-xs font-semibold capitalize ${filter === value ? "bg-[var(--brand)] text-white" : "bg-[var(--background)] text-[var(--muted)] hover:bg-[var(--brand-soft)]"}`}>
                  {value === "all" ? "All jobs" : value}
                </button>
              ))}
              <span className="ml-auto text-xs text-[var(--muted)]">{jobs.length} {jobs.length === 1 ? "result" : "results"}, highest match first</span>
            </div>
          </div>

          {(error || notice) && <div role="status" className={`mt-4 rounded-xl px-4 py-3 text-sm ${error ? "bg-red-50 text-red-700" : "bg-[var(--brand-soft)] text-[var(--brand)]"}`}>{error || notice}</div>}

          <div className="mt-5 space-y-3">
            {loading ? <div className="rounded-2xl border border-[var(--line)] bg-white p-10 text-center text-sm text-[var(--muted)]">Loading your opportunities…</div> :
              jobs.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-[var(--line)] bg-white px-6 py-14 text-center">
                  <span className="mx-auto grid size-12 place-items-center rounded-2xl bg-[var(--brand-soft)] text-[var(--brand)]"><Search size={22} /></span>
                  <h2 className="mt-4 font-semibold">{query || location || source ? "No matching jobs" : filter === "archived" ? "Nothing in your archive" : "No jobs in this view yet"}</h2>
                  <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[var(--muted)]">
                    {query || location || source ? "Try another keyword, location, or source." : "Find jobs uses your headline, skills, and location. You can also paste a link or add the details yourself."}
                  </p>
                  {!query && filter !== "archived" && <button onClick={() => void findJobs()} disabled={finding} className="mt-5 inline-flex items-center gap-2 rounded-xl bg-[var(--brand)] px-4 py-3 text-sm font-semibold text-white disabled:opacity-60"><Sparkles size={16} /> Find jobs</button>}
                </div>
              ) : jobs.map(job => (
                <article key={job.id} className="rounded-2xl border border-[var(--line)] bg-white p-5 md:p-6">
                  <div className="flex flex-col justify-between gap-4 sm:flex-row">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${sourceClass(job.source)}`}>{job.source}</span>
                        <span className="text-xs capitalize text-[var(--muted)]">{job.status}</span>
                        {job.match_score !== null && <span className="text-xs font-semibold text-[var(--brand)]">{job.match_score}/100 match</span>}
                      </div>
                      <h2 className="mt-3 text-lg font-semibold"><Link href={`/jobs/${job.id}`} className="text-[var(--foreground)] no-underline hover:text-[var(--brand)]">{job.title}</Link></h2>
                      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-[var(--muted)]">
                        <span className="inline-flex items-center gap-1.5"><Building2 size={14} />{job.company || "Company not specified"}</span>
                        <span className="inline-flex items-center gap-1.5"><MapPin size={14} />{job.location}</span>
                        {job.salary && <span>{job.salary}</span>}
                      </div>
                      {job.description && <p className="mt-4 whitespace-pre-line text-sm leading-6 text-slate-600">{job.description.length > 420 ? job.description.slice(0, 420).trimEnd() + "…" : job.description}</p>}
                      <p className="mt-3 text-xs text-[var(--muted)]">{job.posted_at ? `Posted ${new Date(job.posted_at).toLocaleDateString()}` : `Added ${new Date(job.created_at).toLocaleDateString()}`}</p>
                    </div>
                    <div className="flex shrink-0 flex-row flex-wrap items-start gap-2 sm:flex-col">
                      <Link href={`/jobs/${job.id}`} className="inline-flex items-center gap-2 rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-semibold text-[var(--brand)] no-underline hover:bg-[var(--brand-soft)]">View <ArrowUpRight size={13} /></Link>
                      {job.status !== "saved" && <button onClick={() => void changeStatus(job, "saved")} className="inline-flex items-center gap-2 rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-semibold text-[var(--foreground)]">Save</button>}
                      <button onClick={() => void changeStatus(job, job.status === "archived" ? "saved" : "archived")} className="inline-flex items-center gap-2 rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-semibold text-[var(--muted)] hover:bg-[var(--background)]">{job.status === "archived" ? <><ArrowUpRight size={13} /> Restore</> : <><Archive size={13} /> Archive</>}</button>
                      <button onClick={() => void removeJob(job)} className="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold text-slate-400 hover:bg-red-50 hover:text-red-600"><Trash2 size={13} /> Delete</button>
                    </div>
                  </div>
                </article>
              ))}
          </div>
          {settings && settings.attributions.length > 0 && (
            <p className="mt-6 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--muted)]">
              {settings.attributions.map(item => <a key={item.url} href={item.url} target="_blank" rel="noreferrer" className="font-semibold text-[var(--brand)]">{item.label}</a>)}
            </p>
          )}
          <p className="mt-4 text-xs leading-5 text-[var(--muted)]">Match scores compare the wording with your profile. They are indicative, not a hiring prediction. Results are cached so repeated searches stay inside the free API limits.</p>
        </div>
      </div>
    </main>
  );
}

type DiscoverResult = {
  cached: boolean;
  created: number;
  updated: number;
  duplicates: number;
  removed: number;
  providers: ProviderRun[];
  link_outs: LinkOut[];
  attributions: Attribution[];
  search: DiscoverySettings["search"];
};
