# CareerPilot

An AI-powered career workspace for discovering opportunities, building ATS-friendly CVs, preparing applications, and managing the job-search journey.

## Product direction

Each person signs in with their own account. AI-generated work is reviewable and approval-gated: the platform does not submit applications or contact employers without explicit user approval.

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

Apply `backend/migrations_sql/20261117_0001_add_user_scoping.sql` in the Supabase SQL editor before starting this version of the API. It deletes the old sample rows and adds a `user_id` to every user-owned table. The API process does not create or migrate tables: the runtime role `careerpilot_app` has no `CREATE` privilege on `public`.

Web service (Vercel project environment, not the backend):

- `NEXT_PUBLIC_SUPABASE_URL` — `https://kcrtedhezyovfygfotia.supabase.co`
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` — the publishable key (`sb_publishable_...`)

`NEXT_PUBLIC_` values are inlined when the web app is built, so set them in Vercel before the production build.

Backend service:

- `DATABASE_URL` — the `careerpilot_app` Postgres connection string. SQLite is only for local tests and is not durable on serverless instances.
- `SUPABASE_URL` — `https://kcrtedhezyovfygfotia.supabase.co`
- `SUPABASE_JWKS_URL` — optional. When unset, the API uses `${SUPABASE_URL}/auth/v1/.well-known/jwks.json`

The `CAREERPILOT_BACKEND_URL` binding is injected from `vercel.json`. Do not set a public `NEXT_PUBLIC_API_URL`. Do not put a service-role key, secret key, or the legacy JWT secret in either service. Nothing in the web app should use a key that bypasses row level security.

Supabase Auth → URL configuration, for `https://careerpilot-eight-iota.vercel.app`:

- Site URL: `https://careerpilot-eight-iota.vercel.app`
- Redirect URLs: `https://careerpilot-eight-iota.vercel.app/auth/callback` and, for local development, `http://localhost:3000/auth/callback`
- Email provider enabled, with email + password. Magic links use the same email provider.

### Authentication and isolation

Sign-up, sign-in, magic link, sign-out, and password reset are Supabase Auth, using `@supabase/ssr` cookie sessions in the Next.js app. The Node.js proxy at `apps/web/src/proxy.ts` redirects signed-out visitors from workspace pages to `/login` and refreshes the session with `getClaims()`. It is a proxy rather than Edge middleware because Vercel Services reject Edge Functions.

The same-origin proxy reads that session and sends `Authorization: Bearer <access token>` to FastAPI. It does not forward a client-supplied user id or Authorization header. FastAPI verifies the token locally against the Supabase JWKS. This project signs tokens with ES256; RS256 is also accepted so a later asymmetric rotation keeps working. A token must use one of those algorithms, issuer `${SUPABASE_URL}/auth/v1`, audience `authenticated`, and role `authenticated`. The user id is the `sub` claim. The legacy shared JWT secret is not a verifier. Missing or invalid tokens get 401. If the API has no `SUPABASE_URL`, or the key set cannot be fetched, it fails closed with 503.

`/health` stays public and returns no personal data, so the platform can probe the service. Every `/api/v1/*` route requires a verified user.

Profile, CV, CV versions, and job listings each have a non-null `user_id`. There is one profile and one CV draft per user (`UNIQUE (user_id)`), created the first time that user opens or saves them. Versions and jobs are filtered by the same id. A request for another user's version or job id returns 404. Duplicate job URLs are enforced per user. Row level security stays enabled. `authenticated` can only touch rows where `auth.uid() = user_id`. `anon` has no grants. `careerpilot_app` still has `BYPASSRLS` and a permissive policy, so the API's `user_id` filters are the enforcement layer for the backend connection. The owner policies are what stop the Supabase Data API from returning someone else's rows.

Browser drafts in local storage are keyed by the signed-in user id and cleared on sign-out.

### CV document export

CV Studio can generate an ATS-friendly, single-column PDF or editable Word document from the saved CV. The export endpoint builds each file in memory and returns it as a download; no generated CV files are persisted on the server. The export uses the facts entered in CV Studio and does not add inferred experience, skills, dates, or achievements.

### CV version history

CV Studio can save named, immutable snapshots of the current CV draft, optionally tagged with a target role and company. The version list is newest-first. Restoring a snapshot copies its content back into the active CV editor; the saved snapshot remains unchanged. PDF and Word export continue to use the active CV draft, so restore the intended version before exporting it.
