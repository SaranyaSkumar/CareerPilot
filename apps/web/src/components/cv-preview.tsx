import type { ReactNode } from "react";
import { contactLine, formatSkillLines, parseEntries, summaryLines, type CvContact } from "@/lib/cv-layout";

type PreviewCv = {
  name: string;
  headline: string;
  summary: string;
  experience: string;
  skills: string;
  education: string;
};

export function CvPreview({ cv, contact }: { cv: PreviewCv; contact: CvContact }) {
  const line = contactLine(contact);
  const summary = summaryLines(cv.summary);
  const experience = parseEntries(cv.experience);
  const skills = formatSkillLines(cv.skills);
  const education = parseEntries(cv.education);

  return (
    <article
      id="cv-print-area"
      style={{ fontFamily: "Arial, Helvetica, sans-serif" }}
      className="mx-auto min-h-[720px] max-w-[680px] border border-[#e8e8e2] bg-white p-8 text-[#26302a] shadow-sm print:min-h-0 print:max-w-none print:border-0 print:p-0 print:shadow-none"
    >
      <h2 className="text-[26px] font-bold leading-none tracking-tight text-[#174c3a]">{cv.name.trim() || "Your Name"}</h2>
      {cv.headline.trim() ? <p className="mt-1 text-[13px] font-semibold leading-5 text-[#4b5b51]">{cv.headline.trim()}</p> : null}
      {line ? <p className="mt-1 text-[11.5px] leading-5 text-[#4b5b51]">{line}</p> : null}

      {summary.length > 0 ? (
        <PreviewSection title="Professional Summary">
          {summary.map((paragraph) => (
            <p key={paragraph} className="mt-2 text-[13px] leading-5">
              {paragraph}
            </p>
          ))}
        </PreviewSection>
      ) : null}

      {experience.length > 0 ? (
        <PreviewSection title="Experience">
          {experience.map((entry, index) => (
            <PreviewEntry key={`${entry.title}-${entry.dates}-${index}`} entry={entry} first={index === 0} />
          ))}
        </PreviewSection>
      ) : null}

      {skills.length > 0 ? (
        <PreviewSection title="Skills">
          {skills.map((skillLine, index) => (
            <p key={`${skillLine}-${index}`} className="mt-2 text-[13px] leading-5">
              {skillLine}
            </p>
          ))}
        </PreviewSection>
      ) : null}

      {education.length > 0 ? (
        <PreviewSection title="Education">
          {education.map((entry, index) => (
            <PreviewEntry key={`${entry.title}-${entry.dates}-${index}`} entry={entry} first={index === 0} />
          ))}
        </PreviewSection>
      ) : null}
    </article>
  );
}

function PreviewSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-5">
      <h3 className="border-b border-[#174c3a] pb-1 text-[11px] font-bold uppercase tracking-[0.12em] text-[#174c3a]">{title}</h3>
      {children}
    </section>
  );
}

function PreviewEntry({
  entry,
  first,
}: {
  entry: { title: string; dates: string; companyLine: string; bullets: string[]; paragraphs: string[] };
  first: boolean;
}) {
  return (
    <div className={first ? "mt-2 break-inside-avoid" : "mt-4 break-inside-avoid"}>
      {entry.title ? (
        <div className="flex items-baseline justify-between gap-4">
          <p className="text-[13.5px] font-bold leading-5">{entry.title}</p>
          {entry.dates ? <p className="shrink-0 text-[12px] leading-5 text-[#4b5b51]">{entry.dates}</p> : null}
        </div>
      ) : null}
      {entry.companyLine ? <p className="text-[12.5px] italic leading-5 text-[#4b5b51]">{entry.companyLine}</p> : null}
      {entry.paragraphs.map((paragraph, index) => (
        <p key={`${paragraph}-${index}`} className="mt-1 text-[13px] leading-5">
          {paragraph}
        </p>
      ))}
      {entry.bullets.length > 0 ? (
        <ul className="mt-0.5 list-disc space-y-0.5 pl-5 text-[13px] leading-5">
          {entry.bullets.map((bullet, index) => (
            <li key={`${bullet}-${index}`} className="pl-1">
              {bullet}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
