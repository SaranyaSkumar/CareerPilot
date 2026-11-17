"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Archive, ArrowLeft, Building2, Download, ExternalLink, MapPin, Sparkles, Trash2 } from "lucide-react";
import { WorkspaceHeader, WorkspaceNav } from "@/components/workspace-nav";
import { workspaceFetch } from "@/lib/workspace-fetch";

type JobMatch = {
  score: number | null;
  matched_skills: string[];
  not_found_skills: string[];
  detected_requirement_count: number;
  profile_ready: boolean;
  message: string;
};

type JobDetail = {
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
  created_at: string;
  match: JobMatch;
};

async function readDetail(response: Response): Promise<string> {
  const body = await response.json().catch(() => null) as { detail?: unknown } | null;
  return typeof body?.detail === "string" ? body.detail : "";
}

export default function JobDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const [job, setJob] = useState<JobDetail | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState<"pdf" | "docx" | null>(null);

  useEffect(() => {
    if (!id || !/^\d+$/.test(id)) {
      setError("Job not found.");
      setLoading(false);
      return;
    }
    let active = true;
    workspaceFetch(`/api/v1/jobs/${id}`)
      .then(async response => {
        if (response.status === 404) throw new Error("Job not found.");
        if (!response.ok) throw new Error((await readDetail(response)) || "Could not load this job.");
        return response.json() as Promise<JobDetail>;
      })
      .then(body => { if (active) setJob(body); })
      .catch(err => { if (active) setError(err instanceof Error ? err.message : "Could not load this job."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id]);

  async function changeStatus(status: "saved" | "archived") {
    if (!job) return;
    setError("");
    const response = await workspaceFetch(`/api/v1/jobs/${job.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    if (!response.ok) {
      setError("Could not update this job.");
      return;
    }
    const updated = await response.json() as { status: JobDetail["status"] };
    setJob(current => current ? { ...current, status: updated.status } : current);
    setNotice(status === "saved" ? "Saved to your shortlist." : "Moved to your archive.");
  }

  async function removeJob() {
    if (!job || !window.confirm(`Delete "${job.title}" from CareerPilot?`)) return;
    const response = await workspaceFetch(`/api/v1/jobs/${job.id}`, { method: "DELETE" });
    if (!response.ok) {
      setError("Could not delete this job.");
      return;
    }
    router.push("/jobs");
  }

  async function exportCv(format: "pdf" | "docx") {
    setExporting(format);
    setError("");
    setNotice("");
    try {
      const response = await workspaceFetch(`/api/v1/cv/export?format=${format}`, { method: "POST" });
      if (!response.ok) throw new Error((await readDetail(response)) || "The document could not be generated.");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `CareerPilot-CV.${format}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setNotice(`Downloaded your original ${format.toUpperCase()} CV. A tailored copy is a separate named variant in CV Studio.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The document could not be generated.");
    } finally {
      setExporting(null);
    }
  }

  return (
    <main className="min-h-screen">
      <WorkspaceNav active="/jobs" />
      <div className="lg:pl-[248px]">
        <WorkspaceHeader />
        <div className="mx-auto max-w-3xl px-6 py-9 md:px-10">
          <Link href="/jobs" className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--brand)] no-underline"><ArrowLeft size={16} /> All jobs</Link>
          {loading && <p className="mt-8 text-sm text-[var(--muted)]">Loading this job…</p>}
          {!loading && error && !job && <p className="mt-8 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700" role="status">{error}</p>}
          {job && (
            <article className="mt-6">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-[var(--brand-soft)] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-[var(--brand)]">{job.source}</span>
                <span className="text-xs capitalize text-[var(--muted)]">{job.status}</span>
              </div>
              <h1 className="mt-3 text-3xl font-semibold tracking-tight">{job.title}</h1>
              <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-[var(--muted)]">
                <span className="inline-flex items-center gap-1.5"><Building2 size={15} />{job.company || "Company not specified"}</span>
                <span className="inline-flex items-center gap-1.5"><MapPin size={15} />{job.location}</span>
                {job.salary && <span>{job.salary}</span>}
              </div>
              <p className="mt-2 text-xs text-[var(--muted)]">{job.posted_at ? `Posted ${new Date(job.posted_at).toLocaleDateString()}` : `Added ${new Date(job.created_at).toLocaleDateString()}`}</p>

              <div className="mt-6 flex flex-wrap gap-2">
                <Link href={`/cv?job=${job.id}#cv-ai`} className="inline-flex items-center gap-2 rounded-xl bg-[var(--brand)] px-4 py-3 text-sm font-semibold text-white no-underline hover:bg-[var(--brand-dark)]">
                  <Sparkles size={16} /> Tailor my CV for this job
                </Link>
                <button onClick={() => void exportCv("pdf")} disabled={exporting !== null} className="inline-flex items-center gap-2 rounded-xl border border-[var(--line)] bg-white px-4 py-3 text-sm font-semibold disabled:opacity-60"><Download size={16} />{exporting === "pdf" ? "Preparing PDF…" : "Download PDF"}</button>
                <button onClick={() => void exportCv("docx")} disabled={exporting !== null} className="inline-flex items-center gap-2 rounded-xl border border-[var(--line)] bg-white px-4 py-3 text-sm font-semibold disabled:opacity-60"><Download size={16} />{exporting === "docx" ? "Preparing Word…" : "Download Word"}</button>
                {job.url && <a href={job.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-xl border border-[var(--line)] bg-white px-4 py-3 text-sm font-semibold text-[var(--foreground)] no-underline">Original listing <ExternalLink size={15} /></a>}
              </div>
              <p className="mt-3 text-xs leading-5 text-[var(--muted)]">Tailor my CV opens CV Studio with this job selected. Accepting the suggestion saves a named variant, such as “Tailored – {job.title}{job.company ? ` @ ${job.company}` : ""}”, and does not replace your original CV. PDF and Word here download that original CV. Export the variant from CV Studio after you save it.</p>
              {!job.description.trim() && <p className="mt-4 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">This job has no description, so CV tailoring needs one before it can run.</p>}
              {(error || notice) && <p role="status" className={`mt-4 rounded-xl px-4 py-3 text-sm ${error ? "bg-red-50 text-red-700" : "bg-[var(--brand-soft)] text-[var(--brand)]"}`}>{error || notice}</p>}

              <section className="mt-6 rounded-2xl border border-[var(--line)] bg-white p-5">
                <h2 className="font-semibold">Description</h2>
                <p className="mt-3 whitespace-pre-line text-sm leading-6 text-slate-700">{job.description || "No description was saved with this job."}</p>
              </section>

              <section className="mt-4 rounded-2xl border border-[var(--line)] bg-white p-5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h2 className="font-semibold">Match to your profile</h2>
                  <span className="text-sm font-semibold text-[var(--brand)]">{job.match.score === null ? "Not enough detail to score" : `${job.match.score}/100 indicative match`}</span>
                </div>
                {!job.match.profile_ready && <p className="mt-2 text-xs text-amber-700">Add your professional headline and skills to Career Profile for a more useful comparison.</p>}
                {job.match.detected_requirement_count === 0 ? <p className="mt-2 text-sm text-[var(--muted)]">No recognised skills were found in this description, so CareerPilot has not invented a score.</p> : (
                  <div className="mt-3 grid gap-3 sm:grid-cols-2">
                    <div><p className="text-xs font-semibold text-[var(--muted)]">Found in your profile</p><p className="mt-1 text-sm">{job.match.matched_skills.length ? job.match.matched_skills.join(", ") : "No recognised matches yet"}</p></div>
                    <div><p className="text-xs font-semibold text-[var(--muted)]">Not found in your profile</p><p className="mt-1 text-sm">{job.match.not_found_skills.length ? job.match.not_found_skills.join(", ") : "None from the recognised terms"}</p></div>
                  </div>
                )}
                <p className="mt-3 text-xs leading-5 text-[var(--muted)]">{job.match.message}</p>
              </section>

              <div className="mt-4 flex flex-wrap gap-2">
                {job.status !== "saved" && <button onClick={() => void changeStatus("saved")} className="rounded-xl border border-[var(--line)] bg-white px-4 py-2.5 text-sm font-semibold">Save to shortlist</button>}
                <button onClick={() => void changeStatus(job.status === "archived" ? "saved" : "archived")} className="inline-flex items-center gap-2 rounded-xl border border-[var(--line)] bg-white px-4 py-2.5 text-sm font-semibold"><Archive size={15} />{job.status === "archived" ? "Restore" : "Archive"}</button>
                <button onClick={() => void removeJob()} className="inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-red-700 hover:bg-red-50"><Trash2 size={15} /> Delete</button>
              </div>
            </article>
          )}
        </div>
      </div>
    </main>
  );
}
