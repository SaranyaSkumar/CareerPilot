# CareerPilot

An AI-powered career workspace for discovering opportunities, building ATS-friendly CVs, preparing applications, and managing the job-search journey.

## Product direction

CareerPilot is being built personal-first, with an architecture that can support multiple users later. AI-generated work is reviewable and approval-gated: the platform does not submit applications or contact employers without explicit user approval.

## Planned MVP

- Career profile and evidence-backed master CV
- CV Studio with editable CV content and ATS-friendly PDF/DOCX export
- General and job-specific ATS analysis
- New Zealand-first job discovery and explainable matching
- Application preparation, quality checks, and tracking
- Agent run history and approval controls

## Architecture

The initial implementation is a modular monolith: Next.js + TypeScript + Tailwind for the web app, FastAPI for the API, and PostgreSQL for persistent data. Background processing and external integrations will be introduced incrementally.

See `docs/` for the product specification and architecture.

## Job discovery — first release

The Discover jobs workspace now supports:

- Saving a vacancy from a public job-board or company careers-page URL.
- Pasting the original job description so it is available for later matching.
- Searching saved opportunities by role, company, skills, location, and source.
- Filtering saved and archived roles, restoring archived roles, and deleting entries.
- Duplicate URL detection to avoid saving the same listing twice.

This release is a personal job inbox, not a live job-board aggregator. It does not scrape SEEK, Trade Me Jobs, LinkedIn, or employer sites. Provider integrations will be added only through permitted feeds or APIs and in accordance with their terms. Job descriptions and URLs are user-provided and should be treated as untrusted content.

The API is available at `GET/POST /api/v1/jobs`, `PATCH /api/v1/jobs/{id}`, and `DELETE /api/v1/jobs/{id}`. Search supports `q`, `location`, and `status` query parameters.

## Vercel multi-service deployment

The repository defines two Vercel services in the root `vercel.json`:

- `web`: Next.js application rooted at `apps/web`; this is the only service receiving public traffic.
- `backend`: FastAPI application rooted at `backend`, with ASGI entrypoint `app.main:app`.

The web service has an internal service binding to `backend`. Vercel injects the backend service URL into the web runtime as `CAREERPILOT_BACKEND_URL`. Browser requests use same-origin `/api/*` paths; the Next.js catch-all route at `apps/web/src/app/api/[...path]/route.ts` forwards those requests server-side to the bound backend. The root rewrite sends all public paths to `web`; there is no direct public rewrite to the backend service.

### Required deployment configuration

- Configure `DATABASE_URL` for the backend to point to a managed PostgreSQL database. The default SQLite database is suitable only for local development and is not durable on serverless instances.
- Configure the `CAREERPILOT_BACKEND_URL` service binding through Vercel as declared in `vercel.json`; do not set a public `NEXT_PUBLIC_API_URL`.
- Ensure the Vercel project is linked to this repository and supports the configured multi-service deployment.

### Security gate before production

This is still a personal-development API with a singleton profile/CV and no authentication or per-user authorization. Although the backend service is not routed directly from the public edge, the web proxy intentionally exposes its current API paths at same-origin `/api/v1/*`. **Do not use this deployment with real personal data or promote it to production until authentication, per-user data isolation, authorization, and appropriate database protections are implemented and tested.** Keeping the backend service internal is not a substitute for API authentication.

### CV document export

CV Studio can generate an ATS-friendly, single-column PDF or editable Word document from the saved CV. The export endpoint builds each file in memory and returns it as a download; no generated CV files are persisted on the server. The export uses the facts entered in CV Studio and does not add inferred experience, skills, dates, or achievements.

### CV version history

CV Studio can save named, immutable snapshots of the current CV draft, optionally tagged with a target role and company. The version list is newest-first. Restoring a snapshot copies its content back into the active CV editor; the saved snapshot remains unchanged. PDF and Word export continue to use the active CV draft, so restore the intended version before exporting it.
