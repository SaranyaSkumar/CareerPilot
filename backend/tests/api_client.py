from fastapi.testclient import TestClient

from tests.jwt_support import DEFAULT_USER_ID, bearer


class AuthClient(TestClient):
    """Test client that sends a verified Supabase-shaped access token."""

    def __init__(self, app, user_id=DEFAULT_USER_ID, **kwargs):
        super().__init__(app, **kwargs)
        self.user_id = user_id

    def request(self, method, url, **kwargs):
        headers = dict(kwargs.pop("headers", None) or {})
        if not any(name.lower() == "authorization" for name in headers):
            headers["Authorization"] = bearer(self.user_id)
        kwargs["headers"] = headers
        return super().request(method, url, **kwargs)
