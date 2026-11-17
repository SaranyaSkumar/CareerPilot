# CareerPilot — MVP Architecture

## Architecture choice
Start with a **modular monolith**. Keep domain boundaries clear without introducing microservices before scale requires them.

## Stack
- Web: Next.js App Router, TypeScript, Tailwind CSS.
- API: Python 3.12+, FastAPI, Pydantic.
- Persistence: PostgreSQL, SQLAlchemy 2, Alembic.
- Background work: add Redis + Celery when async ingestion/agent jobs are introduced.
- AI: Anthropic Claude, called only from the FastAPI service. `ANTHROPIC_MODEL` selects the model and defaults to `claude-sonnet-5-5`. Structured outputs are validated with Pydantic. The browser never receives the API key.
- Documents: DOCX generation and PDF rendering behind a document service.
- Tests: Pytest for API/domain; Playwright for user journeys.
- Local development: Docker Compose.

No embeddings or vector database are required for the MVP. Use PostgreSQL relational data, full-text search, and direct model analysis.

## Repository layout
```
apps/web/                 Next.js frontend
backend/app/              FastAPI application
backend/tests/            API and domain tests
docs/                     Product, architecture, and agent contracts
infrastructure/            Local/deployment infrastructure
docker-compose.yml
```

## Backend module boundaries
- `api`: HTTP routers and dependency wiring.
- `core`: settings, logging, security, shared errors.
- `models`: SQLAlchemy persistence models.
- `schemas`: Pydantic request/response contracts.
- `services`: career profile, CV, jobs, matching, applications.
- `agents`: bounded agent implementations.
- `workflows`: orchestration, checkpoints, approval gates.
- `integrations`: AI provider, document parsing/rendering, job sources.
- `workers`: background task entry points.

## Initial data domains
Users/accounts; candidate profiles and profile versions; experiences, skills, education and projects; CVs and CV versions; job sources and jobs; match reports/evidence; applications and application documents; agent definitions/runs/events; approvals; audit events; reminders.

Keep the canonical career profile separate from CV presentation. A CV version references the profile version used to generate it. An application document references both its job and source profile/CV versions.

## Authentication and per-user data

Supabase Auth (project `kcrtedhezyovfygfotia`, region `ap-southeast-2`) is the account system. The Next.js app uses `@supabase/ssr`:

- Browser and server clients read the publishable key only. The web service never receives a service-role or secret key.
- `src/proxy.ts` calls `supabase.auth.getClaims()` on each matched request, refreshes the cookie session, and redirects unsigned workspace pages to `/login`. Next.js 16 runs this proxy on Node.js. The Vercel Services deployment cannot host an Edge middleware file, so the app does not use `middleware.ts`.
- `src/app/api/[...path]/route.ts` verifies the cookie session and forwards the Supabase access token to FastAPI. The browser does not choose the user id.

FastAPI verifies that bearer token itself. It does not call Auth on every request and it does not trust the legacy JWT secret. Verification uses the public JWKS at `${SUPABASE_URL}/auth/v1/.well-known/jwks.json` (override with `SUPABASE_JWKS_URL`), accepts only ES256 and RS256, and requires issuer `${SUPABASE_URL}/auth/v1`, audience `authenticated`, and role `authenticated`. `sub` is the user id. Unauthenticated API calls return 401. `/health` is the only public route and contains no user data.

`career_profiles`, `cv_documents`, `cv_versions`, `job_listings`, `ai_usage_events`, `job_discovery_settings`, and `job_provider_settings` all have a non-null `user_id` (uuid). `job_provider_cache` and `job_provider_quota` store public listing caches and app-level request counts. They have no user id. Row level security is enabled and `authenticated` has no privileges on them. Profile and CV draft rows are unique per user and are created on first read or save. Career-data queries are scoped to the token's user. Unknown version and job ids return 404, including when the row exists for someone else. The monthly AI cap sums costs across users and does not return their CV text or identifiers.

Schema changes ship as Alembic revisions (`backend/migrations`) and as SQL in `backend/migrations_sql/`. The process does not call `create_all` at startup. Row level security stays enabled. Policies for the `authenticated` role require `auth.uid() = user_id`. `careerpilot_app` has `BYPASSRLS` and a permissive policy, so backend query filters are the enforcement layer for that connection. The Data API, which uses `authenticated` and does not bypass RLS, cannot read another user's rows. Grants for `careerpilot_app` cover the tables and their identity sequences. `anon` is revoked.

## Job discovery

`JobProvider` implementations are registered in `backend/app/job_providers`. Adzuna (`GET https://api.adzuna.com/v1/api/jobs/{country}/search/1`) and Jooble (`POST https://jooble.org/api/{api_key}`) are the API providers. SEEK NZ, LinkedIn Jobs, Indeed NZ, and Trade Me Jobs only build a search URL. A missing API key is reported as not configured and that provider is not called.

