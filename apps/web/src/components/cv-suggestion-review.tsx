"use client";

import { useEffect, useState } from "react";
import { applyAcceptedSuggestions, type CvContent, type SuggestionItem } from "@/lib/cv-suggestions";
import { workspaceFetch } from "@/lib/workspace-fetch";

export type KeywordGap = { term: string; note: string };
export type ScoreSnapshot = {
  formatting_score: number;
  content_score: number | null;
  overall_score: number | null;
};
export type AiResult = {
  operation: "tailor" | "improve_bullets" | "adjust";
  job_id: number | null;
  job_title: string;
  company: string;
  items: SuggestionItem[];
  could_not_support: string[];
  keyword_gaps?: KeywordGap[];
  original_score?: ScoreSnapshot | null;
  order_changed: boolean;
  input_tokens: number;
  output_tokens: number;
};

const suggestionField = "mt-1 w-full rounded-xl border border-[var(--line)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--brand)] focus:ring-2 focus:ring-[var(--brand-soft)]";

function SuggestionCard({
  item,
  decision,
  onDecision,
  onEdit,
}: {
  item: SuggestionItem;
  decision: "pending" | "accepted" | "rejected";
  onDecision: (id: string, decision: "accepted" | "rejected") => void;
  onEdit: (id: string, after: string) => void;
}) {
  const label = item.section === "summary" ? "Summary" : item.section === "skills" ? "Skill" : "Experience";
  const unchanged = item.section !== "skills" && item.before === item.after && !item.unsupported;
  if (unchanged) {
    return (
      <div className="rounded-xl border border-dashed border-[var(--line)] px-3 py-2 text-sm text-[var(--muted)]">
        <span className="font-medium text-[var(--foreground)]">{label} kept as written. </span>
        {item.before}
      </div>
    );
  }
  return (
    <div className={"rounded-xl border p-3 " + (item.unsupported ? "border-amber-200 bg-amber-50" : decision === "accepted" ? "border-[var(--brand)] bg-[var(--brand-soft)]" : "border-[var(--line)] bg-white")}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">{label}</p>
        {item.unsupported ? (
          <p className="text-xs font-semibold text-amber-800">Can’t accept — not supported by your CV</p>
        ) : (
          <div className="flex gap-2">
            <button type="button" onClick={() => onDecision(item.id, "accepted")} className="rounded-lg bg-[var(--brand)] px-3 py-1.5 text-xs font-semibold text-white" aria-pressed={decision === "accepted"}>Accept</button>
            <button type="button" onClick={() => onDecision(item.id, "rejected")} className="rounded-lg border border-[var(--line)] bg-white px-3 py-1.5 text-xs font-semibold" aria-pressed={decision === "rejected"}>Reject</button>
          </div>
        )}
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <div>
          <p className="text-xs font-semibold text-[var(--muted)]">Current</p>
          <p className="mt-1 whitespace-pre-wrap text-sm leading-6">{item.before || "Empty"}</p>
        </div>
        <div>
          <label className="block text-xs font-semibold text-[var(--muted)]">Suggestion
            <textarea
              className={suggestionField + " min-h-20 resize-y"}
              value={item.after}
              onChange={event => onEdit(item.id, event.target.value)}
              disabled={item.unsupported}
            />
          </label>
        </div>
      </div>
      {item.note ? <p className="mt-2 text-xs leading-5 text-[var(--muted)]">{item.note}</p> : null}
    </div>
  );
}

