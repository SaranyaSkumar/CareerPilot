"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertCircle, Cloud, Download, FileUser, HardDrive, Printer, Save } from "lucide-react";
import { WorkspaceHeader, WorkspaceNav } from "@/components/workspace-nav";

type Cv = { name: string; headline: string; summary: string; experience: string; skills: string; education: string };
type ApiCv = { id: number; name: string; headline: string; summary: string; experience: string; skills: string; education: string };
type ApiProfile = { full_name: string; headline: string; summary: string; skills: string };

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
  const [message, setMessage] = useState("");\n  const [exporting, setExporting] = useState<"pdf" | "docx" | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const response = await fetch("/api/v1/cv");
        if (!response.ok) throw new Error("CV API unavailable");
        const serverCv = fromApi(await response.json() as ApiCv);
        const localRaw = localStorage.getItem("careerpilot.cv");

        if (!hasContent(serverCv) && localRaw) {
          try {
            const localCv = { ...blank, ...JSON.parse(localRaw) } as Cv;
            if (hasContent(localCv)) {
              const migrated = await fetch("/api/v1/cv", {
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
          const profileResponse = await fetch("/api/v1/profile");
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
        const raw = localStorage.getItem("careerpilot.cv");
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
      const response = await fetch("/api/v1/cv", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cv),
      });
      if (!response.ok) throw new Error("The CV draft could not be saved.");
      const saved = fromApi(await response.json() as ApiCv);
      setCv(saved);
      localStorage.setItem("careerpilot.cv", JSON.stringify(saved));
      setStatus("saved");
      setMessage("CV draft saved to your CareerPilot database.");
    } catch (error) {
      localStorage.setItem("careerpilot.cv", JSON.stringify(cv));
      setStatus("offline");
      setMessage(error instanceof Error ? `${error.message} A browser copy was saved instead.` : "API unavailable. A browser copy was saved instead.");
    }
  }

  async function exportCv(format: "pdf" | "docx") {
    setExporting(format);
    setMessage("");
    try {
      // Persist the current editor state first so the downloaded file is never stale.
      const savedResponse = await fetch("/api/v1/cv", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cv),
      });
      if (!savedResponse.ok) throw new Error("Save your CV before exporting.");
      const saved = fromApi(await savedResponse.json() as ApiCv);
      setCv(saved);
      localStorage.setItem("careerpilot.cv", JSON.stringify(saved));

      const response = await fetch(`/api/v1/cv/export?format=${format}`, { method: "POST" });
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
              <article className="mx-auto min-h-[720px] max-w-[680px] border border-[#e8e8e2] bg-white p-8 text-[#202a25] shadow-sm print:border-0 print:shadow-none">
                <h2 className="text-2xl font-bold tracking-tight">{cv.name || "Your Name"}</h2>
                <p className="mt-1 text-sm font-medium text-[#315d49]">{cv.headline || "Professional Title"}</p>
                {sections.filter(section => section.title === "Professional summary").map(section => <section key={section.title} className="mt-7"><h3 className="border-b border-[#dfe5df] pb-2 text-xs font-bold uppercase tracking-widest">{section.title}</h3><p className="mt-3 whitespace-pre-wrap text-sm leading-6">{section.body}</p></section>)}
                {sections.filter(section => section.title !== "Professional summary").map(section => <section key={section.title} className="mt-7"><h3 className="border-b border-[#dfe5df] pb-2 text-xs font-bold uppercase tracking-widest">{section.title}</h3><p className="mt-3 whitespace-pre-wrap text-sm leading-6">{section.body}</p></section>)}
              </article>
            </section>
          </div>
          <p className="mt-5 text-xs text-[var(--muted)]">Download an editable Word document or an ATS-friendly PDF. Multiple templates, version history and ATS diagnostics are coming next.</p>
        </div>
      </div>
    </main>
  );
}
