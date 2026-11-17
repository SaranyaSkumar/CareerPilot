export type CvContent = {
  name: string;
  headline: string;
  summary: string;
  experience: string;
  skills: string;
  education: string;
};

export type SuggestionItem = {
  id: string;
  section: "summary" | "experience" | "skills";
  source_line: number | null;
  before: string;
  after: string;
  unsupported: boolean;
  note: string;
};

function promoteSkills(skills: string, phrases: string[]): string {
  const useLines = skills.includes("\n");
  const parts = skills.split(useLines ? "\n" : ",").map(part => part.trim()).filter(Boolean);
  const front: string[] = [];
  const rest: string[] = [];
  const seen = new Set<string>();
  for (const phrase of phrases) {
    const key = phrase.trim().toLowerCase();
    if (!key || seen.has(key)) continue;
    const existing = parts.find(part => part.toLowerCase() === key);
    front.push(existing ?? phrase.trim());
    seen.add(key);
  }
  for (const part of parts) {
    if (!seen.has(part.toLowerCase())) rest.push(part);
  }
  return [...front, ...rest].join(useLines ? "\n" : ", ");
}

export function applyAcceptedSuggestions(
  cv: CvContent,
  items: SuggestionItem[],
  acceptedIds: ReadonlySet<string>,
  useSuggestedOrder: boolean,
): CvContent {
  const accepted = (item: SuggestionItem) => acceptedIds.has(item.id) && !item.unsupported;

  let summary = cv.summary;
  for (const item of items) {
    if (item.section === "summary" && accepted(item) && item.after.trim()) summary = item.after;
  }

  const experienceItems = items.filter(item => item.section === "experience");
  let experience = cv.experience;
  if (experienceItems.length > 0) {
    const lines = cv.experience.split("\n");
    if (useSuggestedOrder) {
      const used = new Set<number>();
      const next: string[] = [];
      for (const item of experienceItems) {
        const index = item.source_line;
        if (index === null || index < 0 || index >= lines.length || used.has(index)) continue;
        used.add(index);
        next.push(accepted(item) && item.after.trim() ? item.after : lines[index]);
      }
      lines.forEach((line, index) => {
        if (!used.has(index)) next.push(line);
      });
      experience = next.join("\n");
    } else {
      const next = lines.slice();
      for (const item of experienceItems) {
        const index = item.source_line;
        if (!accepted(item) || index === null || index < 0 || index >= next.length || !item.after.trim()) continue;
        next[index] = item.after;
      }
      experience = next.join("\n");
    }
  }

  const phrases = items
    .filter(item => item.section === "skills" && accepted(item))
    .map(item => item.before.trim() || item.after.trim())
    .filter(Boolean);

  return {
    ...cv,
    summary,
    experience,
    skills: phrases.length > 0 ? promoteSkills(cv.skills, phrases) : cv.skills,
  };
}
