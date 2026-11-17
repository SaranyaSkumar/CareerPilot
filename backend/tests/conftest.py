import os

import pytest

from app.auth import reset_jwks_client
from tests.jwt_support import SUPABASE_URL, StaticJWKClient, public_jwks


@pytest.fixture(autouse=True)
def supabase_test_verifier(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", SUPABASE_URL)
    monkeypatch.delenv("SUPABASE_JWKS_URL", raising=False)
    reset_jwks_client(StaticJWKClient(public_jwks()))
    yield
    reset_jwks_client(None)


# Importing the app reads nothing from Supabase, but keep the URL present
# before test modules build their clients.
os.environ.setdefault("SUPABASE_URL", SUPABASE_URL)
