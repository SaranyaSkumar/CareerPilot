import assert from "node:assert/strict";
import test from "node:test";
import { applyAcceptedSuggestions, variantLabel, type CvContent, type SuggestionItem } from "./cv-suggestions.ts";

const cv: CvContent = {
  name: "Alex Example",
  headline: "Software Engineer",
  summary: "Builds dependable applications.",
  experience: "Software Engineer | Example Ltd | 2022-present\n- Built the billing API in Python\n- Wrote internal notes",
  skills: "Python, TypeScript",
  education: "BSc Computer Science",
};

function item(partial: SuggestionItem): SuggestionItem {
  return partial;
}

test("pending and rejected suggestions leave the CV unchanged", () => {
  const items = [
    item({
      id: "summary",
      section: "summary",
      source_line: null,
      before: cv.summary,
      after: "A different summary",
      unsupported: false,
      note: "",
    }),
    item({
      id: "experience-1",
      section: "experience",
      source_line: 1,
      before: "- Built the billing API in Python",
      after: "- Built the billing API in Python for production use",
      unsupported: false,
      note: "",
    }),
  ];
  const next = applyAcceptedSuggestions(cv, items, new Set(), false);
  assert.deepEqual(next, cv);
});

test("an accepted bullet replaces that line and leaves the others in place", () => {
  const items = [
    item({
      id: "experience-1",
      section: "experience",
      source_line: 1,
      before: "- Built the billing API in Python",
      after: "- Built the billing API in Python for dependable applications",
      unsupported: false,
      note: "",
    }),
  ];
  const next = applyAcceptedSuggestions(cv, items, new Set(["experience-1"]), false);
  assert.equal(
    next.experience,
    "Software Engineer | Example Ltd | 2022-present\n- Built the billing API in Python for dependable applications\n- Wrote internal notes",
  );
  assert.equal(next.summary, cv.summary);
});

test("an unsupported suggestion is not applied even when its id is accepted", () => {
  const items = [
    item({
      id: "experience-1",
      section: "experience",
      source_line: 1,
      before: "- Built the billing API in Python",
      after: "- Increased revenue by 40% at Stripe",
      unsupported: true,
      note: "Introduces a number",
    }),
  ];
  const next = applyAcceptedSuggestions(cv, items, new Set(["experience-1"]), false);
  assert.equal(next.experience, cv.experience);
});

test("suggested order is optional and keeps rejected lines on their original text", () => {
  const items = [
    item({
      id: "experience-2",
      section: "experience",
      source_line: 2,
      before: "- Wrote internal notes",
      after: "- Wrote internal notes for the billing API",
      unsupported: false,
      note: "",
    }),
    item({
      id: "experience-1",
      section: "experience",
      source_line: 1,
      before: "- Built the billing API in Python",
      after: "- Built a different billing API",
      unsupported: false,
      note: "",
    }),
    item({
      id: "experience-0",
      section: "experience",
      source_line: 0,
      before: "Software Engineer | Example Ltd | 2022-present",
      after: "Software Engineer | Example Ltd | 2022-present",
      unsupported: false,
      note: "",
    }),
  ];
  const kept = applyAcceptedSuggestions(cv, items, new Set(["experience-2"]), false);
  assert.equal(
    kept.experience,
    "Software Engineer | Example Ltd | 2022-present\n- Built the billing API in Python\n- Wrote internal notes for the billing API",
  );
  const reordered = applyAcceptedSuggestions(cv, items, new Set(["experience-2"]), true);
  assert.equal(
    reordered.experience,
    "- Wrote internal notes for the billing API\n- Built the billing API in Python\nSoftware Engineer | Example Ltd | 2022-present",
  );
});

test("a confirmed gap is added and an unticked gap is not", () => {
  const next = applyAcceptedSuggestions(cv, [], new Set(), false, ["FastAPI"]);
  assert.equal(next.skills, "FastAPI, Python, TypeScript");
  assert.equal(next.summary, cv.summary);
  const ignored = applyAcceptedSuggestions(cv, [], new Set(), false, []);
  assert.equal(ignored.skills, cv.skills);
});

test("variant labels name the role and employer without replacing a long title", () => {
  assert.equal(variantLabel("Backend Engineer", "Northwind"), "Tailored – Backend Engineer @ Northwind");
  assert.equal(variantLabel("  ", ""), "Tailored – role");
});

test("accepted skills move to the front and unsupported skills are not added", () => {
  const items = [
    item({
      id: "skill-1",
      section: "skills",
      source_line: null,
      before: "TypeScript",
      after: "TypeScript",
      unsupported: false,
      note: "",
    }),
    item({
      id: "skill-2",
      section: "skills",
      source_line: null,
      before: "Kubernetes",
      after: "Kubernetes",
      unsupported: true,
      note: "Not in the CV",
    }),
  ];
  const next = applyAcceptedSuggestions(cv, items, new Set(["skill-1", "skill-2"]), false);
  assert.equal(next.skills, "TypeScript, Python");
});
