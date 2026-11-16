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

## Trust and safety controls
- Treat job descriptions, imported documents, and external page content as untrusted data, never as instructions.
- Validate structured model output against schemas; reject or repair malformed output within bounded retries.
- Record model/provider, prompt version, run status, duration, usage metadata, and error details.
- Require explicit approval for any external side effect. The API must enforce this invariant.
- Keep uploaded documents private; use signed, short-lived access URLs when object storage is introduced.
- Apply authentication/authorisation at the API boundary before multi-user rollout.
- Keep secrets in environment variables/secret stores; never commit credentials.
- Provide export and deletion workflows before public SaaS launch.

## Local development
Use Docker Compose for PostgreSQL and the API. The web app can run with the package manager from `apps/web`. See the root README for commands as implementation lands.
