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
        "/api/v1/library/papers",
        "/api/v1/library/papers/{paper_id}/progress",
        "/api/v1/library/papers/{paper_id}/annotations",
        "/api/v1/library/papers/{paper_id}/annotations/{annotation_id}",
        "/api/v1/library/papers/{paper_id}/pdf",
        "/api/v1/library/upload",
        "/api/v1/library/collections",
        "/api/v1/library/collections/{collection_id}",
        "/api/v1/library/collections/{collection_id}/papers/{paper_id}",
        "/api/v1/library/tags",
        "/api/v1/library/tags/{tag_id}",
        "/api/v1/library/tags/{tag_id}/papers/{paper_id}",
        "/api/v1/documents/{document_id}",
        "/api/v1/documents/{document_id}/status",
        "/api/v1/documents/{document_id}/pages",
        "/api/v1/documents/{document_id}/retry",
        "/api/v1/conversations",
        "/api/v1/conversations/{conversation_id}",
        "/api/v1/conversations/{conversation_id}/messages",
        "/api/v1/ai/usage",
        "/api/v1/analysis",
        "/api/v1/analysis/{paper_id}",
        "/api/v1/analysis/compare",
        "/api/v1/analysis/comparisons",
        "/api/v1/analysis/comparisons/{comparison_id}",
        "/api/v1/citations",
        "/api/v1/citations/{citation_id}",
        "/api/v1/citations/import",
        "/api/v1/citations/export",
        "/api/v1/citations/format",
        "/api/v1/writing",
        "/api/v1/writing/{doc_id}",
        "/api/v1/writing/{doc_id}/versions",
        "/api/v1/writing/{doc_id}/versions/{version_id}/restore",
        "/api/v1/writing/{doc_id}/assist",
        "/api/v1/writing/{doc_id}/export",
        "/api/v1/multimodal/documents/{document_id}/extract",
        "/api/v1/multimodal/documents/{document_id}/assets",
        "/api/v1/multimodal/assets/{asset_id}",
        "/api/v1/multimodal/assets/{asset_id}/image",
        "/api/v1/multimodal/assets/{asset_id}/explain",
        "/api/v1/multimodal/assets/{asset_id}/vqa",
        "/api/v1/projects",
        "/api/v1/projects/{project_id}",
        "/api/v1/projects/{project_id}/papers",
        "/api/v1/projects/{project_id}/papers/{user_paper_id}",
        "/api/v1/projects/{project_id}/notes",
        "/api/v1/projects/{project_id}/notes/{note_id}",
        "/api/v1/projects/{project_id}/tasks",
        "/api/v1/projects/{project_id}/tasks/{task_id}",
        "/api/v1/projects/{project_id}/conversations/{conversation_id}",
        "/api/v1/projects/{project_id}/export",
        "/api/v1/analytics/overview",
        "/api/v1/analytics/timeline",
        "/api/v1/analytics/knowledge-graph",
        "/api/v1/education/guides",
        "/api/v1/education/guides/{slug}",
        "/api/v1/education/guides/{slug}/progress",
        "/api/v1/education/glossary",
        "/api/v1/education/explain-paper/{user_paper_id}",
        "/api/v1/teams",
        "/api/v1/teams/{workspace_id}",
        "/api/v1/teams/{workspace_id}/members",
        "/api/v1/teams/{workspace_id}/members/{member_user_id}",
        "/api/v1/teams/{workspace_id}/collections",
        "/api/v1/teams/{workspace_id}/collections/{collection_id}",
        "/api/v1/teams/{workspace_id}/notes",
        "/api/v1/teams/{workspace_id}/notes/{note_id}",
    }
    oauth_flow = schema["components"]["securitySchemes"]["OAuth2PasswordBearer"][
        "flows"
    ]
    assert oauth_flow["password"]["tokenUrl"] == "/api/v1/auth/login"
    for path, operations in schema["paths"].items():
        if path.startswith(
            (
                "/api/v1/papers",
                "/api/v1/library",
                "/api/v1/documents",
                "/api/v1/projects",
                "/api/v1/analytics",
                "/api/v1/education",
                "/api/v1/teams",
            )
        ):
            for operation in operations.values():
                assert operation["security"] == [{"OAuth2PasswordBearer": []}]
    assert schema["paths"]["/api/v1/discovery/save-to-library"]["post"]["security"] == [
        {"OAuth2PasswordBearer": []}
    ]
