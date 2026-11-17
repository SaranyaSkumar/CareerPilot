"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, Cloud, Download, FileUser, HardDrive, Printer, Save } from "lucide-react";
import { WorkspaceHeader, WorkspaceNav } from "@/components/workspace-nav";
import { currentUserId, readDraft, writeDraft } from "@/lib/draft-storage";
import { workspaceFetch } from "@/lib/workspace-fetch";

type Cv = { name: string; headline: string; summary: string; experience: string; skills: string; education: string };
type ApiCv = { id: number; name: string; headline: string; summary: string; experience: string; skills: string; education: string };
type ApiProfile = { full_name: string; headline: string; summary: string; skills: string };
type CvVersion = { id: number; label: string; job_title: string; company: string; notes: string; created_at: string; snapshot: Cv };
type AtsFinding = { code: string; severity: "info" | "warning" | "good"; title: string; detail: string };
type AtsKeyword = { term: string; status: "matched" | "related" | "missing"; evidence: string };
type AtsAnalysis = { formatting_score: number; content_score: number | null; overall_score: number | null; findings: AtsFinding[]; keywords: AtsKeyword[]; disclaimer: string };

const blank: Cv = { name: "", headline: "", summary: "", experience: "", skills: "", education: "" };
const input = "mt-1 w-full rounded-xl border border-[var(--line)] bg-white px-3.5 py-3 text-sm outline-none focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand-soft)]";

function fromApi(value: ApiCv): Cv {
  return { name: value.name, headline: value.headline, summary: value.summary, experience: value.experience, skills: value.skills, education: value.education };
}
function hasContent(value: Cv) {
  return Object.values(value).some(field => field.trim().length > 0);
}

