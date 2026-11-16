# CareerPilot — Product Specification

## Product vision
CareerPilot is an AI-assisted career workspace that helps a person discover suitable opportunities, present their experience clearly, prepare high-quality applications, and manage the end-to-end job search.

**Initial audience:** a single primary user, starting with New Zealand roles. The product is designed so multi-user support can be added without rebuilding the domain model.

## Product principles
1. **Evidence before eloquence:** never invent employment history, qualifications, skills, dates, achievements, or metrics.
2. **Human approval:** AI prepares and recommends; the user reviews and approves. No autonomous application submission or employer communication.
3. **Explainable decisions:** job-fit assessments must show supporting evidence, gaps, and uncertainty.
4. **User-owned career record:** maintain one verified master profile and create tailored CV/application versions from it.
5. **Source traceability:** retain the source URL and retrieval time for every imported job.
6. **Privacy by design:** minimise personal data, protect documents, and provide export/deletion paths.

## MVP modules

### 1. Career profile
- Structured profile for contact details, headline, summary, work history, education, skills, certifications, projects, and preferences.
- Support source notes and verification status for claims.
- Profile versioning so generated documents can be traced to the exact facts used.

### 2. CV Studio
- Create a CV from scratch or import PDF/DOCX for assisted extraction.
- Review and correct parsed content before it becomes trusted profile data.
- Maintain a master CV and multiple targeted versions.
- AI assistance for summaries, experience bullets, and skills wording; every suggestion must remain grounded in verified facts.
- ATS-friendly single-column templates, live preview, editing, and PDF/DOCX export.
- Save version history and associate each exported CV with an application.

### 3. ATS analyser
- General checks: standard headings, section completeness, parsing risks, layout complexity, readability, dates, and file format.
- Job-specific checks: skill/keyword coverage, relevant evidence, and missing or unclear requirements.
- Return a diagnostic score with prioritised fixes. Never claim to predict or guarantee an employer's ATS outcome.

### 4. Job discovery
- New Zealand-first search and ingestion.
- MVP sources: user-pasted job description, supported public job URL, and manual entry.
- Preserve employer, title, location, employment type, salary when supplied, source URL, posted date when known, and retrieval timestamp.
- Search, save, dismiss, deduplicate, and mark potentially expired listings.
- Add authorised feeds and integrations only after source terms and access methods are reviewed. Do not bypass logins, CAPTCHAs, paywalls, robots policies, or site terms.

### 5. Explainable job matching
- Initial configurable weighting: technical skills 30%, relevant experience 25%, responsibilities 20%, seniority 10%, location/preferences 10%, qualifications 5%.
- Show matched skills, transferable evidence, gaps, unknowns, seniority fit, and reasons to consider or skip.
- Missing exact keywords must not automatically disqualify a candidate.
- Scores are decision support, not hiring predictions.

### 6. Application Studio
- Generate a tailored CV, cover letter, application-question drafts, and interview preparation from the verified profile and a specific job description.
- Run QA for unsupported claims, incorrect dates/titles, generic language, repetition, grammar, and requirement coverage.
- User reviews and approves each document before export or external use.

### 7. Application tracker
- Statuses: Interested, Shortlisted, Preparing, Ready for review, Applied, Assessment, Interview, Offer, Rejected, Withdrawn.
- List/board views, dates, notes, job snapshot, attached document versions, interview details, reminders, and activity history.

### 8. Agent control centre
- Four initial agents: Job Scout, Fit Reviewer, Application Writer, Application QA.
- Show run status, inputs/outputs, errors, duration, usage metadata, and approval checkpoints.
- Backend enforces approval boundaries; UI controls alone are not sufficient.

## MVP acceptance criteria
- User can create and edit a structured career profile.
- User can create a CV and review imported CV content before trusting it.
- CV versions can be exported to valid PDF and DOCX.
- ATS analysis gives actionable, explainable findings and does not promise employer outcomes.
- A job can be ingested from pasted text or a supported URL, with source metadata.
- Duplicate jobs are detected.
- Match results expose evidence, gaps, and uncertainty.
- An application pack is editable and linked to the exact profile/CV version used.
- QA catches seeded unsupported claims in tests.
- The backend blocks unapproved external actions.
- Agent failures are recorded and recoverable.

## Out of scope for the first milestone
Billing, public multi-tenant SaaS, paid embedding/vector infrastructure, autonomous application submission, broad web scraping, and production deployment.

## Later opportunities
Scheduled job alerts, additional authorised job sources, career-development plans, learning recommendations, interview coaching, company research, multi-user accounts, and subscriptions.
