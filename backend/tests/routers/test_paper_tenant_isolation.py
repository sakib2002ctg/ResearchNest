import pytest

from app.repositories.paper_repository import PaperRepository
from app.schemas.research_paper import ResearchPaperCreate

pytestmark = pytest.mark.parametrize("api_prefix", ["/api/v1", ""])


@pytest.fixture
def tenant_papers(db, test_user, another_user):
    repository = PaperRepository(db)
    owned, foreign = [], []
    # Interleave rows so pagination must filter by owner before offset/limit.
    for index in range(4):
        foreign.append(
            repository.create_paper(
                ResearchPaperCreate(title=f"Shared topic private B {index}"),
                owner_id=another_user.id,
            )
        )
        if index < 3:
            owned.append(
                repository.create_paper(
                    ResearchPaperCreate(title=f"Shared topic private A {index}"),
                    owner_id=test_user.id,
                )
            )
    return owned, foreign


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/papers/", None),
        ("GET", "/papers/search?q=Shared", None),
        ("GET", "/papers/1", None),
        ("POST", "/papers/", {"title": "Test"}),
        ("PUT", "/papers/1", {"title": "Test"}),
        ("DELETE", "/papers/1", None),
    ],
)
def test_all_paper_endpoints_require_authentication(
    api_prefix, client, method, path, payload
):
    response = client.request(method, f"{api_prefix}{path}", json=payload)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("path", ["/papers/", "/papers/search"])
def test_list_and_search_exclude_other_users_and_their_counts(
    api_prefix, client, access_token, tenant_papers, path
):
    owned, _ = tenant_papers
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"size": 2, "q": "Shared"}
    response = client.get(f"{api_prefix}{path}", headers=headers, params=params)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert data["pages"] == 2
    assert [paper["id"] for paper in data["items"]] == [p.id for p in owned[:2]]

    response = client.get(
        f"{api_prefix}{path}", headers=headers, params={**params, "page": 2}
    )
    assert response.status_code == 200
    assert [paper["id"] for paper in response.json()["items"]] == [owned[2].id]


@pytest.mark.parametrize("field", ["title", "authors", "abstract"])
def test_search_never_returns_foreign_matches(
    api_prefix, client, access_token, db, another_user, field
):
    payload = {"title": "Other user's paper", field: "PrivateNeedle"}
    PaperRepository(db).create_paper(
        ResearchPaperCreate(**payload), owner_id=another_user.id
    )
    response = client.get(
        f"{api_prefix}/papers/search?q=PrivateNeedle",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "page": 1,
        "size": 10,
        "total": 0,
        "pages": 0,
    }


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
def test_foreign_paper_is_not_found_and_remains_unchanged(
    api_prefix, client, access_token, another_access_token, tenant_papers, method
):
    _, foreign = tenant_papers
    paper = foreign[0]
    path = f"{api_prefix}/papers/{paper.id}"
    kwargs = {"json": {"title": "Unauthorized change"}} if method == "PUT" else {}
    response = client.request(
        method, path, headers={"Authorization": f"Bearer {access_token}"}, **kwargs
    )

    assert response.status_code == 404
    assert "title" not in response.json()
    # The rightful owner can still read the original after every denied operation.
    response = client.get(
        path, headers={"Authorization": f"Bearer {another_access_token}"}
    )
    assert response.status_code == 200
    assert response.json()["title"] == paper.title


def test_create_uses_authenticated_owner(
    api_prefix, client, access_token, test_user, another_user, db
):
    response = client.post(
        f"{api_prefix}/papers/",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"title": "My private paper", "owner_id": another_user.id},
    )

    assert response.status_code == 200
    paper_id = response.json()["id"]
    repository = PaperRepository(db)
    assert repository.get_paper_by_id(paper_id, owner_id=test_user.id) is not None
    assert repository.get_paper_by_id(paper_id, owner_id=another_user.id) is None
