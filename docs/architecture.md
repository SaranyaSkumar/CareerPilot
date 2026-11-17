# CareerPilot — MVP Architecture

## Architecture choice
Start with a **modular monolith**. Keep domain boundaries clear without introducing microservices before scale requires them.

## Stack
- Web: Next.js App Router, TypeScript, Tailwind CSS.
- API: Python 3.12+, FastAPI, Pydantic.
- Persistence: PostgreSQL, SQLAlchemy 2, Alembic.
- Background work: add Redis + Celery when async ingestion/agent jobs are introduced.
- AI: provider abstraction around OpenAI; structured outputs validated with Pydantic.
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

`career_profiles`, `cv_documents`, `cv_versions`, and `job_listings` all have a non-null `user_id` (uuid). Profile and CV draft rows are unique per user and are created on first read or save. Every query is scoped to the token's user. Unknown version and job ids return 404, including when the row exists for someone else.

Schema changes ship as an Alembic revision (`backend/migrations`) and as `backend/migrations_sql/20261117_0001_add_user_scoping.sql`. The process does not call `create_all` at startup. Row level security stays enabled. Policies for the `authenticated` role require `auth.uid() = user_id`. `careerpilot_app` has `BYPASSRLS` and a permissive policy, so backend query filters are the enforcement layer for that connection. The Data API, which uses `authenticated` and does not bypass RLS, cannot read another user's rows. Grants for `careerpilot_app` cover the tables and their identity sequences. `anon` is revoked.

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
