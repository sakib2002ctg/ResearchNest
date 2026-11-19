import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.database.database import Base

LIBRARY = "/api/v1/library"
LEGACY_PAPERS = "/api/v1/papers/"
PAPERS = f"{LIBRARY}/papers"


@pytest.fixture
def db(tmp_path, monkeypatch):
    # Legacy auth and async library requests must read the same database.
    url = URL.create("sqlite", database=str(tmp_path / "library.sqlite"))
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    monkeypatch.setattr("app.main.settings.DATABASE_URL", str(url))
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


@pytest.fixture
def owners(access_token, another_access_token):
    return tuple(
        {"Authorization": f"Bearer {token}"}
        for token in (access_token, another_access_token)
    )


def add_paper(client, headers, title, **fields):
    created = client.post(
        LEGACY_PAPERS, json={"title": title, **fields}, headers=headers
    )
    assert created.status_code == 200, created.text
    listing = client.get(PAPERS, headers=headers)
    assert listing.status_code == 200, listing.text
    return next(
        item
        for item in listing.json()["items"]
        if item["legacy_paper_id"] == created.json()["id"]
    )


def create_named(client, resource, headers, payload):
    response = client.post(f"{LIBRARY}/{resource}", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize("suffix", ["papers", "collections", "tags"])
def test_library_lists_require_authentication(client, suffix):
    assert client.get(f"{LIBRARY}/{suffix}").status_code == 401


def test_private_library_search_and_pagination(client, owners):
    owner, other = owners
    coastal = add_paper(client, owner, "Coastal Wetlands", authors="Grace Hopper")
    arctic = add_paper(client, owner, "Arctic Wetlands", abstract="Blue carbon")
    add_paper(client, other, "Coastal secrets", authors="Grace Hopper")

    first = client.get(PAPERS, headers=owner, params={"size": 1}).json()
    second = client.get(PAPERS, headers=owner, params={"size": 1, "page": 2}).json()
    assert first == {"items": [arctic], "page": 1, "size": 1, "total": 2, "pages": 2}
    assert second == {"items": [coastal], "page": 2, "size": 1, "total": 2, "pages": 2}
    for query, expected in [("  hopper  ", coastal), ("BLUE CARBON", arctic)]:
        result = client.get(PAPERS, headers=owner, params={"q": query})
        assert result.status_code == 200
        assert result.json()["items"] == [expected]
    assert client.get(PAPERS, headers=owner, params={"q": "%"}).json()["items"] == []
    assert client.get(PAPERS, headers=owner, params={"page": 0}).status_code == 422


@pytest.mark.parametrize(
    ("resource", "extra", "updated", "invalid"),
    [
        (
            "collections",
            {"description": "Reading list"},
            {"description": None},
            {"description": "x" * 2001},
        ),
        ("tags", {"color": "#ff44aa"}, {"color": None}, {"color": "red"}),
    ],
)
def test_named_resource_crud_and_owner_scoped_uniqueness(
    client, owners, resource, extra, updated, invalid
):
    owner, other = owners
    url = f"{LIBRARY}/{resource}"
    record = create_named(client, resource, owner, {"name": " Coastal ", **extra})
    replacement = create_named(client, resource, owner, {"name": "Arctic"})
    other_record = create_named(client, resource, other, {"name": "Coastal"})
    item = f"{url}/{record['id']}"

    assert record["name"] == "Coastal"
    assert client.get(item, headers=owner).json() == record
    assert client.get(url, headers=owner).json() == [replacement, record]
    assert client.get(url, headers=other).json() == [other_record]
    assert client.post(url, headers=owner, json={"name": "Coastal"}).status_code == 409
    assert (
        client.post(url, headers=owner, json={"name": " ", **extra}).status_code == 422
    )
    assert client.patch(item, headers=owner, json=invalid).status_code == 422
    assert client.patch(item, headers=owner, json={"name": None}).status_code == 422
    assert client.patch(item, headers=owner, json={"name": "Arctic"}).status_code == 409

    for method, body in [
        ("GET", {}),
        ("PATCH", {"json": {"name": "Foreign edit"}}),
        ("DELETE", {}),
    ]:
        denied = client.request(method, item, headers=other, **body)
        absent = client.request(method, f"{url}/2000000000", headers=other, **body)
        assert denied.status_code == absent.status_code == 404
        assert denied.json() == absent.json()

    change = client.patch(item, headers=owner, json={"name": "New name", **updated})
    assert change.status_code == 200, change.text
    assert change.json()["name"] == "New name"
    assert {field: change.json()[field] for field in updated} == updated
    assert client.delete(item, headers=owner).status_code == 204
    assert client.get(item, headers=owner).status_code == 404
    assert client.get(url, headers=other).json() == [other_record]


def test_collection_and_tag_membership_filters_require_both_resources_owned(
    client, owners
):
    owner, other = owners
    first = add_paper(client, owner, "Coastal")["id"]
    second = add_paper(client, owner, "Arctic")["id"]
    foreign = add_paper(client, other, "Private")["id"]
    collection_id = create_named(client, "collections", owner, {"name": "Saved"})["id"]
    tag_id = create_named(client, "tags", owner, {"name": "Ecology"})["id"]
    for resource, resource_id, query_key in [
        ("collections", collection_id, "collection_id"),
        ("tags", tag_id, "tag_id"),
    ]:
        url = f"{LIBRARY}/{resource}/{resource_id}/papers"
        for _ in range(2):
            assert client.put(f"{url}/{first}", headers=owner).status_code == 204
        assert client.put(f"{url}/{foreign}", headers=owner).status_code == 404
        assert client.put(f"{url}/{foreign}", headers=other).status_code == 404
        assert client.delete(f"{url}/{first}", headers=other).status_code == 404
        params = {query_key: resource_id}
        assert client.get(PAPERS, headers=other, params=params).status_code == 404
        matched = client.get(PAPERS, headers=owner, params=params).json()
        assert matched["total"] == 1
        assert matched["items"][0]["id"] == first
        empty = client.get(PAPERS, headers=owner, params={**params, "q": "Arctic"})
        assert empty.json()["total"] == 0

    assert (
        client.put(
            f"{LIBRARY}/tags/{tag_id}/papers/{second}", headers=owner
        ).status_code
        == 204
    )
    matched = client.get(
        PAPERS, headers=owner, params={"collection_id": collection_id, "tag_id": tag_id}
    ).json()
    assert matched["total"] == 1
    assert matched["items"][0]["collection_ids"] == [collection_id]
    assert matched["items"][0]["tag_ids"] == [tag_id]
    path = f"{LIBRARY}/tags/{tag_id}/papers/{first}"
    assert client.delete(path, headers=owner).status_code == 204
    assert client.delete(path, headers=owner).status_code == 204
    assert (
        client.delete(
            f"{LIBRARY}/collections/{collection_id}", headers=owner
        ).status_code
        == 204
    )
    items = client.get(PAPERS, headers=owner).json()["items"]
    assert [
        (record["id"], record["collection_ids"], record["tag_ids"]) for record in items
    ] == [(second, [], [tag_id]), (first, [], [])]


def test_annotations_enforce_both_library_paper_and_owner(client, owners):
    owner, other = owners
    paper_id = add_paper(client, owner, "Reading notes")["id"]
    sibling_id = add_paper(client, owner, "Other notes")["id"]
    base = f"{PAPERS}/{paper_id}/annotations"
    payload = {
        "type": "highlight",
        "content": "A private finding",
        "page_number": 3,
        "color": "#BADA55",
    }
    assert client.get(base, headers=other).status_code == 404
    assert client.post(base, headers=other, json=payload).status_code == 404
    assert (
        client.post(base, headers=owner, json={**payload, "page_number": 0}).status_code
        == 422
    )
    assert (
        client.post(
            base, headers=owner, json={**payload, "type": "comment"}
        ).status_code
        == 422
    )
    created = client.post(base, headers=owner, json=payload)
    assert created.status_code == 201, created.text
    record = created.json()
    item = f"{base}/{record['id']}"
    sibling_path = f"{PAPERS}/{sibling_id}/annotations/{record['id']}"
    for method, body in [
        ("GET", {}),
        ("PATCH", {"json": {"content": "Foreign edit"}}),
        ("DELETE", {}),
    ]:
        denied = client.request(method, item, headers=other, **body)
        sibling = client.request(method, sibling_path, headers=owner, **body)
        assert denied.status_code == sibling.status_code == 404
        assert denied.json() == sibling.json()

    assert client.get(base, headers=owner).json() == [record]
    assert client.get(item, headers=owner).json() == record
    updated = client.patch(
        item,
        headers=owner,
        json={"type": "note", "content": "Updated", "page_number": None, "color": None},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["content"] == "Updated"
    assert updated.json()["page_number"] is None
    assert client.delete(item, headers=owner).status_code == 204
    assert client.get(base, headers=owner).json() == []


def test_reading_progress_validates_input_and_is_owner_scoped(client, owners):
    owner, other = owners
    created = add_paper(client, owner, "Reading state")
    assert (created["reading_status"], created["reading_progress_percent"]) == (
        "unread",
        0,
    )
    url = f"{PAPERS}/{created['id']}/progress"
    payload = {"reading_status": "reading", "reading_progress_percent": 67.25}
    denied = client.patch(url, headers=other, json=payload)
    absent = client.patch(f"{PAPERS}/2000000000/progress", headers=other, json=payload)
    assert denied.status_code == absent.status_code == 404
    assert denied.json() == absent.json()
    for update in [
        {"reading_status": "finished"},
        {"reading_progress_percent": 101},
        {"reading_progress_percent": -1},
        {"user_id": 2},
    ]:
        assert (
            client.patch(url, headers=owner, json={**payload, **update}).status_code
            == 422
        )
    changed = client.patch(url, headers=owner, json=payload)
    assert changed.status_code == 200, changed.text
    assert changed.json() == {"id": created["id"], **payload}
    assert client.get(PAPERS, headers=owner).json()["items"] == [{**created, **payload}]
