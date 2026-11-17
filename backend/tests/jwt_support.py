"""Sign test access tokens with a local ES256 key.

The public key is published through a stand-in JWKS client so API tests exercise
the same verifier the backend uses for Supabase. Nothing here contacts Supabase.
"""

from __future__ import annotations

import json
import time
import uuid

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from jwt import PyJWKClient
from jwt.algorithms import ECAlgorithm

PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
OTHER_PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
KEY_ID = "test-signing-key"
SUPABASE_URL = "https://kcrtedhezyovfygfotia.supabase.co"
ISSUER = f"{SUPABASE_URL}/auth/v1"
DEFAULT_USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_A = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
USER_B = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def public_jwks() -> dict:
    jwk = json.loads(ECAlgorithm(ECAlgorithm.SHA256).to_jwk(PRIVATE_KEY.public_key()))
    jwk.update({"kid": KEY_ID, "alg": "ES256", "use": "sig"})
    return {"keys": [jwk]}


class StaticJWKClient(PyJWKClient):
    def __init__(self, jwks: dict):
        super().__init__("https://example.invalid/auth/v1/.well-known/jwks.json", cache_keys=False)
        self._jwks = jwks

    def fetch_data(self):
        return self._jwks


def make_token(
    user_id: uuid.UUID | str = DEFAULT_USER_ID,
    *,
    private_key=PRIVATE_KEY,
    kid: str = KEY_ID,
    algorithm: str = "ES256",
    audience: str = "authenticated",
    issuer: str = ISSUER,
    role: str | None = "authenticated",
    expires_in: int = 3600,
    include_exp: bool = True,
) -> str:
    now = int(time.time())
    payload: dict = {
        "sub": str(user_id),
        "aud": audience,
        "iss": issuer,
        "iat": now,
    }
    if role is not None:
        payload["role"] = role
    if include_exp:
        payload["exp"] = now + expires_in
    return jwt.encode(payload, private_key, algorithm=algorithm, headers={"kid": kid, "alg": algorithm})


def bearer(user_id: uuid.UUID | str = DEFAULT_USER_ID) -> str:
    return f"Bearer {make_token(user_id)}"