export function SuggestionReview({
  base,
  result,
  stale,
  busy,
  jobDescription,
  saveLabel,
  showVersionOption,
  onSave,
  onDiscard,
}: {
  base: CvContent;
  result: AiResult;
  stale: boolean;
  busy: boolean;
  jobDescription: string;
  saveLabel: string;
  showVersionOption: boolean;
  onSave: (draft: CvContent, saveVersion: boolean) => Promise<void>;
  onDiscard: () => void;
}) {
  const [items, setItems] = useState(result.items);
  const [decisions, setDecisions] = useState<Record<string, "accepted" | "rejected">>({});
  const [gaps, setGaps] = useState<Record<string, boolean>>({});
  const [useOrder, setUseOrder] = useState(false);
  const [saveVersion, setSaveVersion] = useState(false);
  const [notice, setNotice] = useState("");
  const [adjustedScore, setAdjustedScore] = useState<number | null>(null);

  const acceptedIds = new Set(
    Object.entries(decisions).filter(([, decision]) => decision === "accepted").map(([id]) => id),
  );
  const confirmedGaps = (result.keyword_gaps ?? []).filter(gap => gaps[gap.term]).map(gap => gap.term);
  const draft = applyAcceptedSuggestions(base, items, acceptedIds, useOrder && result.order_changed, confirmedGaps);
  const scorePayload = JSON.stringify({ ...draft, job_description: jobDescription });

  useEffect(() => {
    if (!jobDescription.trim() || stale) return;
    let active = true;
    const timer = setTimeout(() => {
      void workspaceFetch("/api/v1/cv/variants/score", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: scorePayload,
      }).then(async response => {
        if (!active || !response.ok) return;
        const body = await response.json() as ScoreSnapshot;
        setAdjustedScore(body.overall_score);
      }).catch(() => undefined);
    }, 350);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [scorePayload, jobDescription, stale]);

  function acceptAll() {
    const next: Record<string, "accepted"> = {};
    for (const item of items) {
      if (!item.unsupported && (item.section === "skills" || item.before !== item.after)) next[item.id] = "accepted";
    }
    setDecisions(next);
  }

  return (
    <div className="mt-5 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">Review suggestions</h3>
        <button type="button" onClick={acceptAll} className="rounded-lg border border-[var(--line)] px-3 py-1.5 text-xs font-semibold">Accept all</button>
      </div>
      <p className="text-xs text-[var(--muted)]">
        {result.input_tokens} input tokens and {result.output_tokens} output tokens were used. Nothing is saved until you accept it. You can edit a suggestion before saving.
      </p>
      {result.original_score ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl border border-[var(--line)] p-3">
            <p className="text-xs text-[var(--muted)]">Original alignment</p>
            <p className="mt-1 text-2xl font-semibold">{result.original_score.overall_score === null ? "—" : <>{result.original_score.overall_score}<span className="text-sm font-normal">/100</span></>}</p>
          </div>
          <div className="rounded-xl bg-[var(--brand-soft)] p-3">
            <p className="text-xs text-[var(--muted)]">Adjusted variant, with what you have accepted</p>
            <p className="mt-1 text-2xl font-semibold">{adjustedScore === null ? "—" : <>{adjustedScore}<span className="text-sm font-normal">/100</span></>}</p>
          </div>
        </div>
      ) : null}
      {result.could_not_support.length > 0 ? (
        <div className="rounded-xl bg-amber-50 px-4 py-3">
          <p className="text-sm font-semibold text-amber-950">Left out, because your CV does not say it</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-amber-950">
            {result.could_not_support.map(note => <li key={note}>{note}</li>)}
          </ul>
        </div>
      ) : null}
      {items.map(item => (
        <SuggestionCard
          key={item.id}
          item={item}
          decision={decisions[item.id] ?? "pending"}
          onDecision={(id, decision) => setDecisions(current => ({ ...current, [id]: decision }))}
          onEdit={(id, after) => setItems(current => current.map(entry => entry.id === id ? { ...entry, after } : entry))}
        />
      ))}
      {(result.keyword_gaps ?? []).length > 0 ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3">
          <p className="text-sm font-semibold text-amber-950">Gaps you could add if true</p>
          <p className="mt-1 text-xs leading-5 text-amber-950">These keywords are not in your saved CV. Tick one only when you genuinely have it. Ticked keywords are added to this variant’s skills list, not to your original CV.</p>
          <div className="mt-3 space-y-2">
            {result.keyword_gaps?.map(gap => (
              <label key={gap.term} className="flex items-start gap-2 text-sm text-amber-950">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={gaps[gap.term] === true}
                  onChange={event => setGaps(current => ({ ...current, [gap.term]: event.target.checked }))}
                />
                <span><span className="font-semibold">{gap.term}</span> — {gap.note}</span>
              </label>
            ))}
          </div>
        </div>
      ) : null}
      {result.order_changed ? (
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-1" checked={useOrder} onChange={event => setUseOrder(event.target.checked)} />
          <span>Use the suggested order of experience lines. Rejected lines keep their current wording.</span>
        </label>
      ) : null}
      {showVersionOption ? (
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-1" checked={saveVersion} onChange={event => setSaveVersion(event.target.checked)} />
          <span>Also keep a saved CV version of the accepted result.</span>
        </label>
      ) : null}
      {stale ? <p className="text-sm text-amber-800">Your draft changed after this suggestion. Generate it again before accepting.</p> : null}
      {notice ? <p className="text-sm" role="status">{notice}</p> : null}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy || stale}
          onClick={() => {
            if (JSON.stringify(draft) === JSON.stringify(base)) {
              setNotice("Accept a supported suggestion, or tick a gap you genuinely have, before saving.");
              return;
            }
            setNotice("");
            void onSave(draft, saveVersion);
          }}
          className="rounded-xl bg-[var(--brand)] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
        >
          {busy ? "Saving…" : saveLabel}
        </button>
        <button type="button" onClick={onDiscard} className="rounded-xl border border-[var(--line)] px-4 py-2.5 text-sm font-semibold">Discard suggestions</button>
      </div>
    </div>
  );
}
