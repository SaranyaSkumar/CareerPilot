from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app import models  # noqa: F401 - register ORM models before create_all
from app.profile import router as profile_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Lightweight local-MVP bootstrap. Replace with Alembic migrations before production.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="CareerPilot API",
    version="0.2.0",
    description="API for the CareerPilot personal career workspace.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "PUT", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.include_router(profile_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "careerpilot-api"}


@app.get("/api/v1", tags=["system"])
def api_root() -> dict[str, str]:
    return {"name": "CareerPilot API", "version": "0.2.0"}
