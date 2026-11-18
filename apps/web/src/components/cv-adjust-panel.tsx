"use client";

import { useEffect, useMemo, useState } from "react";
import { SuggestionReview, type AiResult } from "@/components/cv-suggestion-review";
import { variantLabel, type CvContent } from "@/lib/cv-suggestions";
import { workspaceFetch } from "@/lib/workspace-fetch";

async function readDetail(response: Response): Promise<string> {
  const body = await response.json().catch(() => null) as { detail?: unknown } | null;
  return typeof body?.detail === "string" ? body.detail : "";
}

export function CvAdjustPanel({
  cv,
  jobDescription,
  analysis,
  disabled,
  onVariantCreated,
}: {
  cv: CvContent;
  jobDescription: string;
  disabled: boolean;
  onVariantCreated: () => void;
}) {
  const [jobTitle, setJobTitle] = useState("");
  const [profiles, setProfiles] = useState<Array<{id:number;name:string;cv_name:string;headline:string;summary:string;experience:string;skills:string;education:string}>>([]);
  const [profileId, setProfileId] = useState("");
  useEffect(() => { const initial = new URLSearchParams(window.location.search).get("profile"); if (initial && /^\d+$/.test(initial)) setProfileId(initial); workspaceFetch("/api/v1/career-profiles").then(async r => { if (r.ok) setProfiles(await r.json()); }).catch(() => undefined); }, []);
  const selectedProfile = profiles.find(p => String(p.id) === profileId);
  const sourceCv = useMemo<CvContent>(() => selectedProfile ? ({
    name: selectedProfile.cv_name || cv.name, headline: selectedProfile.headline, summary: selectedProfile.summary,
    experience: selectedProfile.experience, skills: selectedProfile.skills, education: selectedProfile.education,
  }) : cv, [selectedProfile, cv]);
  const [company, setCompany] = useState("");
  const [userInstructions, setUserInstructions] = useState("");
  const [busy, setBusy] = useState<"adjust" | "save" | null>(null);
  const [message, setMessage] = useState("");
  const [review, setReview] = useState<{ base: CvContent; result: AiResult } | null>(null);
  const field = "mt-1 w-full rounded-xl border border-[var(--line)] bg-white px-3.5 py-3 text-sm outline-none focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand-soft)]";

  if (!jobDescription.trim()) return null;

  async function createSuggestion() {
    setBusy("adjust");
    setMessage("");
    try {
      const saved = profileId ? null : await workspaceFetch("/api/v1/cv", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cv),
      });
      if (saved && !saved.ok) {
        setMessage((await readDetail(saved)) || "Save your CV before creating an adjusted version.");
        return;
      }
      const response = await workspaceFetch("/api/v1/cv/ai/adjust", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          profile_id: profileId ? Number(profileId) : null,
          job_description: jobDescription,
          job_title: jobTitle,
          company,
          user_instructions: userInstructions,
        }),
      });
      if (!response.ok) {
        setMessage((await readDetail(response)) || "An adjusted CV could not be prepared.");
        return;
      }
      const result = await response.json() as AiResult;
      setReview({ base: sourceCv, result });
      setMessage("Review the adjusted CV. Your original draft will not be replaced.");
    } catch {
      setMessage("An adjusted CV could not be prepared.");
    } finally {
      setBusy(null);
    }
  }

  async function saveVariant(draft: CvContent) {
    if (!review) return;
    setBusy("save");
    setMessage("");
    const label = variantLabel(jobTitle || review.result.job_title, company || review.result.company);
    try {
      const response = await workspaceFetch("/api/v1/cv/variants", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...draft,
          label,
          job_title: jobTitle || review.result.job_title,
          company: company || review.result.company,
          job_description: jobDescription,
          profile_id: profileId ? Number(profileId) : null,
        }),
      });
      if (!response.ok) {
        setMessage((await readDetail(response)) || "The adjusted CV could not be saved.");
        return;
      }
      setReview(null);
      setMessage(`Saved “${label}” under ${selectedProfile?.name ?? "Master CV"}. Your source CV was not changed.`);
      onVariantCreated();
    } catch {
      setMessage("The adjusted CV could not be saved.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mt-5 border-t border-[var(--line)] pt-5">
      <h3 className="text-sm font-semibold">Generate your tailored CV</h3>
      <p className="mt-1 text-xs leading-5 text-[var(--muted)]">
        Generate a job-specific CV from your selected source profile. CareerPilot will prioritise relevant experience and naturally use supported job keywords without inventing skills or achievements. Your original CV stays unchanged.
      </p>
      <label className="mt-3 block text-sm font-medium">Tailor from profile
        <select className={field} value={profileId} onChange={event => setProfileId(event.target.value)}>
          <option value="">Master CV</option>
          {profiles.map(profile => <option key={profile.id} value={profile.id}>{profile.name}</option>)}
        </select>
      </label>
      <p className="mt-1 text-xs text-[var(--muted)]">{selectedProfile ? `Using the independent “${selectedProfile.name}” profile as the source. Your master CV will not be changed.` : "Using your master CV as the source."}</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="text-sm font-medium">Role title <span className="font-normal text-[var(--muted)]">(optional)</span>
          <input className={field} value={jobTitle} onChange={event => setJobTitle(event.target.value)} placeholder="e.g. Backend Engineer" />
        </label>
        <label className="text-sm font-medium">Company <span className="font-normal text-[var(--muted)]">(optional)</span>
          <input className={field} value={company} onChange={event => setCompany(event.target.value)} placeholder="e.g. Northwind" />
        </label>
      </div>
      <label className="mt-3 block text-sm font-medium">Regeneration instructions <span className="font-normal text-[var(--muted)]">(optional)</span>
        <textarea className={field + " min-h-24 resize-y"} value={userInstructions} onChange={event => setUserInstructions(event.target.value)} placeholder="For example: Give more emphasis to API development, rewrite the summary for this role, remove Azure, and include PostgreSQL only where my experience supports it." />
      </label>
      <button type="button" onClick={() => void createSuggestion()} disabled={disabled || busy !== null} className="mt-3 rounded-xl bg-[var(--brand)] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60">
        {busy === "adjust" ? "Generating tailored CV…" : review ? "Regenerate tailored CV" : "Generate tailored CV"}
      </button>
      {message ? <p className="mt-3 text-sm" role="status">{message}</p> : null}
      {review ? (
        <SuggestionReview
          key={`${review.result.input_tokens}-${review.result.output_tokens}`}
          base={review.base}
          result={review.result}
          stale={false}
          busy={busy === "save"}
          jobDescription={jobDescription}
          saveLabel="Save tailored CV"
          showVersionOption={false}
          onSave={draft => saveVariant(draft)}
          onDiscard={() => {
            setReview(null);
            setMessage("Suggestions discarded. Nothing from the suggestion was saved.");
          }}
        />
      ) : null}
    </div>
  );
}
