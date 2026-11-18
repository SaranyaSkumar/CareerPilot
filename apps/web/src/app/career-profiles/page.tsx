"use client";

import { useEffect, useState } from "react";
import { Copy, Plus, Save, Trash2, Users } from "lucide-react";
import { WorkspaceHeader, WorkspaceNav } from "@/components/workspace-nav";
import { workspaceFetch } from "@/lib/workspace-fetch";

type Profile = {
  id: number; name: string; employment_type: string; target_roles: string; location: string;
  cv_name: string; headline: string; summary: string; experience: string; skills: string; education: string;
};
const blank = { name: "", employment_type: "full_time", target_roles: "", location: "New Zealand", cv_name: "", headline: "", summary: "", experience: "", skills: "", education: "" };
const field = "mt-1 w-full rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm outline-none focus:border-[var(--brand)]";
const areas = ["summary", "experience", "skills", "education"] as const;
const labels: Record<string, string> = { full_time: "Full-time", part_time: "Part-time", contract: "Contract", casual: "Casual", custom: "Custom" };

export default function CareerProfilesPage() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [draft, setDraft] = useState(blank);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<number | "new" | null>(null);
  const [message, setMessage] = useState("");
  async function reload() {
    const response = await workspaceFetch("/api/v1/career-profiles");
    if (!response.ok) throw new Error("Could not load career profiles.");
    setProfiles(await response.json() as Profile[]);
  }
  useEffect(() => { let active = true; workspaceFetch("/api/v1/career-profiles").then(async r => { if (!r.ok) throw new Error(); const rows = await r.json() as Profile[]; if (active) setProfiles(rows); }).catch(() => { if (active) setMessage("Career profiles could not be loaded. Check your connection."); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, []);
  async function create() {
    if (!draft.name.trim()) { setMessage("Give this profile a name."); return; }
    setBusy("new"); setMessage("");
    try { const r = await workspaceFetch("/api/v1/career-profiles", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(draft) }); if (!r.ok) throw new Error("Could not create profile."); setDraft(blank); await reload(); setMessage("Career profile created."); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Could not create profile."); } finally { setBusy(null); }
  }
  async function save(profile: Profile) {
    setBusy(profile.id); setMessage("");
    try { const { id, ...values } = profile; const r = await workspaceFetch(`/api/v1/career-profiles/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(values) }); if (!r.ok) throw new Error("Could not save profile."); await reload(); setMessage(`Saved ${profile.name}.`); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Could not save profile."); } finally { setBusy(null); }
  }
  async function copyMaster(profile: Profile) {
    setBusy(profile.id); setMessage("");
    try { const r = await workspaceFetch(`/api/v1/career-profiles/from-master/${profile.id}`, { method: "POST" }); if (!r.ok) throw new Error("Save your master CV first."); await reload(); setMessage(`Copied master CV content into ${profile.name}. You can now customise it independently.`); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Could not copy master CV."); } finally { setBusy(null); }
  }
  async function remove(profile: Profile) {
    if (!window.confirm(`Delete the ${profile.name} profile? Saved tailored CVs will be kept, but detached from this profile.`)) return;
    setBusy(profile.id);
    try { const r = await workspaceFetch(`/api/v1/career-profiles/${profile.id}`, { method: "DELETE" }); if (!r.ok) throw new Error("Could not delete profile."); await reload(); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Could not delete profile."); } finally { setBusy(null); }
  }
  function change(id: number, key: keyof Profile, value: string) { setProfiles(rows => rows.map(p => p.id === id ? { ...p, [key]: value } : p)); }
  return <div className="min-h-screen bg-[var(--surface)]"><WorkspaceNav active="/career-profiles" /><div className="lg:pl-[248px]"><WorkspaceHeader /><main className="mx-auto max-w-[1100px] px-6 py-9 md:px-10">
    <p className="text-sm font-semibold text-[var(--brand)]">YOUR CAREER DIRECTIONS</p><h1 className="mt-1 text-3xl font-semibold tracking-tight">Career profiles</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">Keep separate CV starting points for full-time, part-time, contract and other career directions. Each profile can produce its own job-specific CVs. Your master CV is never overwritten.</p>
    <section className="mt-7 rounded-2xl border border-[var(--line)] bg-white p-5"><div className="flex items-center gap-2"><Plus size={18}/><h2 className="font-semibold">Create a profile</h2></div><div className="mt-4 grid gap-3 sm:grid-cols-2"><label className="text-sm font-medium">Profile name<input className={field} placeholder="e.g. Full-time software roles" value={draft.name} onChange={e => setDraft(v => ({ ...v, name: e.target.value }))}/></label><label className="text-sm font-medium">Employment type<select className={field} value={draft.employment_type} onChange={e => setDraft(v => ({ ...v, employment_type: e.target.value }))}>{Object.entries(labels).map(([v,l]) => <option key={v} value={v}>{l}</option>)}</select></label><label className="text-sm font-medium sm:col-span-2">Target roles<input className={field} placeholder="Software Engineer, Backend Developer…" value={draft.target_roles} onChange={e => setDraft(v => ({ ...v, target_roles: e.target.value }))}/></label></div><button onClick={() => void create()} disabled={busy !== null} className="mt-4 inline-flex items-center gap-2 rounded-xl bg-[var(--brand)] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"><Plus size={16}/>{busy === "new" ? "Creating…" : "Create profile"}</button></section>
    {loading ? <p className="mt-6 text-sm text-[var(--muted)]">Loading profiles…</p> : null}
    {!loading && profiles.length === 0 ? <div className="mt-6 rounded-2xl border border-dashed border-[var(--line)] p-8 text-center"><Users className="mx-auto text-[var(--muted)]"/><p className="mt-2 font-medium">No career profiles yet</p><p className="mt-1 text-sm text-[var(--muted)]">Create your first profile above.</p></div> : null}
    <div className="mt-6 space-y-5">{profiles.map(p => <section key={p.id} className="rounded-2xl border border-[var(--line)] bg-white p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-semibold">{p.name}</h2><p className="mt-1 text-xs text-[var(--muted)]">{labels[p.employment_type] ?? p.employment_type} · {p.target_roles || "Add target roles"}</p></div><div className="flex gap-2"><button onClick={() => void copyMaster(p)} disabled={busy !== null} className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-semibold"><Copy size={14}/>Copy master CV</button><button onClick={() => void remove(p)} disabled={busy !== null} aria-label="Delete profile" className="rounded-lg border border-[var(--line)] p-2 text-rose-700"><Trash2 size={15}/></button></div></div><div className="mt-4 grid gap-3 sm:grid-cols-2"><label className="text-sm font-medium">Profile name<input className={field} value={p.name} onChange={e => change(p.id, "name", e.target.value)}/></label><label className="text-sm font-medium">Employment type<select className={field} value={p.employment_type} onChange={e => change(p.id, "employment_type", e.target.value)}>{Object.entries(labels).map(([v,l]) => <option key={v} value={v}>{l}</option>)}</select></label><label className="text-sm font-medium">Target roles<input className={field} value={p.target_roles} onChange={e => change(p.id, "target_roles", e.target.value)}/></label><label className="text-sm font-medium">Location<input className={field} value={p.location} onChange={e => change(p.id, "location", e.target.value)}/></label><label className="text-sm font-medium">Name on CV<input className={field} value={p.cv_name} onChange={e => change(p.id, "cv_name", e.target.value)}/></label><label className="text-sm font-medium">CV headline<input className={field} value={p.headline} onChange={e => change(p.id, "headline", e.target.value)}/></label>{areas.map(key => <label key={key} className="text-sm font-medium sm:col-span-2 capitalize">{key}<textarea className={field + " min-h-24"} value={p[key]} onChange={e => change(p.id, key, e.target.value)}/></label>)}<button onClick={() => void save(p)} disabled={busy !== null} className="inline-flex items-center justify-center gap-2 rounded-xl bg-[var(--brand)] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"><Save size={15}/>{busy === p.id ? "Saving…" : "Save profile"}</button></div></section>)}</div>
    {message ? <p className="mt-5 text-sm" role="status">{message}</p> : null}
  </main></div></div>;
}
