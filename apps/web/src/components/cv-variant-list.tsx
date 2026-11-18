"use client";

import { useEffect, useState } from "react";
import { workspaceFetch } from "@/lib/workspace-fetch";

type Variant = {
  id: number;
  label: string;
  job_title: string;
  company: string;
  job_description: string;
  profile_id: number | null;
  is_default: boolean;
  name: string;
  updated_at: string;
};

type ScorePair = {
  variant: { overall_score: number | null };
  original: { overall_score: number | null };
};

async function readDetail(response: Response): Promise<string> {
  const body = await response.json().catch(() => null) as { detail?: unknown } | null;
  return typeof body?.detail === "string" ? body.detail : "";
}

async function downloadExport(variant: Variant, format: "pdf" | "docx") {
  const response = await workspaceFetch(`/api/v1/cv/variants/${variant.id}/export?format=${format}`, { method: "POST" });
  if (!response.ok) throw new Error((await readDetail(response)) || "The document could not be generated.");
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${variant.label}.${format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function CvVariantList({ refreshKey }: { refreshKey: number }) {
  const [variants, setVariants] = useState<Variant[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [names, setNames] = useState<Record<number, string>>({});
  const [scores, setScores] = useState<Record<number, ScorePair>>({});

  useEffect(() => {
    let active = true;
    workspaceFetch("/api/v1/cv/variants")
      .then(async response => {
        if (!active || !response.ok) return;
        const rows = await response.json() as Variant[];
        if (!active) return;
        setVariants(rows);
        setNames(Object.fromEntries(rows.map(row => [row.id, row.label])));
      })
      .catch(() => undefined)
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [refreshKey]);

  async function reload() {
    const response = await workspaceFetch("/api/v1/cv/variants");
    if (!response.ok) return;
    const rows = await response.json() as Variant[];
    setVariants(rows);
    setNames(Object.fromEntries(rows.map(row => [row.id, row.label])));
  }

  async function rename(variant: Variant) {
    const label = (names[variant.id] ?? "").trim();
    if (!label) {
      setMessage("Name this CV variant.");
      return;
    }
    setBusyId(variant.id);
    try {
      const response = await workspaceFetch(`/api/v1/cv/variants/${variant.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label }),
      });
      if (!response.ok) {
        setMessage((await readDetail(response)) || "The variant could not be renamed.");
        return;
      }
      setMessage("Variant renamed. Your original CV was not changed.");
      await reload();
    } finally {
      setBusyId(null);
    }
  }

  async function act(variant: Variant, path: string, method: "POST" | "DELETE") {
    setBusyId(variant.id);
    setMessage("");
    try {
      const response = await workspaceFetch(`/api/v1/cv/variants/${variant.id}${path}`, { method });
      if (!response.ok) {
        setMessage((await readDetail(response)) || "That action could not be completed.");
        return;
      }
      await reload();
    } finally {
      setBusyId(null);
    }
  }

  async function analyse(variant: Variant) {
    setBusyId(variant.id);
    setMessage("");
    try {
      const response = await workspaceFetch(`/api/v1/cv/variants/${variant.id}/analyse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_description: variant.job_description }),
      });
      if (!response.ok) {
        setMessage((await readDetail(response)) || "ATS analysis could not be completed.");
        return;
      }
      const pair = await response.json() as ScorePair;
      setScores(current => ({ ...current, [variant.id]: pair }));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="mt-6 rounded-2xl border border-[var(--line)] bg-white p-5">
      <div>
        <h2 className="font-semibold">CV variants</h2>
        <p className="mt-1 text-xs text-[var(--muted)]">Tailored copies stay separate from your original CV. One variant can be the default. Export or re-check any of them on its own.</p>
      </div>
      {loading ? <p className="mt-4 text-sm text-[var(--muted)]">Loading CV variants…</p> : null}
      {!loading && variants.length === 0 ? <p className="mt-4 text-sm text-[var(--muted)]">No tailored CVs yet. Paste a job description, choose a career profile and create your first tailored CV.</p> : null}
      <div className="mt-4 space-y-3">
        {variants.map(variant => {
          const score = scores[variant.id];
          return (
            <div key={variant.id} className="rounded-xl border border-[var(--line)] p-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <label className="sr-only" htmlFor={`variant-name-${variant.id}`}>Variant name</label>
                    <input
                      id={`variant-name-${variant.id}`}
                      className="w-full max-w-md rounded-lg border border-[var(--line)] px-3 py-2 text-sm font-semibold"
                      value={names[variant.id] ?? variant.label}
                      onChange={event => setNames(current => ({ ...current, [variant.id]: event.target.value }))}
                    />
                    {variant.is_default ? <span className="rounded-full bg-[var(--brand-soft)] px-2 py-1 text-xs font-semibold text-[var(--brand)]">Default</span> : null}
                  </div>
                  <p className="mt-1 text-xs text-[var(--muted)]">{[variant.job_title, variant.company].filter(Boolean).join(" · ") || "General variant"} · {variant.profile_id ? `Profile #${variant.profile_id}` : "Master CV"} · {new Date(variant.updated_at).toLocaleString()}</p>
                </div>
                <button type="button" onClick={() => void rename(variant)} disabled={busyId === variant.id} className="rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-semibold disabled:opacity-60">Rename</button>
              </div>
              {score ? (
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  <p className="rounded-lg border border-[var(--line)] px-3 py-2 text-sm">Original alignment <span className="font-semibold">{score.original.overall_score ?? "—"}</span>/100</p>
                  <p className="rounded-lg bg-[var(--brand-soft)] px-3 py-2 text-sm">This variant <span className="font-semibold">{score.variant.overall_score ?? "—"}</span>/100</p>
                </div>
              ) : null}
              <div className="mt-3 flex flex-wrap gap-2">
                <button type="button" onClick={() => void act(variant, "/default", "POST")} disabled={busyId === variant.id || variant.is_default} className="rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-semibold disabled:opacity-60">Set default</button>
                <button type="button" onClick={() => void act(variant, "/duplicate", "POST")} disabled={busyId === variant.id} className="rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-semibold disabled:opacity-60">Duplicate</button>
                <button type="button" onClick={() => void downloadExport(variant, "pdf").catch(error => setMessage(error instanceof Error ? error.message : "The document could not be generated."))} disabled={busyId === variant.id} className="rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-semibold disabled:opacity-60">PDF</button>
                <button type="button" onClick={() => void downloadExport(variant, "docx").catch(error => setMessage(error instanceof Error ? error.message : "The document could not be generated."))} disabled={busyId === variant.id} className="rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-semibold disabled:opacity-60">Word</button>
                <button type="button" onClick={() => void analyse(variant)} disabled={busyId === variant.id} className="rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-semibold disabled:opacity-60">Re-run ATS</button>
                <button type="button" onClick={() => void act(variant, "", "DELETE")} disabled={busyId === variant.id} className="rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-semibold text-amber-800 disabled:opacity-60">Delete</button>
              </div>
            </div>
          );
        })}
      </div>
      {variants.some(variant => variant.is_default) ? (
        <button
          type="button"
          className="mt-3 text-xs font-semibold text-[var(--brand)]"
          onClick={() => void workspaceFetch("/api/v1/cv/variants/clear-default", { method: "POST" }).then(response => { if (response.ok) return reload(); return undefined; })}
        >
          Use the original CV as the default
        </button>
      ) : null}
      {message ? <p className="mt-3 text-sm" role="status">{message}</p> : null}
    </section>
  );
}
