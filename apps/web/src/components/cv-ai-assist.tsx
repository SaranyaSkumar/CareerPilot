"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { SuggestionReview, type AiResult } from "@/components/cv-suggestion-review";
import { variantLabel, type CvContent } from "@/lib/cv-suggestions";
import { workspaceFetch } from "@/lib/workspace-fetch";

type JobOption = { id: number; title: string; company: string; description: string };

type AiStatus = {
  configured: boolean;
  model: string;
  request_cap_usd: string;
  daily_cap_usd: string;
  daily_spent_usd: string;
  monthly_cap_usd: string;
  monthly_spent_usd: string;
};

type Review = { base: CvContent; result: AiResult };

const fieldClass = "mt-1 w-full rounded-xl border border-[var(--line)] bg-white px-3.5 py-3 text-sm outline-none focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand-soft)]";

async function readDetail(response: Response): Promise<string> {
  const body = await response.json().catch(() => null) as { detail?: unknown } | null;
  return typeof body?.detail === "string" ? body.detail : "";
}

export function CvAiAssist({
  cv,
  editorBusy,
  onDraftPersisted,
  onApplied,
  onVariantCreated,
}: {
  cv: CvContent;
  editorBusy: boolean;
  onDraftPersisted: (cv: CvContent) => void;
  onApplied: (cv: CvContent, message: string, refreshVersions: boolean) => void;
  onVariantCreated?: () => void;
}) {
  const [phase, setPhase] = useState<"loading" | "unconfigured" | "ready" | "unavailable">("loading");
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [jobs, setJobs] = useState<JobOption[]>([]);
  const [jobId, setJobId] = useState("");
  const [selectedLines, setSelectedLines] = useState<Record<number, boolean>>({});
  const [busy, setBusy] = useState<"tailor" | "improve" | "save" | null>(null);
  const [message, setMessage] = useState("");
  const [review, setReview] = useState<Review | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([
      workspaceFetch("/api/v1/cv/ai/status"),
      workspaceFetch("/api/v1/jobs?status=saved"),
    ]).then(async ([statusResponse, jobsResponse]) => {
      if (!active) return;
      if (statusResponse.status === 503) {
        const detail = await readDetail(statusResponse);
        if (!active) return;
        setPhase(detail === "AI not configured." ? "unconfigured" : "unavailable");
      } else if (statusResponse.ok) {
        const body = await statusResponse.json() as AiStatus;
        if (!active) return;
        setStatus(body);
        setPhase("ready");
      } else if (active) {
        setPhase("unavailable");
      }
      if (jobsResponse.ok) {
        const saved = await jobsResponse.json() as JobOption[];
        if (active) setJobs(saved);
      }
    }).catch(() => {
      if (active) setPhase("unavailable");
    });
    return () => { active = false; };
  }, []);

  const lines = cv.experience.split("\n").map((text, index) => ({ index, text })).filter(line => line.text.trim());
  const dailyReached = status !== null && Number(status.daily_spent_usd) >= Number(status.daily_cap_usd);
  const selectedJob = jobs.find(job => String(job.id) === jobId) ?? null;
  const stale = review !== null && JSON.stringify(review.base) !== JSON.stringify(cv);
  const configured = phase === "ready";

  async function persistDraft(): Promise<CvContent | null> {
    const response = await workspaceFetch("/api/v1/cv", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cv),
    });
    if (!response.ok) {
      setMessage((await readDetail(response)) || "Save your CV before asking for a suggestion.");
      return null;
    }
    const saved = await response.json() as CvContent & { id: number };
    const next = {
      name: saved.name,
      headline: saved.headline,
      summary: saved.summary,
      experience: saved.experience,
      skills: saved.skills,
      education: saved.education,
    };
    onDraftPersisted(next);
    return next;
  }

  async function refreshStatus() {
    const response = await workspaceFetch("/api/v1/cv/ai/status");
    if (!response.ok) return;
    setStatus(await response.json() as AiStatus);
    setPhase("ready");
  }

  async function requestSuggestion(kind: "tailor" | "improve") {
    setMessage("");
    if (kind === "tailor" && jobId === "") {
      setMessage("Choose one of your saved jobs.");
      return;
    }
    if (kind === "tailor" && selectedJob && !selectedJob.description.trim()) {
      setMessage("That saved job has no description to tailor against.");
      return;
    }
    const bullets = lines.filter(line => selectedLines[line.index]).map(line => line.text);
    if (kind === "improve" && bullets.length === 0) {
      setMessage("Select at least one experience line to rewrite.");
      return;
    }
    setBusy(kind);
    try {
      const saved = await persistDraft();
      if (!saved) return;
      const response = await workspaceFetch(kind === "tailor" ? "/api/v1/cv/ai/tailor" : "/api/v1/cv/ai/improve-bullets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(kind === "tailor" ? { job_id: Number(jobId) } : { bullets }),
      });
      if (!response.ok) {
        const detail = await readDetail(response);
        if (response.status === 503 && detail === "AI not configured.") {
          setPhase("unconfigured");
          setReview(null);
          setMessage("AI not configured.");
          return;
        }
        setMessage(detail || "A suggestion could not be prepared.");
        return;
      }
      const result = await response.json() as AiResult;
      setReview({ base: saved, result });
      setMessage("Review each suggestion. Nothing is saved until you accept it.");
      await refreshStatus();
    } catch {
      setMessage("A suggestion could not be prepared.");
    } finally {
      setBusy(null);
    }
  }

  async function saveAccepted(next: CvContent, saveVersion: boolean) {
    if (!review || stale) return;
    setBusy("save");
    setMessage("");
    try {
      if (review.result.operation === "tailor" || review.result.operation === "adjust") {
        const label = variantLabel(review.result.job_title, review.result.company);
        const response = await workspaceFetch("/api/v1/cv/variants", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ...next,
            label,
            job_title: review.result.job_title,
            company: review.result.company,
            job_id: review.result.job_id,
          }),
        });
        if (!response.ok) {
          setMessage((await readDetail(response)) || "The tailored CV could not be saved.");
          return;
        }
        setReview(null);
        setMessage(`Saved “${label}” as its own CV. Your original draft was not changed.`);
        onVariantCreated?.();
        return;
      }
      const response = await workspaceFetch("/api/v1/cv", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(next),
      });
      if (!response.ok) {
        setMessage((await readDetail(response)) || "The accepted changes could not be saved.");
        return;
      }
      let versionNote = "";
      if (saveVersion) {
        const version = await workspaceFetch("/api/v1/cv/versions", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ label: "Clearer bullet points" }),
        });
        versionNote = version.ok
          ? " A saved version was added as well."
          : " The draft was saved, but the version could not be created.";
      }
      setReview(null);
      onApplied(next, `Accepted suggestions are now in your CV draft.${versionNote}`, saveVersion);
    } catch {
      setMessage("The accepted changes could not be saved.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="mt-6 rounded-2xl border border-[var(--line)] bg-white p-5" aria-labelledby="cv-ai-heading">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles className="text-[var(--brand)]" size={18} />
            <h2 id="cv-ai-heading" className="font-semibold">AI writing help</h2>
          </div>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-[var(--muted)]">
            Your current draft is saved first, so the suggestion uses the facts on screen. A tailored CV is saved as its own named variant and does not replace this draft. Bullet rewrites still update the draft, and only after you accept them.
          </p>
        </div>
      </div>

      {phase === "loading" ? <p className="mt-4 text-sm text-[var(--muted)]">Checking whether AI writing is available…</p> : null}
      {phase === "unconfigured" ? (
        <p className="mt-4 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">
          AI not configured. Add an Anthropic API key on the backend to tailor a CV or rewrite bullets. Editing, export, and the keyword analyser keep working.
        </p>
      ) : null}
      {phase === "unavailable" ? <p className="mt-4 text-sm text-[var(--muted)]">AI assistance is unavailable right now.</p> : null}

      {configured && status ? (
        <p className="mt-3 text-xs text-[var(--muted)]">
          Using {status.model}. Each request is limited to US${status.request_cap_usd}. Today US${status.daily_spent_usd} of US${status.daily_cap_usd}. This month the workspace has used US${status.monthly_spent_usd} of US${status.monthly_cap_usd}.
        </p>
      ) : null}
      {dailyReached ? <p className="mt-2 text-sm text-amber-800">You have reached today’s AI limit of US${status?.daily_cap_usd}.</p> : null}

      <div className="mt-4 grid gap-5 lg:grid-cols-2">
        <div>
          <h3 className="text-sm font-semibold">Tailor to a saved job</h3>
          <label className="mt-2 block text-sm font-medium">Saved job
            <select className={fieldClass} value={jobId} onChange={event => setJobId(event.target.value)} disabled={!configured || editorBusy}>
              <option value="">Choose a job</option>
              {jobs.map(job => <option key={job.id} value={job.id}>{job.title}{job.company ? ` · ${job.company}` : ""}</option>)}
            </select>
          </label>
          {jobs.length === 0 && configured ? <p className="mt-2 text-xs text-[var(--muted)]">Save a job, including its description, in <Link href="/jobs" className="font-semibold text-[var(--brand)]">Discover jobs</Link>.</p> : null}
          <button type="button" onClick={() => void requestSuggestion("tailor")} disabled={!configured || dailyReached || editorBusy || busy !== null} className="mt-3 rounded-xl bg-[var(--brand)] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60">
            {busy === "tailor" ? "Preparing suggestion…" : "Suggest a tailored CV"}
          </button>
        </div>
        <div>
          <h3 className="text-sm font-semibold">Improve bullet points</h3>
          <p className="mt-1 text-xs text-[var(--muted)]">Choose lines from your original CV. Accepted rewrites update that draft. A tailored CV for a saved job, including jobs added by discovery, is stored as a separate variant.</p>
          <div className="mt-2 max-h-48 space-y-2 overflow-auto rounded-xl border border-[var(--line)] p-3">
            {lines.length === 0 ? <p className="text-sm text-[var(--muted)]">Add experience lines to rewrite them.</p> : null}
            {lines.map(line => (
              <label key={line.index} className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={selectedLines[line.index] === true}
                  onChange={event => setSelectedLines(current => ({ ...current, [line.index]: event.target.checked }))}
                  disabled={!configured || editorBusy}
                />
                <span className="whitespace-pre-wrap">{line.text}</span>
              </label>
            ))}
          </div>
          <button type="button" onClick={() => void requestSuggestion("improve")} disabled={!configured || dailyReached || editorBusy || busy !== null} className="mt-3 rounded-xl border border-[var(--line)] bg-white px-4 py-2.5 text-sm font-semibold disabled:opacity-60">
            {busy === "improve" ? "Rewriting…" : "Rewrite selected bullets"}
          </button>
        </div>
      </div>

      {message ? <p className="mt-4 text-sm" role="status">{message}</p> : null}

      {review ? (
        <SuggestionReview
          key={`${review.result.operation}-${review.result.input_tokens}-${review.result.output_tokens}-${review.result.job_id ?? "pasted"}`}
          base={review.base}
          result={review.result}
          stale={stale}
          busy={busy === "save"}
          jobDescription={review.result.operation === "improve_bullets" ? "" : (selectedJob?.description ?? "")}
          saveLabel={review.result.operation === "improve_bullets" ? "Save accepted changes" : "Save as new CV variant"}
          showVersionOption={review.result.operation === "improve_bullets"}
          onSave={saveAccepted}
          onDiscard={() => { setReview(null); setMessage("Suggestions discarded. Nothing from the suggestion was saved."); }}
        />
      ) : null}
    </section>
  );
}
