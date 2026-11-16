"use client";

import { useEffect, useState } from "react";
import { Save, UserRound } from "lucide-react";
import { WorkspaceHeader, WorkspaceNav } from "@/components/workspace-nav";

type Profile = { fullName: string; email: string; headline: string; location: string; summary: string; skills: string };
const emptyProfile: Profile = { fullName: "", email: "", headline: "", location: "New Zealand", summary: "", skills: "" };

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile>(emptyProfile);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    const raw = window.localStorage.getItem("careerpilot.profile");
    if (raw) { try { setProfile({ ...emptyProfile, ...JSON.parse(raw) }); } catch { window.localStorage.removeItem("careerpilot.profile"); } }
  }, []);
  function update<K extends keyof Profile>(key: K, value: Profile[K]) { setProfile(current => ({ ...current, [key]: value })); setSaved(false); }
  function save() { window.localStorage.setItem("careerpilot.profile", JSON.stringify(profile)); setSaved(true); }
  const field = "mt-1 w-full rounded-xl border border-[var(--line)] bg-white px-3.5 py-3 text-sm text-[var(--foreground)] outline-none transition focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand-soft)]";
  return <main className="min-h-screen"><WorkspaceNav active="/profile"/><div className="lg:pl-[248px]"><WorkspaceHeader/><div className="mx-auto max-w-4xl px-6 py-9 md:px-10"><div className="flex items-start gap-4"><span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-[var(--brand-soft)] text-[var(--brand)]"><UserRound/></span><div><p className="text-sm font-semibold text-[var(--brand)]">YOUR FOUNDATION</p><h1 className="mt-1 text-3xl font-semibold tracking-tight">Career profile</h1><p className="mt-2 text-sm text-[var(--muted)]">Keep your verified career information here. CVs and applications will be created from this profile.</p></div></div>
<section className="mt-8 rounded-2xl border border-[var(--line)] bg-white p-6 md:p-8"><h2 className="font-semibold">Personal details</h2><p className="mt-1 text-sm text-[var(--muted)]">Only add details you are comfortable storing in this personal workspace.</p><div className="mt-6 grid gap-5 md:grid-cols-2"><label className="text-sm font-medium">Full name<input className={field} value={profile.fullName} onChange={e=>update("fullName",e.target.value)} placeholder="Your name"/></label><label className="text-sm font-medium">Email address<input className={field} type="email" value={profile.email} onChange={e=>update("email",e.target.value)} placeholder="you@example.com"/></label><label className="text-sm font-medium">Professional headline<input className={field} value={profile.headline} onChange={e=>update("headline",e.target.value)} placeholder="e.g. Software Engineer"/></label><label className="text-sm font-medium">Preferred location<input className={field} value={profile.location} onChange={e=>update("location",e.target.value)} placeholder="e.g. Auckland, New Zealand"/></label></div><div className="mt-6"><label className="text-sm font-medium">Professional summary<textarea className={field+" min-h-32 resize-y"} value={profile.summary} onChange={e=>update("summary",e.target.value)} placeholder="Summarise your experience, strengths and the kind of work you do."/></label></div><div className="mt-6"><label className="text-sm font-medium">Skills<textarea className={field+" min-h-24 resize-y"} value={profile.skills} onChange={e=>update("skills",e.target.value)} placeholder="Type skills separated by commas"/></label><p className="mt-2 text-xs text-[var(--muted)]">Use skills you can confidently discuss and support with real experience.</p></div><div className="mt-7 flex flex-wrap items-center gap-3"><button onClick={save} className="inline-flex items-center gap-2 rounded-xl bg-[var(--brand)] px-5 py-3 text-sm font-semibold text-white hover:bg-[var(--brand-dark)]"><Save size={16}/>Save profile</button>{saved&&<span role="status" className="text-sm font-medium text-[var(--brand)]">Saved on this device.</span>}</div></section><p className="mt-4 text-xs leading-5 text-[var(--muted)]">Development note: this first version stores profile data in this browser only. Account authentication and encrypted server-side persistence will be added before multi-device or shared use.</p></div></div></main>;
}
