import pytest


@pytest.mark.parametrize("path", ["/", "/health", "/about"])
def test_public_information_routes_remain_available(client, path):
    assert client.get(path).status_code == 200


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/greet/example"), ("GET", "/add?a=1&b=2"), ("POST", "/student")],
)
def test_demo_routes_are_removed(client, method, path):
    assert client.request(method, path).status_code == 404


@pytest.mark.parametrize("path", ["/users/", "/api/v1/users/"])
def test_duplicate_registration_is_removed(client, path, user_payload):
    assert client.post(path, json=user_payload).status_code == 404


def test_users_me_requires_authentication(client):
    assert client.get("/api/v1/users/me").status_code == 401


def test_users_me_returns_only_current_user(authenticated_client, test_user):
    response = authenticated_client.get("/api/v1/users/me")

    assert response.status_code == 200
    assert response.json() == {
        "id": test_user.id,
        "username": test_user.username,
        "email": test_user.email,
        "is_verified": False,
    }


def test_openapi_exposes_versioned_routes_and_hides_legacy_aliases(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert set(schema["paths"]) == {
        "/",
        "/health",
        "/about",
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/me",
        "/api/v1/auth/logout",
        "/api/v1/auth/logout-all",
        "/api/v1/auth/verify-email/request",
        "/api/v1/auth/verify-email/confirm",
        "/api/v1/auth/password-reset/request",
        "/api/v1/auth/password-reset/confirm",
        "/api/v1/auth/password-change",
        "/api/v1/users/me",
        "/api/v1/users/me/profile",
        "/api/v1/users/me/preferences",
        "/api/v1/users/me/sessions",
        "/api/v1/users/me/activity",
        "/api/v1/users/me/sessions/{session_id}",
        "/api/v1/users/me/export",
        "/api/v1/users/me/dashboard",
        "/api/v1/papers/",
        "/api/v1/papers/search",
        "/api/v1/papers/{paper_id}",
        "/api/v1/research/search",
        "/api/v1/discovery/search",
        "/api/v1/discovery/doi/{doi}",
        "/api/v1/discovery/save-to-library",
    }
    oauth_flow = schema["components"]["securitySchemes"]["OAuth2PasswordBearer"][
        "flows"
    ]
    assert oauth_flow["password"]["tokenUrl"] == "/api/v1/auth/login"
    for path, operations in schema["paths"].items():
        if path.startswith("/api/v1/papers"):
            for operation in operations.values():
                assert operation["security"] == [{"OAuth2PasswordBearer": []}]
    assert schema["paths"]["/api/v1/discovery/save-to-library"]["post"]["security"] == [
        {"OAuth2PasswordBearer": []}
    ]