export default function CvPage() {
  const [cv, setCv] = useState<Cv>(blank);
  const [status, setStatus] = useState<"loading" | "connected" | "saving" | "saved" | "offline">("loading");
  const [message, setMessage] = useState("");
  const [exporting, setExporting] = useState<"pdf" | "docx" | null>(null);
  const [versions, setVersions] = useState<CvVersion[]>([]);
  const [loadingVersions, setLoadingVersions] = useState(true);
  const [versionBusy, setVersionBusy] = useState(false);
  const [jobDescription, setJobDescription] = useState("");
  const [analysis, setAnalysis] = useState<AtsAnalysis | null>(null);
  const [analysing, setAnalysing] = useState(false);
  const userIdRef = useRef<string | null>(null);

  function rememberCv(value: Cv) {
    if (userIdRef.current) writeDraft("cv", userIdRef.current, JSON.stringify(value));
  }

  useEffect(() => {
    let active = true;
    async function load() {
      userIdRef.current = await currentUserId();
      try {
        const response = await workspaceFetch("/api/v1/cv");
        if (!response.ok) throw new Error("CV API unavailable");
        const serverCv = fromApi(await response.json() as ApiCv);
        const localRaw = userIdRef.current ? readDraft("cv", userIdRef.current) : null;

        if (!hasContent(serverCv) && localRaw) {
          try {
            const localCv = { ...blank, ...JSON.parse(localRaw) } as Cv;
            if (hasContent(localCv)) {
              const migrated = await workspaceFetch("/api/v1/cv", {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(localCv),
              });
              if (!migrated.ok) throw new Error("CV draft migration failed");
              if (active) {
                setCv(fromApi(await migrated.json() as ApiCv));
                setStatus("connected");
                setMessage("Your existing browser CV draft has been copied to the API.");
              }
              return;
            }
          } catch {
            // Keep the API as source of truth if a legacy draft cannot be migrated.
          }
        }

        if (!hasContent(serverCv)) {
          const profileResponse = await workspaceFetch("/api/v1/profile");
          if (profileResponse.ok) {
            const profile = await profileResponse.json() as ApiProfile;
            serverCv.name = profile.full_name;
            serverCv.headline = profile.headline;
            serverCv.summary = profile.summary;
            serverCv.skills = profile.skills;
          }
        }
        if (active) {
          setCv(serverCv);
          setStatus("connected");
          setMessage("");
        }
      } catch {
        const raw = userIdRef.current ? readDraft("cv", userIdRef.current) : null;
        if (active) {
          if (raw) {
            try { setCv({ ...blank, ...JSON.parse(raw) }); } catch { /* ignore invalid local draft */ }
          }
          setStatus("offline");
          setMessage("API unavailable. You can keep a browser copy until the API is running.");
        }
      }
    }
    void load();
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    workspaceFetch("/api/v1/cv/versions")
      .then(response => { if (!response.ok) throw new Error("Could not load CV versions"); return response.json() as Promise<CvVersion[]>; })
      .then(data => { if (active) setVersions(data); })
      .catch(() => { if (active) setMessage("CV version history is unavailable until the API is connected."); })
      .finally(() => { if (active) setLoadingVersions(false); });
    return () => { active = false; };
  }, []);

  const set = <K extends keyof Cv,>(key: K, value: Cv[K]) => {
    setCv(current => ({ ...current, [key]: value }));
    setStatus("connected");
    setMessage("");
  };

  const sections = useMemo(() => [
    { title: "Professional summary", body: cv.summary },
    { title: "Experience", body: cv.experience },
    { title: "Skills", body: cv.skills },
    { title: "Education", body: cv.education },
  ].filter(section => section.body.trim()), [cv]);

  async function save() {
    setStatus("saving");
    setMessage("");
    try {
      const response = await workspaceFetch("/api/v1/cv", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cv),
      });
      if (!response.ok) throw new Error("The CV draft could not be saved.");
      const saved = fromApi(await response.json() as ApiCv);
      setCv(saved);
      rememberCv(saved);
      setStatus("saved");
      setMessage("CV draft saved to your CareerPilot database.");
    } catch (error) {
      rememberCv(cv);
      setStatus("offline");
      setMessage(error instanceof Error ? `${error.message} A browser copy was saved instead.` : "API unavailable. A browser copy was saved instead.");
    }
  }

  async function createVersion() {
    if (!hasContent(cv)) {
      setMessage("Add CV content before creating a version.");
      return;
    }
    const defaultLabel = cv.headline ? `${cv.headline} – ${new Date().toLocaleDateString()}` : `CV version – ${new Date().toLocaleDateString()}`;
    const label = window.prompt("Name this CV version", defaultLabel)?.trim();
    if (!label) return;
    const jobTitle = window.prompt("Target role (optional)", "")?.trim() || "";
    const company = window.prompt("Company (optional)", "")?.trim() || "";
    setVersionBusy(true);
    setMessage("");
    try {
      const saved = await workspaceFetch("/api/v1/cv", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cv),
      });
      if (!saved.ok) throw new Error("Save your CV before creating a version.");
      const response = await workspaceFetch("/api/v1/cv/versions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label, job_title: jobTitle, company }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null) as { detail?: string } | null;
        throw new Error(detail?.detail || "Could not create this CV version.");
      }
      const created = await response.json() as CvVersion;
      setVersions(current => [created, ...current]);
      setStatus("saved");
      setMessage("A separate, saved snapshot has been added to your CV history.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not create this CV version.");
    } finally {
      setVersionBusy(false);
    }
  }

  async function restoreVersion(version: CvVersion) {
    if (!window.confirm(`Load "${version.label}" into the editor? Your saved version will remain unchanged.`)) return;
    setVersionBusy(true);
    try {
      const response = await workspaceFetch(`/api/v1/cv/versions/${version.id}/restore`, { method: "POST" });
      if (!response.ok) throw new Error("Could not restore this CV version.");
      const restored = fromApi(await response.json() as ApiCv);
      setCv(restored);
      rememberCv(restored);
      setStatus("saved");
      setMessage(`"${version.label}" has been loaded into the editor. The saved snapshot remains in history.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not restore this CV version.");
    } finally {
      setVersionBusy(false);
    }
  }

  async function runAtsAnalysis() {
    setAnalysing(true);
    setMessage("");
    try {
      const saved = await workspaceFetch("/api/v1/cv", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cv),
      });
      if (!saved.ok) throw new Error("Save your CV before analysing it.");
      const response = await workspaceFetch("/api/v1/cv/analyse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_description: jobDescription }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null) as { detail?: string } | null;
        throw new Error(detail?.detail || "ATS analysis could not be completed.");
      }
      setAnalysis(await response.json() as AtsAnalysis);
      setStatus("saved");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "ATS analysis could not be completed.");
    } finally {
      setAnalysing(false);
    }
  }

  async function exportCv(format: "pdf" | "docx") {
    setExporting(format);
    setMessage("");
    try {
      // Persist the current editor state first so the downloaded file is never stale.
      const savedResponse = await workspaceFetch("/api/v1/cv", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cv),
      });
      if (!savedResponse.ok) throw new Error("Save your CV before exporting.");
      const saved = fromApi(await savedResponse.json() as ApiCv);
      setCv(saved);
      rememberCv(saved);

      const response = await workspaceFetch(`/api/v1/cv/export?format=${format}`, { method: "POST" });
      if (!response.ok) {
        const detail = await response.json().catch(() => null) as { detail?: string } | null;
        throw new Error(detail?.detail || "The document could not be generated.");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `CareerPilot-CV.${format}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setStatus("saved");
      setMessage(`Your ${format.toUpperCase()} CV is ready.`);
    } catch (error) {
      setStatus("connected");
      setMessage(error instanceof Error ? error.message : "The document could not be generated.");
    } finally {
      setExporting(null);
    }
  }

  return (
    <main className="min-h-screen">
      <WorkspaceNav active="/cv" />
      <style jsx global>{`
        @media print {
          @page { size: A4; margin: 16mm; }
          body * { visibility: hidden !important; }
          #cv-print-area, #cv-print-area * { visibility: visible !important; }
          #cv-print-area {
            position: absolute !important;
            inset: 0 auto auto 0 !important;
            width: 100% !important;
            max-width: none !important;
            min-height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            border: 0 !important;
            box-shadow: none !important;
          }
        }
      `}</style>
      <div className="lg:pl-[248px]">
        <WorkspaceHeader />
        <div className="mx-auto max-w-[1280px] px-6 py-9 md:px-10">
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
            <div>
              <p className="text-sm font-semibold text-[var(--brand)]">CREATE AND REFINE</p>
              <h1 className="mt-1 text-3xl font-semibold tracking-tight">CV Studio</h1>
              <p className="mt-2 text-sm text-[var(--muted)]">Build a clear, ATS-friendly CV from your verified experience.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button onClick={save} disabled={status === "saving" || status === "loading" || exporting !== null} className="inline-flex items-center gap-2 rounded-xl bg-[var(--brand)] px-4 py-3 text-sm font-semibold text-white disabled:opacity-60"><Save size={16}/>{status === "saving" ? "Saving…" : "Save draft"}</button>
              <button onClick={() => void exportCv("pdf")} disabled={status === "loading" || exporting !== null} className="inline-flex items-center gap-2 rounded-xl border border-[var(--line)] bg-white px-4 py-3 text-sm font-semibold disabled:opacity-60"><Download size={16}/>{exporting === "pdf" ? "Preparing PDF…" : "Download PDF"}</button>
              <button onClick={() => void exportCv("docx")} disabled={status === "loading" || exporting !== null} className="inline-flex items-center gap-2 rounded-xl border border-[var(--line)] bg-white px-4 py-3 text-sm font-semibold disabled:opacity-60"><Download size={16}/>{exporting === "docx" ? "Preparing Word…" : "Download Word"}</button>
              <button onClick={() => window.print()} className="inline-flex items-center gap-2 rounded-xl border border-[var(--line)] bg-white px-4 py-3 text-sm font-semibold"><Printer size={16}/>Print</button>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-[var(--muted)]">
            {status === "loading" && <span>Connecting to CareerPilot…</span>}
            {status === "connected" && <span className="inline-flex items-center gap-1"><Cloud size={14}/>Connected to API</span>}
            {status === "saved" && <span className="inline-flex items-center gap-1 text-[var(--brand)]"><Cloud size={14}/>Saved to database</span>}
            {status === "offline" && <span className="inline-flex items-center gap-1 text-amber-700"><HardDrive size={14}/>Browser backup</span>}
            {message && <span>{message}</span>}
            {status === "offline" && <AlertCircle size={14}/>}
          </div>

          <section className="mt-6 rounded-2xl border border-[var(--line)] bg-white p-5">
            <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
              <div>
                <h2 className="font-semibold">CV versions</h2>
                <p className="mt-1 text-xs text-[var(--muted)]">Save named snapshots for different roles. Restoring loads a copy into the editor; it never edits the saved snapshot.</p>
              </div>
              <button onClick={() => void createVersion()} disabled={versionBusy || status === "loading" || exporting !== null} className="rounded-xl bg-[var(--brand)] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60">{versionBusy ? "Working…" : "Save current as version"}</button>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {loadingVersions && <p className="text-sm text-[var(--muted)]">Loading version history…</p>}
              {!loadingVersions && versions.length === 0 && <p className="text-sm text-[var(--muted)]">No saved versions yet. Save your first snapshot when your CV is ready.</p>}
              {versions.map(version => (
                <div key={version.id} className="flex items-center justify-between gap-3 rounded-xl border border-[var(--line)] p-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold">{version.label}</p>
                    <p className="mt-1 truncate text-xs text-[var(--muted)]">{[version.job_title, version.company].filter(Boolean).join(" · ") || "General CV"} · {new Date(version.created_at).toLocaleString()}</p>
                  </div>
                  <button onClick={() => void restoreVersion(version)} disabled={versionBusy} className="shrink-0 rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-semibold disabled:opacity-60">Restore</button>
                </div>
              ))}
            </div>
          </section>

          <section className="mt-6 rounded-2xl border border-[var(--line)] bg-white p-5">
            <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
              <div>
                <h2 className="font-semibold">ATS analyser</h2>
                <p className="mt-1 text-xs text-[var(--muted)]">Check your CV structure and compare its wording with a specific job description.</p>
              </div>
              <button onClick={() => void runAtsAnalysis()} disabled={analysing || status === "loading"} className="rounded-xl bg-[var(--brand)] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60">{analysing ? "Analysing…" : "Analyse my CV"}</button>
            </div>
            <label className="mt-4 block text-sm font-medium">Job description <span className="font-normal text-[var(--muted)]">(optional)</span>
              <textarea className={input + " min-h-36 resize-y"} value={jobDescription} onChange={e => setJobDescription(e.target.value)} placeholder="Paste the job description here for a tailored keyword and alignment check…"/>
            </label>
            {analysis && <div className="mt-5 space-y-5">
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl bg-[var(--brand-soft)] p-4"><p className="text-xs text-[var(--muted)]">CV structure</p><p className="mt-1 text-2xl font-semibold">{analysis.formatting_score}<span className="text-sm font-normal">/100</span></p></div>
                <div className="rounded-xl border border-[var(--line)] p-4"><p className="text-xs text-[var(--muted)]">Job keyword coverage</p><p className="mt-1 text-2xl font-semibold">{analysis.content_score === null ? "—" : <>{analysis.content_score}<span className="text-sm font-normal">/100</span></>}</p></div>
                <div className="rounded-xl border border-[var(--line)] p-4"><p className="text-xs text-[var(--muted)]">Indicative alignment</p><p className="mt-1 text-2xl font-semibold">{analysis.overall_score === null ? "—" : <>{analysis.overall_score}<span className="text-sm font-normal">/100</span></>}</p></div>
              </div>
              <div>
                <h3 className="text-sm font-semibold">Recommendations</h3>
                <div className="mt-2 grid gap-2 md:grid-cols-2">
                  {analysis.findings.map(item => <div key={item.code} className="rounded-xl border border-[var(--line)] p-3">
                    <p className="text-sm font-semibold">{item.title}</p><p className="mt-1 text-xs leading-5 text-[var(--muted)]">{item.detail}</p>
                  </div>)}
                </div>
              </div>
              {analysis.keywords.length > 0 && <div>
                <h3 className="text-sm font-semibold">Job description terms</h3>
                <div className="mt-2 flex flex-wrap gap-2">
                  {analysis.keywords.map(item => <span key={item.term} title={item.evidence} className={"rounded-full px-3 py-1.5 text-xs font-medium " + (item.status === "matched" ? "bg-[var(--brand-soft)] text-[var(--brand)]" : "bg-amber-50 text-amber-800")}>{item.term} · {item.status}</span>)}
                </div>
              </div>}
              <p className="text-xs leading-5 text-[var(--muted)]">{analysis.disclaimer}</p>
            </div>}
          </section>

          <div className="mt-6 grid items-start gap-6 xl:grid-cols-[1fr_0.9fr]">
            <section className="rounded-2xl border border-[var(--line)] bg-white p-6">
              <div className="flex items-center gap-2"><FileUser className="text-[var(--brand)]" size={19}/><h2 className="font-semibold">CV content</h2></div>
              <p className="mt-1 text-xs text-[var(--muted)]">Write factual information only. AI-assisted tailoring will be added after the profile foundation.</p>
              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                <label className="text-sm font-medium">Full name<input className={input} value={cv.name} onChange={e => set("name", e.target.value)} placeholder="Your name"/></label>
                <label className="text-sm font-medium">Professional title<input className={input} value={cv.headline} onChange={e => set("headline", e.target.value)} placeholder="e.g. Software Engineer"/></label>
              </div>
              {([
                { key: "summary", label: "Professional summary", hint: "A concise overview of your experience and strengths." },
                { key: "experience", label: "Work experience", hint: "Role, employer, dates and evidence-backed achievements." },
                { key: "skills", label: "Skills", hint: "Relevant technical and professional skills." },
                { key: "education", label: "Education", hint: "Qualification, institution and dates." },
              ] as const).map(section => (
                <label key={section.key} className="mt-5 block text-sm font-medium">{section.label}<textarea className={input + " min-h-28 resize-y"} value={cv[section.key]} onChange={e => set(section.key, e.target.value)} placeholder={section.hint}/></label>
              ))}
            </section>

            <section className="rounded-2xl border border-[var(--line)] bg-white p-6 print:border-0 print:p-0">
              <div className="mb-5 flex items-center justify-between"><h2 className="font-semibold">Live preview</h2><span className="rounded-full bg-[var(--brand-soft)] px-3 py-1 text-xs font-medium text-[var(--brand)]">Single-column layout</span></div>
              <article id="cv-print-area" className="mx-auto min-h-[720px] max-w-[680px] border border-[#e8e8e2] bg-white p-8 text-[#202a25] shadow-sm print:min-h-0 print:max-w-none print:border-0 print:p-0 print:shadow-none">
                <h2 className="text-2xl font-bold tracking-tight">{cv.name || "Your Name"}</h2>
                <p className="mt-1 text-sm font-medium text-[#315d49]">{cv.headline || "Professional Title"}</p>
                {sections.filter(section => section.title === "Professional summary").map(section => <section key={section.title} className="mt-7"><h3 className="border-b border-[#dfe5df] pb-2 text-xs font-bold uppercase tracking-widest">{section.title}</h3><p className="mt-3 whitespace-pre-wrap text-sm leading-6">{section.body}</p></section>)}
                {sections.filter(section => section.title !== "Professional summary").map(section => <section key={section.title} className="mt-7"><h3 className="border-b border-[#dfe5df] pb-2 text-xs font-bold uppercase tracking-widest">{section.title}</h3><p className="mt-3 whitespace-pre-wrap text-sm leading-6">{section.body}</p></section>)}
              </article>
            </section>
          </div>
          <p className="mt-5 text-xs text-[var(--muted)]">Download an editable Word document or an ATS-friendly PDF. The analyser checks your structured CV content and job-description wording; it does not emulate a specific employer ATS.</p>
        </div>
      </div>
    </main>
  );
}
