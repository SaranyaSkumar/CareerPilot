"use client";

import { useEffect, useState } from "react";
import { Save, UserRound, Cloud, HardDrive, AlertCircle } from "lucide-react";
import { WorkspaceHeader, WorkspaceNav } from "@/components/workspace-nav";

type Profile = {
  fullName: string;
  email: string;
  headline: string;
  location: string;
  summary: string;
  skills: string;
};

type ApiProfile = {
  id: number;
  full_name: string;
  email: string;
  headline: string;
  location: string;
  summary: string;
  skills: string;
};

const emptyProfile: Profile = {
  fullName: "",
  email: "",
  headline: "",
  location: "New Zealand",
  summary: "",
  skills: "",
};


function fromApi(value: ApiProfile): Profile {
  return {
    fullName: value.full_name,
    email: value.email,
    headline: value.headline,
    location: value.location,
    summary: value.summary,
    skills: value.skills,
  };
}

function toApi(value: Profile) {
  return {
    full_name: value.fullName,
    email: value.email,
    headline: value.headline,
    location: value.location,
    summary: value.summary,
    skills: value.skills,
  };
}

function hasContent(value: Profile) {
  return Object.entries(value).some(([key, field]) => key !== "location" && field.trim().length > 0);
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile>(emptyProfile);
  const [status, setStatus] = useState<"loading" | "connected" | "offline" | "saving" | "saved" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const response = await fetch("/api/v1/profile");
        if (!response.ok) throw new Error("The profile API could not be reached.");
        const serverProfile = fromApi(await response.json() as ApiProfile);
        const localRaw = window.localStorage.getItem("careerpilot.profile");

        // Migrate an existing browser-only draft once, but never overwrite a populated server profile.
        if (!hasContent(serverProfile) && localRaw) {
          try {
            const localProfile = { ...emptyProfile, ...JSON.parse(localRaw) } as Profile;
            if (hasContent(localProfile)) {
              const migrated = await fetch("/api/v1/profile", {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(toApi(localProfile)),
              });
              if (!migrated.ok) throw new Error("Could not migrate the saved browser profile.");
              if (active) {
                setProfile(fromApi(await migrated.json() as ApiProfile));
                setStatus("connected");
                setMessage("Your existing browser draft has been copied to the API.");
              }
              return;
            }
          } catch {
            // Invalid legacy browser data is ignored; the server remains the source of truth.
          }
        }

        if (active) {
          setProfile(serverProfile);
          setStatus("connected");
          setMessage("");
        }
      } catch {
        const raw = window.localStorage.getItem("careerpilot.profile");
        if (active) {
          if (raw) {
            try { setProfile({ ...emptyProfile, ...JSON.parse(raw) }); } catch { /* ignore invalid local draft */ }
          }
          setStatus("offline");
          setMessage("API unavailable. Your edits can be kept in this browser until the API is running.");
        }
      }
    }

    void load();
    return () => { active = false; };
  }, []);

  function update<K extends keyof Profile>(key: K, value: Profile[K]) {
    setProfile(current => ({ ...current, [key]: value }));
    setStatus("connected");
    setMessage("");
  }

  async function save() {
    setStatus("saving");
    setMessage("");
    try {
      const response = await fetch("/api/v1/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(toApi(profile)),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail?.[0]?.msg || "The profile could not be saved.");
      }
      const saved = fromApi(await response.json() as ApiProfile);
      setProfile(saved);
      window.localStorage.setItem("careerpilot.profile", JSON.stringify(saved));
      setStatus("saved");
      setMessage("Profile saved to your CareerPilot database.");
    } catch (error) {
      window.localStorage.setItem("careerpilot.profile", JSON.stringify(profile));
      setStatus("offline");
      setMessage(error instanceof Error ? `${error.message} A browser copy was saved instead.` : "API unavailable. A browser copy was saved instead.");
    }
  }

  const field = "mt-1 w-full rounded-xl border border-[var(--line)] bg-white px-3.5 py-3 text-sm text-[var(--foreground)] outline-none transition focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand-soft)]";

  return (
    <main className="min-h-screen">
      <WorkspaceNav active="/profile" />
      <div className="lg:pl-[248px]">
        <WorkspaceHeader />
        <div className="mx-auto max-w-4xl px-6 py-9 md:px-10">
          <div className="flex items-start gap-4">
            <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-[var(--brand-soft)] text-[var(--brand)]"><UserRound /></span>
            <div>
              <p className="text-sm font-semibold text-[var(--brand)]">YOUR FOUNDATION</p>
              <h1 className="mt-1 text-3xl font-semibold tracking-tight">Career profile</h1>
              <p className="mt-2 text-sm text-[var(--muted)]">Keep your verified career information here. CVs and applications will be created from this profile.</p>
            </div>
          </div>

          <section className="mt-8 rounded-2xl border border-[var(--line)] bg-white p-6 md:p-8">
            <h2 className="font-semibold">Personal details</h2>
            <p className="mt-1 text-sm text-[var(--muted)]">Only add details you are comfortable storing in this personal workspace.</p>
            <div className="mt-6 grid gap-5 md:grid-cols-2">
              <label className="text-sm font-medium">Full name<input className={field} value={profile.fullName} onChange={e => update("fullName", e.target.value)} placeholder="Your name" /></label>
              <label className="text-sm font-medium">Email address<input className={field} type="email" value={profile.email} onChange={e => update("email", e.target.value)} placeholder="you@example.com" /></label>
              <label className="text-sm font-medium">Professional headline<input className={field} value={profile.headline} onChange={e => update("headline", e.target.value)} placeholder="e.g. Software Engineer" /></label>
              <label className="text-sm font-medium">Preferred location<input className={field} value={profile.location} onChange={e => update("location", e.target.value)} placeholder="e.g. Auckland, New Zealand" /></label>
            </div>
            <div className="mt-6"><label className="text-sm font-medium">Professional summary<textarea className={field + " min-h-32 resize-y"} value={profile.summary} onChange={e => update("summary", e.target.value)} placeholder="Summarise your experience, strengths and the kind of work you do." /></label></div>
            <div className="mt-6"><label className="text-sm font-medium">Skills<textarea className={field + " min-h-24 resize-y"} value={profile.skills} onChange={e => update("skills", e.target.value)} placeholder="Type skills separated by commas" /></label><p className="mt-2 text-xs text-[var(--muted)]">Use skills you can confidently discuss and support with real experience.</p></div>
            <div className="mt-7 flex flex-wrap items-center gap-3">
              <button onClick={save} disabled={status === "saving" || status === "loading"} className="inline-flex items-center gap-2 rounded-xl bg-[var(--brand)] px-5 py-3 text-sm font-semibold text-white hover:bg-[var(--brand-dark)] disabled:cursor-not-allowed disabled:opacity-60"><Save size={16} />{status === "saving" ? "Saving…" : "Save profile"}</button>
              {status === "loading" && <span className="text-sm text-[var(--muted)]">Connecting to CareerPilot…</span>}
              {status === "connected" && <span className="inline-flex items-center gap-1.5 text-sm text-[var(--muted)]"><Cloud size={15} />Connected to API</span>}
              {status === "saved" && <span role="status" className="inline-flex items-center gap-1.5 text-sm font-medium text-[var(--brand)]"><Cloud size={15} />Saved to database</span>}
              {status === "offline" && <span className="inline-flex items-center gap-1.5 text-sm text-amber-700"><HardDrive size={15} />Browser backup</span>}
              {status === "error" && <span className="inline-flex items-center gap-1.5 text-sm text-red-600"><AlertCircle size={15} />Save failed</span>}
            </div>
            {message && <p role="status" className="mt-3 text-sm text-[var(--muted)]">{message}</p>}
          </section>

          <p className="mt-4 text-xs leading-5 text-[var(--muted)]">Personal development build: the API currently stores one local profile and does not yet have user authentication. Keep the API private and do not deploy it publicly until authentication and per-user access controls are implemented.</p>
        </div>
      </div>
    </main>
  );
}
