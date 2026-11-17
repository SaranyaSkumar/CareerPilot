"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { WorkspaceHeader, WorkspaceNav } from "@/components/workspace-nav";
import { workspaceFetch } from "@/lib/workspace-fetch";

type Provider = {
  provider_key: string;
  label: string;
  kind: "api" | "link";
  description: string;
  enabled: boolean;
  configured: boolean;
  status: string;
};

type Settings = {
  country: string;
  location: string;
  keywords: string;
  remote_preference: "any" | "remote" | "onsite";
  search: { keywords: string; location: string; country: string; keywords_from_profile: boolean };
  providers: Provider[];
};

const countries = [
  { value: "nz", label: "New Zealand" },
  { value: "au", label: "Australia" },
  { value: "gb", label: "United Kingdom" },
  { value: "us", label: "United States" },
];
const remotes = [
  { value: "any", label: "Any workplace" },
  { value: "remote", label: "Remote" },
  { value: "onsite", label: "On-site" },
] as const;
const field = "mt-1 w-full rounded-xl border border-[var(--line)] bg-white px-3.5 py-3 text-sm outline-none focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand-soft)]";

async function readDetail(response: Response): Promise<string> {
  const body = await response.json().catch(() => null) as { detail?: unknown } | null;
  return typeof body?.detail === "string" ? body.detail : "";
}

export default function JobPreferencesPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    workspaceFetch("/api/v1/jobs/discovery/settings")
      .then(async response => {
        if (!response.ok) throw new Error((await readDetail(response)) || "Job sources could not be loaded.");
        return response.json() as Promise<Settings>;
      })
      .then(body => { if (active) setSettings(body); })
      .catch(err => { if (active) setError(err instanceof Error ? err.message : "Job sources could not be loaded."); });
    return () => { active = false; };
  }, []);

  function update<K extends keyof Settings>(key: K, value: Settings[K]) {
    setSettings(current => current ? { ...current, [key]: value } : current);
  }

  function toggle(key: string) {
    setSettings(current => current ? {
      ...current,
      providers: current.providers.map(item => item.provider_key === key ? { ...item, enabled: !item.enabled } : item),
    } : current);
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!settings) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const response = await workspaceFetch("/api/v1/jobs/discovery/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          country: settings.country,
          location: settings.location,
          keywords: settings.keywords,
          remote_preference: settings.remote_preference,
          providers: settings.providers.map(item => ({ provider_key: item.provider_key, enabled: item.enabled })),
        }),
      });
      if (!response.ok) throw new Error((await readDetail(response)) || "Job sources could not be saved.");
      setSettings(await response.json() as Settings);
      setMessage("Job sources saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Job sources could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="min-h-screen">
      <WorkspaceNav active="/jobs" />
      <div className="lg:pl-[248px]">
        <WorkspaceHeader />
        <div className="mx-auto max-w-3xl px-6 py-9 md:px-10">
          <p className="text-sm font-semibold text-[var(--brand)]">JOB SOURCES</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Where CareerPilot looks</h1>
          <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
            Choose a default country, location, and keywords. Leave keywords blank to use your headline and skills.
            Each source can be turned off. API sources are skipped until their keys are set on the backend.
          </p>
          <Link href="/jobs" className="mt-4 inline-flex text-sm font-semibold text-[var(--brand)]">Back to jobs</Link>

          {!settings && !error && <p className="mt-8 text-sm text-[var(--muted)]">Loading your job sources…</p>}
          {error && <p className="mt-6 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700" role="status">{error}</p>}
          {settings && (
            <form onSubmit={save} className="mt-6 space-y-6">
              <section className="rounded-2xl border border-[var(--line)] bg-white p-5">
                <h2 className="font-semibold">Search defaults</h2>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <label className="text-sm font-medium">Country
                    <select className={field} value={settings.country} onChange={event => update("country", event.target.value)}>
                      {countries.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}
                      {!countries.some(item => item.value === settings.country) && <option value={settings.country}>{settings.country}</option>}
                    </select>
                  </label>
                  <label className="text-sm font-medium">Location
                    <input maxLength={200} className={field} value={settings.location} onChange={event => update("location", event.target.value)} placeholder="Auckland" />
                  </label>
                  <label className="text-sm font-medium sm:col-span-2">Keywords override
                    <input maxLength={300} className={field} value={settings.keywords} onChange={event => update("keywords", event.target.value)} placeholder="Leave blank to use your headline and skills" />
                  </label>
                </div>
                <fieldset className="mt-4">
                  <legend className="text-sm font-medium">Workplace</legend>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {remotes.map(item => (
                      <label key={item.value} className={`cursor-pointer rounded-full px-4 py-2 text-sm font-semibold ${settings.remote_preference === item.value ? "bg-[var(--brand)] text-white" : "bg-[var(--background)] text-[var(--muted)]"}`}>
                        <input className="sr-only" type="radio" name="remote" value={item.value} checked={settings.remote_preference === item.value} onChange={() => update("remote_preference", item.value)} />
                        {item.label}
                      </label>
                    ))}
                  </div>
                </fieldset>
                <p className="mt-4 text-sm text-[var(--muted)]">
                  Last saved search: <span className="font-semibold text-[var(--foreground)]">{settings.search.keywords}</span> in {settings.search.location}.
                  {settings.search.keywords_from_profile ? " Taken from your profile." : " Using your keyword override."}
                </p>
              </section>

              <section className="rounded-2xl border border-[var(--line)] bg-white p-5">
                <h2 className="font-semibold">Sources</h2>
                <ul className="mt-4 space-y-3">
                  {settings.providers.map(provider => (
                    <li key={provider.provider_key} className="flex items-start justify-between gap-4 rounded-xl border border-[var(--line)] p-4">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-semibold">{provider.label}</p>
                          <span className="rounded-full bg-[var(--background)] px-2 py-0.5 text-[10px] font-semibold uppercase text-[var(--muted)]">{provider.kind === "api" ? "API" : "Link"}</span>
                          {provider.status === "not_configured" && <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold uppercase text-amber-800">Not configured</span>}
                        </div>
                        <p className="mt-1 text-sm leading-6 text-[var(--muted)]">{provider.description}</p>
                      </div>
                      <button type="button" aria-pressed={provider.enabled} onClick={() => toggle(provider.provider_key)} className={`shrink-0 rounded-full px-3 py-1.5 text-xs font-semibold ${provider.enabled ? "bg-[var(--brand)] text-white" : "bg-slate-100 text-slate-500"}`}>
                        {provider.enabled ? "On" : "Off"}
                      </button>
                    </li>
                  ))}
                </ul>
              </section>

              {message && <p className="rounded-xl bg-[var(--brand-soft)] px-4 py-3 text-sm text-[var(--brand)]" role="status">{message}</p>}
              <button type="submit" disabled={saving} className="rounded-xl bg-[var(--brand)] px-5 py-3 text-sm font-semibold text-white disabled:opacity-60">{saving ? "Saving…" : "Save job sources"}</button>
            </form>
          )}
        </div>
      </div>
    </main>
  );
}
