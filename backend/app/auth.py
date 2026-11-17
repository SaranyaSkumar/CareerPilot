"""Verify Supabase access tokens.

CareerPilot trusts the caller's identity only after it verifies the bearer
token. Supabase Auth on this project signs access tokens with an asymmetric
key (ES256 today; RS256 is also accepted so a later rotation keeps working).
The public keys are published at:

    ${SUPABASE_URL}/auth/v1/.well-known/jwks.json

Verification is local: the API downloads that JSON Web Key Set, checks the
signature, and accepts the token only when the issuer is
`${SUPABASE_URL}/auth/v1`, the audience is `authenticated`, and the `role`
claim is `authenticated`. The user id is the `sub` claim. The legacy shared
JWT secret is not used, and no user id is read from the request body or from
any other header.

`SUPABASE_JWKS_URL` overrides the discovery URL when it is set. The key set is
cached in process for about ten minutes, which matches Supabase's published
cache window. A revoked key can therefore remain trusted until that cache
expires; Supabase's own Data API does not use this cache.
"""

from __future__ import annotations

import os
import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWKClientConnectionError, PyJWKClientError, PyJWTError

_ALLOWED_ALGORITHMS = {"ES256", "RS256"}
_bearer = HTTPBearer(auto_error=False)
_jwks_client: PyJWKClient | None = None


class AuthNotConfigured(Exception):
    """SUPABASE_URL is unset, so tokens cannot be verified."""


class JwksUnavailable(Exception):
    """The signing-key discovery endpoint could not be read."""


class InvalidAccessToken(Exception):
    """The bearer token is missing, expired, or not a Supabase user token."""


def supabase_url() -> str:
    return os.environ.get("SUPABASE_URL", "").strip().rstrip("/")


def resolve_jwks_url() -> str:
    explicit = os.environ.get("SUPABASE_JWKS_URL", "").strip()
    if explicit:
        return explicit
    base = supabase_url()
    if not base:
        return ""
    return f"{base}/auth/v1/.well-known/jwks.json"


def expected_issuer() -> str:
    base = supabase_url()
    if not base:
        raise AuthNotConfigured()
    return f"{base}/auth/v1"


def reset_jwks_client(client: PyJWKClient | None = None) -> None:
    """Replace the cached key client. Tests inject a fixed key set."""

    global _jwks_client
    _jwks_client = client


def get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is not None:
        return _jwks_client
    url = resolve_jwks_url()
    if not url:
        raise AuthNotConfigured()
    _jwks_client = PyJWKClient(url, cache_keys=True, lifespan=600, timeout=5)
    return _jwks_client


def decode_access_token(token: str) -> uuid.UUID:
    if not token or token.count(".") != 2:
        raise InvalidAccessToken()
    try:
        header = jwt.get_unverified_header(token)
    except PyJWTError as exc:
        raise InvalidAccessToken() from exc
    algorithm = header.get("alg")
    if algorithm not in _ALLOWED_ALGORITHMS:
        raise InvalidAccessToken()

    try:
        signing_key = get_jwks_client().get_signing_key_from_jwt(token)
    except AuthNotConfigured:
        raise
    except PyJWKClientConnectionError as exc:
        raise JwksUnavailable() from exc
    except PyJWKClientError as exc:
        message = str(exc)
        if "did not return" in message or "did not contain" in message:
            raise JwksUnavailable() from exc
        raise InvalidAccessToken() from exc
    except PyJWTError as exc:
        raise InvalidAccessToken() from exc

    key_algorithm = getattr(signing_key, "algorithm_name", None)
    if key_algorithm not in _ALLOWED_ALGORITHMS or key_algorithm != algorithm:
        raise InvalidAccessToken()

    try:
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=[algorithm],
            audience="authenticated",
            issuer=expected_issuer(),
            leeway=10,
            options={"require": ["exp", "sub", "iss", "aud"]},
        )
    except AuthNotConfigured:
        raise
    except PyJWTError as exc:
        raise InvalidAccessToken() from exc

    if payload.get("role") != "authenticated":
        raise InvalidAccessToken()
    try:
        return uuid.UUID(str(payload.get("sub")))
    except (TypeError, ValueError) as exc:
        raise InvalidAccessToken() from exc


def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> uuid.UUID:
    """Return the user id from a verified Supabase access token.

    Missing or invalid credentials are 401. A server that cannot verify tokens
    (no project URL, or the key set cannot be fetched) fails closed with 503.
    """

    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials.strip():
        raise HTTPException(
            status_code=401,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return decode_access_token(credentials.credentials.strip())
    except AuthNotConfigured as exc:
        raise HTTPException(status_code=503, detail="Authentication is not configured.") from exc
    except JwksUnavailable as exc:
        raise HTTPException(status_code=503, detail="Authentication keys are unavailable.") from exc
    except InvalidAccessToken as exc:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
