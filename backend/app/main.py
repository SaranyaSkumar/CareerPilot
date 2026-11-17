from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import get_current_user_id
from app.profile import router as profile_router
from app.cv import router as cv_router
from app.cv_analysis import router as cv_analysis_router
from app.cv_ai import router as cv_ai_router
from app.jobs import router as jobs_router

app = FastAPI(
    title="CareerPilot API",
    version="0.6.0",
    description=(
        "API for the CareerPilot career workspace. "
        "Every /api/v1 route requires a Supabase access token. "
        "The database schema is owned by Alembic migrations and is not created at startup."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "PUT", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(profile_router)
app.include_router(cv_router)
app.include_router(cv_analysis_router)
app.include_router(cv_ai_router)
app.include_router(jobs_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "careerpilot-api"}


@app.get("/api/v1", tags=["system"])
def api_root(_user_id: object = Depends(get_current_user_id)) -> dict[str, str]:
    return {"name": "CareerPilot API", "version": "0.6.0"}
