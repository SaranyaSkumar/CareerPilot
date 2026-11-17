// Mirrors the ATS export parser in backend/app/cv_export.py so the print preview
// uses the same contact line, role blocks, and skill lines as the PDF and Word file.

export type CvContact = {
  email: string;
  phone: string;
  location: string;
  websiteUrl: string;
  linkedinUrl: string;
  githubUrl: string;
};

export type CvEntry = {
  title: string;
  dates: string;
  companyLine: string;
  bullets: string[];
  paragraphs: string[];
};

const BULLET = /^[-*•·–—]\s+/;
const DATE_TEXT =
  /^(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+)?(?:19|20)\d{2}(?:\s*(?:[-–—/]|to)\s*(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+)?(?:(?:19|20)\d{2}|present|current))?$/i;

type DraftEntry = {
  title: string;
  dates: string;
  company: string;
  location: string;
  bullets: string[];
  paragraphs: string[];
  expectCompany: boolean;
};

export const emptyContact: CvContact = {
  email: "",
  phone: "",
  location: "",
  websiteUrl: "",
  linkedinUrl: "",
  githubUrl: "",
};

export function contactLine(contact: CvContact): string {
  return [contact.email, contact.phone, contact.location, contact.websiteUrl, contact.linkedinUrl, contact.githubUrl]
    .map((part) => part.trim())
    .filter((part) => part.length > 0)
    .join(" | ");
}

export function formatSkillLines(value: string): string[] {
  const rawLines = value
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .split("\n")
    .map((line) => line.trim().replace(BULLET, ""))
    .filter((line) => line.length > 0);
  const grouped: string[] = [];
  let loose: string[] = [];

  function flush() {
    if (loose.length === 0) return;
    const seen = new Set<string>();
    const unique: string[] = [];
    for (const chunk of loose) {
      for (const part of chunk.split(/[,;]/)) {
        const item = part.trim();
        const key = item.toLocaleLowerCase();
        if (!item || seen.has(key)) continue;
        seen.add(key);
        unique.push(item);
      }
    }
    if (unique.length > 0) grouped.push(unique.join(", "));
    loose = [];
  }

  for (const line of rawLines) {
    if (line.includes(":")) {
      flush();
      const splitAt = line.indexOf(":");
      const label = line.slice(0, splitAt).trim();
      const parts = line
        .slice(splitAt + 1)
        .split(/[,;]/)
        .map((part) => part.trim())
        .filter((part) => part.length > 0);
      grouped.push(parts.length > 0 ? `${label}: ${parts.join(", ")}` : label);
    } else {
      loose.push(line);
    }
  }
  flush();
  return grouped;
}

export function parseEntries(value: string): CvEntry[] {
  const entries: DraftEntry[] = [];
  let current: DraftEntry | null = null;

  function close() {
    if (current) entries.push(current);
    current = null;
  }

  for (const raw of value.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n")) {
    const line = raw.trim();
    if (!line) {
      close();
      continue;
    }
    if (BULLET.test(line)) {
      current ??= blankEntry();
      current.bullets.push(line.replace(BULLET, "").trim());
      current.expectCompany = false;
      continue;
    }
    const dated = datedHeader(line);
    if (dated && current) {
      close();
      current = dated;
      continue;
    }
    if (current?.expectCompany) {
      if (looksLikeProse(line)) current.paragraphs.push(line);
      else {
        const [company, location] = splitCompany(line);
        current.company = company;
        current.location = location;
      }
      current.expectCompany = false;
      continue;
    }
    if (!current) {
      current = dated ?? undatedHeader(line) ?? { ...blankEntry(), paragraphs: [line] };
      continue;
    }
    current.paragraphs.push(line);
  }
  close();
  return entries.map((entry) => ({
    title: entry.title,
    dates: entry.dates,
    companyLine: entry.company && entry.location ? `${entry.company}, ${entry.location}` : entry.company || entry.location,
    bullets: entry.bullets,
    paragraphs: entry.paragraphs,
  }));
}

export function summaryLines(value: string): string[] {
  return value
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

function blankEntry(): DraftEntry {
  return { title: "", dates: "", company: "", location: "", bullets: [], paragraphs: [], expectCompany: false };
}

function looksLikeDates(value: string): boolean {
  const text = value.trim().replace(/\s+/g, " ");
  if (/^(present|current)$/i.test(text)) return true;
  return DATE_TEXT.test(text);
}

function looksLikeProse(value: string): boolean {
  const words = value.split(/\s+/);
  if (words.length >= 8) return true;
  return /[.!?]/.test(value) && words.length >= 4;
}

function parts(value: string): string[] {
  return value
    .split("|")
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
}

function datedHeader(value: string): DraftEntry | null {
  const pieces = parts(value);
  if (pieces.length < 2 || !looksLikeDates(pieces[pieces.length - 1])) return null;
  const middle = pieces.slice(1, -1);
  return {
    title: pieces[0],
    dates: pieces[pieces.length - 1],
    company: middle[0] ?? "",
    location: middle.slice(1).join(", "),
    bullets: [],
    paragraphs: [],
    expectCompany: middle.length === 0,
  };
}

function undatedHeader(value: string): DraftEntry | null {
  const pieces = parts(value);
  if (pieces.length < 2 || looksLikeDates(pieces[pieces.length - 1])) return null;
  return {
    title: pieces[0],
    dates: "",
    company: pieces[1],
    location: pieces.slice(2).join(", "),
    bullets: [],
    paragraphs: [],
    expectCompany: false,
  };
}

function splitCompany(value: string): [string, string] {
  const pieces = parts(value);
  if (pieces.length >= 2 && !looksLikeDates(pieces[pieces.length - 1])) {
    return [pieces[0], pieces.slice(1).join(", ")];
  }
  if (value.includes(",") && !looksLikeProse(value)) {
    const splitAt = value.indexOf(",");
    return [value.slice(0, splitAt).trim(), value.slice(splitAt + 1).trim()];
  }
  return [value.trim(), ""];
}