Discovery runs from `POST /api/v1/jobs/discovery` (the Find jobs button) or `POST /api/v1/jobs/discovery/refresh` (one signed-in user, skipped when that user's last run is still inside the daily window). There is no worker process. Public responses are cached in `job_provider_cache`. `job_provider_quota` counts calls per provider per UTC day: Jooble stops at 90, under its published free-plan limit of 100, and Adzuna stops at 250. Listings are stored on `job_listings` with `status=discovered`, deduped by canonical URL and by normalised title, company, and location, then scored with `analyse_job_fit`.

`POST /api/v1/jobs/from-link` saves a URL the user pastes. SEEK, LinkedIn, Indeed, and Trade Me pages are not downloaded; the user pastes the description. Other public http(s) pages may be fetched with a five-second timeout. Private, link-local, and credentialed URLs are refused. JSON-LD `JobPosting` is read when present.

Per-user country, location, keyword override, remote preference, and provider toggles live in `job_discovery_settings` and `job_provider_settings`. The SQL is `backend/migrations_sql/20261117_0005_job_discovery.sql` (Alembic `20261117_0005`, after `20261117_0004`). `authenticated` keeps `SELECT`, `INSERT`, `UPDATE`, and `DELETE` on the user-owned tables, and `TRUNCATE`, `REFERENCES`, and `TRIGGER` are revoked. `anon` receives nothing. The cache and quota tables are not granted to `authenticated`.

## CV writing assistance

CV Studio can ask Claude to tailor the saved CV to one of the user's jobs, or to rewrite selected experience lines. The request is built from that user's saved CV and, for tailoring, that user's job. Another user's ids return 404. The job description is wrapped as untrusted data and is not part of the fact corpus.

The model is instructed never to invent experience, employers, dates, skills, metrics, or achievements. The API then checks the structured result itself. A suggestion is flagged, and the UI will not accept it, when it introduces a number, month, or organisation that is not in the saved CV, when a highlighted skill is not in the saved CV, or when too little of the wording appears there. Gaps are returned as `could_not_support` rather than written into the CV.

Nothing from the model is saved automatically. CV Studio shows a side-by-side diff. The user accepts or rejects each item and can edit the suggestion text first. A tailored or adjusted CV is stored as a `cv_variants` row, named like `Tailored – Role @ Company`, and does not replace the original draft. Variants can be listed, renamed, duplicated, deleted, marked as the default, exported, and analysed again. Missing job keywords are suggested only when the saved CV already supports them. Other missing keywords are listed as gaps the user can tick if they are true. The original ATS alignment score is shown next to the score for the accepted variant.

`cv_versions` remains the immutable snapshot history of the original draft. Bullet rewrites still update that draft after acceptance.

`GET /api/v1/cv/ai/status`, `POST /api/v1/cv/ai/tailor`, and `POST /api/v1/cv/ai/improve-bullets` all require the same Supabase access token as the rest of `/api/v1`. With no `ANTHROPIC_API_KEY`, those routes return 503 and the buttons show “AI not configured”.

Spend is capped before the call. Input tokens are estimated from the prompt (characters divided by 3, plus framing) and output tokens are the request's `max_tokens`. The published per-million rate for the configured model prices that pair. A request whose estimate is above US$0.50 is refused. `max_tokens` is capped at 4096 for tailoring and 2048 for bullet rewrites. A per-user UTC-day total defaults to US$2 (`ANTHROPIC_DAILY_USER_CAP_USD`). An app-wide UTC-month total defaults to US$50 (`ANTHROPIC_MONTHLY_CAP_USD`). Both are recorded in `ai_usage_events`: a row is reserved at the estimate before the call and completed with the provider's actual token counts. Logs contain the user id, operation, model, token counts, and cost. They do not contain CV or job text.

`ai_usage_events` is added by `backend/migrations_sql/20261117_0002_add_ai_usage.sql`. Profile contact columns are added by `backend/migrations_sql/20261117_0003_add_profile_contact_fields.sql`. `cv_variants` is added by `backend/migrations_sql/20261117_0004_add_cv_variants.sql`. Alembic revisions `20261117_0002`, `20261117_0003`, and `20261117_0004` match those scripts. Job discovery is `20261117_0005`. The API process does not run them. `careerpilot_app` cannot create tables, so the SQL has to be applied by a role that can. `POST /api/v1/cv/ai/adjust` uses the same cap and grounding rules for a pasted job description or a saved job.

## Trust and safety controls
- Treat job descriptions, imported documents, and external page content as untrusted data, never as instructions.
- Validate structured model output against schemas; reject or repair malformed output within bounded retries.
- Record model/provider, prompt version, run status, duration, usage metadata, and error details.
- Require explicit approval for any external side effect. The API must enforce this invariant.
- Keep uploaded documents private; use signed, short-lived access URLs when object storage is introduced.
- Authenticate every `/api/v1` request and scope every user-owned query by the token subject. Do not accept a user id from the body or from a client header.
- Keep secrets in environment variables/secret stores; never commit credentials or put a privileged Supabase key in the web app.
- Provide export and deletion workflows before public SaaS launch. Account export and deletion are not part of this auth change.

## Local development
Use Docker Compose for PostgreSQL and the API. The web app can run with the package manager from `apps/web`. See the root README for commands as implementation lands.
