import { createClient } from "@/lib/supabase/client";

export type DraftKind = "profile" | "cv";

export async function currentUserId(): Promise<string | null> {
  const supabase = createClient();
  if (!supabase) return null;
  const { data } = await supabase.auth.getClaims();
  const sub = data?.claims?.sub;
  return typeof sub === "string" ? sub : null;
}

export function draftKey(kind: DraftKind, userId: string): string {
  return `careerpilot.${kind}.${userId}`;
}

export function readDraft(kind: DraftKind, userId: string): string | null {
  return window.localStorage.getItem(draftKey(kind, userId));
}

export function writeDraft(kind: DraftKind, userId: string, value: string): void {
  window.localStorage.setItem(draftKey(kind, userId), value);
  window.localStorage.removeItem(kind === "profile" ? "careerpilot.profile" : "careerpilot.cv");
}

export function clearLocalDrafts(): void {
  const keys: string[] = [];
  for (let index = 0; index < window.localStorage.length; index += 1) {
    const key = window.localStorage.key(index);
    if (key && (key.startsWith("careerpilot.profile") || key.startsWith("careerpilot.cv"))) {
      keys.push(key);
    }
  }
  keys.forEach((key) => window.localStorage.removeItem(key));
}
