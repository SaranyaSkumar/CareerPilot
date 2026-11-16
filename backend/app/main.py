from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="CareerPilot API",
    version="0.1.0",
    description="API for the CareerPilot personal career workspace.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "careerpilot-api"}


@app.get("/api/v1", tags=["system"])
def api_root() -> dict[str, str]:
    return {"name": "CareerPilot API", "version": "0.1.0"}
