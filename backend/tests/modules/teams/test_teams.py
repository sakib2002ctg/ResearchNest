import json

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.models.audit_log import AuditLog
from app.models.library import Annotation, Collection, CollectionPaper, Document
from app.models.paper import UserPaper
from app.models.research_paper import ResearchPaper
from app.models.teams import TeamMember, TeamNote, TeamSharedCollection, TeamWorkspace
from app.models.user import User
from tests.conftest import issue_test_session

BASE = "/api/v1/teams"
ACTIONS = [
    ("GET", "", None),
    ("POST", "", {"name": "Workspace"}),
    ("GET", "/1", None),
    ("PUT", "/1", {"name": "Updated"}),
    ("DELETE", "/1", None),
    ("POST", "/1/members", {"identifier": "account", "role": "viewer"}),
    ("PUT", "/1/members/2", {"role": "viewer"}),
    ("DELETE", "/1/members/2", None),
    ("POST", "/1/collections", {"collection_id": 1}),
    ("DELETE", "/1/collections/1", None),
    ("GET", "/1/notes", None),
    ("POST", "/1/notes", {"title": "Observation", "content": "Shared"}),
    ("PUT", "/1/notes/1", {"title": "Edited"}),
    ("DELETE", "/1/notes/1", None),
]


@pytest.fixture
def accounts(db):
    result = {}
    for name in ["owner", "editor", "viewer", "outsider"]:
        user = User(
            username=f"team-{name}",
            email=f"{name}@teams.example.com",
            hashed_password="test",
        )
        db.add(user)
        db.commit()
        result[name] = dict(
            id=user.id,
            username=user.username,
            email=user.email,
            token=issue_test_session(db, user),
        )
    db.rollback()
    return result


def request(client, accounts, role, method, path, body=None):
    client.headers["Authorization"] = f"Bearer {accounts[role]['token']}"
    return (
        client.request(method, BASE + path, json=body)
        if body is not None
        else client.request(method, BASE + path)
    )


@pytest.fixture
def workspace(client, accounts):
    response = request(
        client,
        accounts,
        "owner",
        "POST",
        "",
        {"name": "Research team", "description": "Workspace shared description"},
    )
    assert response.status_code == 201, response.text
    wid = response.json()["id"]
    for role in ["editor", "viewer"]:
        response = request(
            client,
            accounts,
            "owner",
            "POST",
            f"/{wid}/members",
            {"identifier": accounts[role]["email"], "role": role},
        )
        assert response.status_code == 201, response.text
    return wid


def collection(db, owner, suffix="own"):
    legacy = ResearchPaper(
        owner_id=owner,
        title=f"Shared paper {suffix}",
        authors="Recorded Author",
        source="arxiv",
        url="https://example.com/paper",
    )
    db.add(legacy)
    db.flush()
    saved = UserPaper(
        user_id=owner, legacy_paper_id=legacy.id, note="PRIVATE LIBRARY NOTE"
    )
    folder = Collection(
        user_id=owner,
        name=f"Sources {suffix}",
        description="Explicitly shared collection",
    )
    db.add_all([saved, folder])
    db.flush()
    db.add_all(
        [
            CollectionPaper(
                user_id=owner, collection_id=folder.id, user_paper_id=saved.id
            ),
            Annotation(
                user_id=owner,
                user_paper_id=saved.id,
                type="note",
                content="PRIVATE ANNOTATION",
            ),
            Document(
                user_id=owner,
                user_paper_id=saved.id,
                storage_key=f"{suffix}.pdf",
                original_filename="PRIVATE_FILENAME.pdf",
                size_bytes=10,
                sha256="a" * 64,
                page_count=1,
            ),
        ]
    )
    db.commit()
    ids = folder.id, saved.id
    db.rollback()
    return ids


@pytest.mark.parametrize("method,path,body", ACTIONS)
def test_every_endpoint_requires_a_live_session(client, method, path, body):
    response = client.request(method, BASE + path, json=body)
    assert response.status_code == 401


def test_workspace_crud_roles_membership_and_safe_member_metadata(
    client, db, accounts, workspace
):
    wid = workspace
    owner = request(client, accounts, "owner", "GET", f"/{wid}")
    assert owner.status_code == 200, owner.text
    assert owner.headers["cache-control"] == "private, no-store"
    assert owner.json()["my_role"] == "owner"
    assert {row["role"] for row in owner.json()["members"]} == {
        "owner",
        "editor",
        "viewer",
    }
    assert (
        "@teams.example.com" not in owner.text and "hashed_password" not in owner.text
    )
    assert request(client, accounts, "outsider", "GET", "").json() == []
    assert request(client, accounts, "outsider", "GET", f"/{wid}").status_code == 404
    assert (
        request(
            client, accounts, "outsider", "PUT", f"/{wid}", {"name": "Stolen"}
        ).status_code
        == 404
    )
    edited = request(
        client,
        accounts,
        "editor",
        "PUT",
        f"/{wid}",
        {"description": "Editor can maintain workspace"},
    )
    assert edited.status_code == 200 and edited.json()["my_role"] == "editor"
    assert (
        request(client, accounts, "viewer", "GET", f"/{wid}").json()["description"]
        == "Editor can maintain workspace"
    )
    assert (
        request(
            client, accounts, "viewer", "PUT", f"/{wid}", {"name": "Denied"}
        ).status_code
        == 403
    )
    assert request(client, accounts, "editor", "DELETE", f"/{wid}").status_code == 403
    assert (
        request(client, accounts, "owner", "PUT", f"/{wid}", {"name": None}).status_code
        == 422
    )
    assert (
        request(
            client,
            accounts,
            "owner",
            "POST",
            "",
            {"name": " ", "owner_id": accounts["outsider"]["id"]},
        ).status_code
        == 422
    )
    assert (
        len(request(client, accounts, "viewer", "GET", "?limit=1&offset=0").json()) == 1
    )
    assert request(client, accounts, "viewer", "GET", "?offset=1").json() == []


@pytest.mark.parametrize(
    "method,suffix,body", [item for item in ACTIONS if item[1] and item[0] != "GET"]
)
def test_viewer_cannot_mutate_any_workspace_resource(
    client, accounts, workspace, method, suffix, body
):
    path = suffix.replace("/1", f"/{workspace}", 1)
    response = request(client, accounts, "viewer", method, path, body)
    assert response.status_code == 403, response.text


@pytest.mark.parametrize("method,suffix,body", [item for item in ACTIONS if item[1]])
def test_nonmember_cannot_read_or_modify_workspace_resources(
    client, accounts, workspace, method, suffix, body
):
    path = suffix.replace("/1", f"/{workspace}", 1)
    response = request(client, accounts, "outsider", method, path, body)
    assert response.status_code == 404, response.text


def test_only_immutable_owner_controls_members_and_audits_are_safe(
    client, db, accounts, workspace
):
    wid = workspace
    owner_id, editor_id = accounts["owner"]["id"], accounts["editor"]["id"]
    for role in ["editor", "viewer"]:
        assert (
            request(
                client,
                accounts,
                role,
                "POST",
                f"/{wid}/members",
                {"identifier": accounts["outsider"]["email"]},
            ).status_code
            == 403
        )
        assert (
            request(
                client,
                accounts,
                role,
                "PUT",
                f"/{wid}/members/{editor_id}",
                {"role": "viewer"},
            ).status_code
            == 403
        )
        assert (
            request(
                client, accounts, role, "DELETE", f"/{wid}/members/{editor_id}"
            ).status_code
            == 403
        )
    assert (
        request(
            client,
            accounts,
            "owner",
            "PUT",
            f"/{wid}/members/{owner_id}",
            {"role": "viewer"},
        ).status_code
        == 409
    )
    assert (
        request(
            client, accounts, "owner", "DELETE", f"/{wid}/members/{owner_id}"
        ).status_code
        == 409
    )
    assert (
        request(
            client,
            accounts,
            "owner",
            "POST",
            f"/{wid}/members",
            {"identifier": "no-such-user"},
        ).status_code
        == 404
    )
    assert (
        request(
            client,
            accounts,
            "owner",
            "POST",
            f"/{wid}/members",
            {"identifier": accounts["viewer"]["email"]},
        ).status_code
        == 409
    )
    assert (
        request(
            client,
            accounts,
            "owner",
            "POST",
            f"/{wid}/members",
            {"identifier": accounts["outsider"]["email"], "role": "owner"},
        ).status_code
        == 422
    )
    added = request(
        client,
        accounts,
        "owner",
        "POST",
        f"/{wid}/members",
        {"identifier": accounts["outsider"]["username"], "role": "editor"},
    )
    assert added.status_code == 201
    assert (
        request(
            client,
            accounts,
            "owner",
            "PUT",
            f"/{wid}/members/{editor_id}",
            {"role": "viewer"},
        ).status_code
        == 200
    )
    removed = request(
        client, accounts, "owner", "DELETE", f"/{wid}/members/{editor_id}"
    )
    assert (
        removed.status_code == 204
        and removed.headers["cache-control"] == "private, no-store"
    )
    assert request(client, accounts, "editor", "GET", f"/{wid}").status_code == 404
    db.expire_all()
    logs = list(db.scalars(select(AuditLog).where(AuditLog.resource_id == str(wid))))
    assert {row.action for row in logs} >= {
        "team.workspace.created",
        "team.member.added",
        "team.member.role_changed",
        "team.member.removed",
    }
    safe = json.dumps([row.details for row in logs])
    assert "@" not in safe and "token" not in safe and "Shared" not in safe


def test_shared_collections_are_explicit_metadata_only_and_never_expand_private_apis(
    client, db, accounts, workspace
):
    wid = workspace
    cid, pid = collection(db, accounts["editor"]["id"])
    private_cid, private_pid = collection(db, accounts["editor"]["id"], "unshared")
    assert (
        request(
            client,
            accounts,
            "owner",
            "POST",
            f"/{wid}/collections",
            {"collection_id": cid},
        ).status_code
        == 404
    )
    response = request(
        client,
        accounts,
        "editor",
        "POST",
        f"/{wid}/collections",
        {"collection_id": cid},
    )
    assert response.status_code == 201, response.text
    assert (
        request(
            client,
            accounts,
            "editor",
            "POST",
            f"/{wid}/collections",
            {"collection_id": cid},
        ).json()["id"]
        == response.json()["id"]
    )
    viewer = request(client, accounts, "viewer", "GET", f"/{wid}")
    assert viewer.status_code == 200
    shared = viewer.json()["collections"][0]
    assert shared["papers"][0]["user_paper_id"] == pid
    assert set(shared["papers"][0]) == {
        "user_paper_id",
        "title",
        "authors",
        "source",
        "url",
        "doi",
    }
    for secret in [
        "PRIVATE LIBRARY NOTE",
        "PRIVATE ANNOTATION",
        "PRIVATE_FILENAME",
        "storage_key",
        "sha256",
        "unshared",
    ]:
        assert secret not in viewer.text
    assert (
        request(client, accounts, "viewer", "GET", f"/{wid}/notes").status_code == 200
    )
    client.headers["Authorization"] = f"Bearer {accounts['viewer']['token']}"
    assert client.get(f"/api/v1/library/collections/{cid}").status_code == 404
    assert client.get(f"/api/v1/library/papers/{pid}/pdf").status_code == 404
    assert (
        client.patch(
            f"/api/v1/library/papers/{pid}/progress",
            json={"reading_status": "completed", "reading_progress_percent": 100},
        ).status_code
        == 404
    )
    assert client.get("/api/v1/library/papers").json()["items"] == []
    assert (
        request(
            client,
            accounts,
            "editor",
            "POST",
            f"/{wid}/notes",
            {"title": "Not shared", "user_paper_id": private_pid},
        ).status_code
        == 404
    )
    assert (
        request(
            client,
            accounts,
            "owner",
            "POST",
            f"/{wid}/notes",
            {"title": "Shared source", "user_paper_id": pid},
        ).status_code
        == 201
    )
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(TeamSharedCollection)) == 1
    assert private_cid != cid


def test_collaborative_notes_and_revocation_mask_private_paper_links(
    client, db, accounts, workspace
):
    wid = workspace
    cid, pid = collection(db, accounts["editor"]["id"])
    assert (
        request(
            client,
            accounts,
            "editor",
            "POST",
            f"/{wid}/collections",
            {"collection_id": cid},
        ).status_code
        == 201
    )
    response = request(
        client,
        accounts,
        "editor",
        "POST",
        f"/{wid}/notes",
        {
            "title": "Team observation",
            "content": "Intentionally shared note",
            "user_paper_id": pid,
        },
    )
    assert response.status_code == 201, response.text
    nid = response.json()["id"]
    assert response.json()["author_id"] == accounts["editor"]["id"]
    assert (
        request(
            client,
            accounts,
            "owner",
            "PUT",
            f"/{wid}/notes/{nid}",
            {"content": "Collaborative revision"},
        ).status_code
        == 200
    )
    assert (
        request(client, accounts, "viewer", "GET", f"/{wid}/notes").json()[0]["content"]
        == "Collaborative revision"
    )
    assert (
        request(
            client, accounts, "owner", "PUT", f"/{wid}/notes/{nid}", {"content": None}
        ).status_code
        == 422
    )
    other = request(
        client, accounts, "owner", "POST", "", {"name": "Other workspace"}
    ).json()["id"]
    assert (
        request(
            client,
            accounts,
            "owner",
            "PUT",
            f"/{other}/notes/{nid}",
            {"title": "Wrong workspace"},
        ).status_code
        == 404
    )
    assert (
        request(
            client, accounts, "owner", "DELETE", f"/{other}/notes/{nid}"
        ).status_code
        == 404
    )
    assert (
        request(
            client, accounts, "owner", "GET", f"/{wid}/notes?limit=1&offset=1"
        ).json()
        == []
    )
    removed = request(
        client,
        accounts,
        "owner",
        "DELETE",
        f"/{wid}/members/{accounts['editor']['id']}",
    )
    assert removed.status_code == 204
    data = request(client, accounts, "viewer", "GET", f"/{wid}").json()
    assert data["collections"] == []
    assert data["notes"][0]["user_paper_id"] is None
    assert data["notes"][0]["content"] == "Collaborative revision"
    assert (
        request(client, accounts, "editor", "GET", f"/{wid}/notes").status_code == 404
    )
    assert (
        request(
            client,
            accounts,
            "editor",
            "PUT",
            f"/{wid}/notes/{nid}",
            {"content": "Denied"},
        ).status_code
        == 404
    )
    deleted = request(client, accounts, "owner", "DELETE", f"/{wid}/notes/{nid}")
    assert (
        deleted.status_code == 204
        and deleted.headers["cache-control"] == "private, no-store"
    )


def test_editor_demotion_and_unshare_revoke_grants_preserving_original_library(
    client, db, accounts, workspace
):
    wid = workspace
    cid, pid = collection(db, accounts["editor"]["id"])
    own_cid, _ = collection(db, accounts["owner"]["id"], "owner")
    assert (
        request(
            client,
            accounts,
            "editor",
            "POST",
            f"/{wid}/collections",
            {"collection_id": cid},
        ).status_code
        == 201
    )
    assert (
        request(
            client,
            accounts,
            "owner",
            "POST",
            f"/{wid}/collections",
            {"collection_id": own_cid},
        ).status_code
        == 201
    )
    assert (
        request(
            client, accounts, "editor", "DELETE", f"/{wid}/collections/{own_cid}"
        ).status_code
        == 403
    )
    unshare = request(client, accounts, "owner", "DELETE", f"/{wid}/collections/{cid}")
    assert (
        unshare.status_code == 204
        and unshare.headers["x-content-type-options"] == "nosniff"
    )
    assert (
        request(
            client,
            accounts,
            "editor",
            "POST",
            f"/{wid}/collections",
            {"collection_id": cid},
        ).status_code
        == 201
    )
    assert (
        request(
            client,
            accounts,
            "owner",
            "PUT",
            f"/{wid}/members/{accounts['editor']['id']}",
            {"role": "viewer"},
        ).status_code
        == 200
    )
    detail = request(client, accounts, "viewer", "GET", f"/{wid}").json()
    assert [item["collection_id"] for item in detail["collections"]] == [own_cid]
    assert (
        request(
            client,
            accounts,
            "editor",
            "POST",
            f"/{wid}/collections",
            {"collection_id": cid},
        ).status_code
        == 403
    )
    deleted = request(client, accounts, "owner", "DELETE", f"/{wid}")
    assert (
        deleted.status_code == 204
        and deleted.headers["cache-control"] == "private, no-store"
    )
    db.expire_all()
    assert db.get(Collection, cid) is not None and db.get(UserPaper, pid) is not None
    assert db.scalar(select(func.count()).select_from(TeamSharedCollection)) == 0
    assert db.scalar(select(func.count()).select_from(TeamMember)) == 0
    assert db.scalar(select(func.count()).select_from(TeamWorkspace)) == 0
    logs = list(db.scalars(select(AuditLog.action)))
    assert "team.collection.shared" in logs and "team.collection.unshared" in logs


def test_database_owner_and_library_association_constraints(db, accounts):
    owner, other = accounts["owner"]["id"], accounts["editor"]["id"]
    workspace = TeamWorkspace(owner_id=owner, name="Database constraints")
    db.add(workspace)
    db.commit()
    wid = workspace.id
    db.add(
        TeamMember(workspace_id=wid, user_id=other, role="owner", owner_user_id=other)
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(TeamMember(workspace_id=wid, user_id=owner, role="owner"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add_all(
        [
            TeamMember(
                workspace_id=wid, user_id=owner, role="owner", owner_user_id=owner
            ),
            TeamMember(workspace_id=wid, user_id=other, role="editor"),
        ]
    )
    db.commit()
    cid, pid = collection(db, owner)
    db.add(
        TeamSharedCollection(workspace_id=wid, shared_by_id=other, collection_id=cid)
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(
        TeamNote(
            workspace_id=wid,
            author_id=other,
            user_paper_id=2147483647,
            title="Missing source",
            content="",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    note = TeamNote(
        workspace_id=wid,
        author_id=owner,
        user_paper_id=pid,
        title="Preserved",
        content="Explicit team content",
    )
    db.add(note)
    db.commit()
    nid = note.id
    db.execute(delete(UserPaper).where(UserPaper.id == pid, UserPaper.user_id == owner))
    db.commit()
    db.expire_all()
    assert db.get(TeamNote, nid).user_paper_id is None


def test_editors_can_discuss_other_owners_explicitly_shared_papers_only(
    client, db, accounts, workspace
):
    wid = workspace
    owner = accounts["owner"]["id"]
    first_collection, first = collection(db, owner, "shared-first")
    second_collection, second = collection(db, owner, "shared-second")
    private_collection, private = collection(db, owner, "private-source")
    other_collection, other_paper = collection(db, owner, "other-workspace")
    for cid in (first_collection, second_collection):
        assert (
            request(
                client,
                accounts,
                "owner",
                "POST",
                f"/{wid}/collections",
                {"collection_id": cid},
            ).status_code
            == 201
        )

    created = request(
        client,
        accounts,
        "editor",
        "POST",
        f"/{wid}/notes",
        {
            "title": "Collaborative reading",
            "content": "Explicit team observation",
            "user_paper_id": first,
        },
    )
    assert created.status_code == 201, created.text
    note_id = created.json()["id"]
    assert created.json()["author_id"] == accounts["editor"]["id"]
    assert created.json()["user_paper_id"] == first
    # Attribution remains the author; another workspace writer may change its
    # source association only to a paper covered by the same live sharing ACL.
    changed = request(
        client,
        accounts,
        "owner",
        "PUT",
        f"/{wid}/notes/{note_id}",
        {"user_paper_id": second},
    )
    assert changed.status_code == 200
    assert changed.json()["author_id"] == accounts["editor"]["id"]
    assert changed.json()["user_paper_id"] == second

    other_wid = request(
        client, accounts, "owner", "POST", "", {"name": "Separate team"}
    ).json()["id"]
    assert (
        request(
            client,
            accounts,
            "owner",
            "POST",
            f"/{other_wid}/members",
            {"identifier": accounts["editor"]["username"], "role": "editor"},
        ).status_code
        == 201
    )
    assert (
        request(
            client,
            accounts,
            "owner",
            "POST",
            f"/{other_wid}/collections",
            {"collection_id": other_collection},
        ).status_code
        == 201
    )
    for inaccessible in (private, other_paper):
        assert (
            request(
                client,
                accounts,
                "editor",
                "POST",
                f"/{wid}/notes",
                {"title": "Unauthorized link", "user_paper_id": inaccessible},
            ).status_code
            == 404
        )
        assert (
            request(
                client,
                accounts,
                "editor",
                "PUT",
                f"/{wid}/notes/{note_id}",
                {"user_paper_id": inaccessible},
            ).status_code
            == 404
        )
    assert private_collection != other_collection
    viewer = request(client, accounts, "viewer", "GET", f"/{wid}/notes")
    assert viewer.json()[0]["user_paper_id"] == second

    # The explicit note ACL does not grant private library/PDF/RAG access.
    client.headers["Authorization"] = f"Bearer {accounts['editor']['token']}"
    assert client.get(f"/api/v1/library/papers/{first}/pdf").status_code == 404
    assert (
        client.post(
            "/api/v1/conversations",
            json={"scope_type": "single_paper", "scope_paper_ids": [first]},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/education/explain-paper/{first}",
            json={"provider": "offline"},
        ).status_code
        == 404
    )

    assert (
        request(
            client,
            accounts,
            "owner",
            "DELETE",
            f"/{wid}/collections/{second_collection}",
        ).status_code
        == 204
    )
    masked = request(client, accounts, "viewer", "GET", f"/{wid}/notes").json()[0]
    assert masked["user_paper_id"] is None
    assert masked["content"] == "Explicit team observation"
    assert (
        request(
            client,
            accounts,
            "editor",
            "PUT",
            f"/{wid}/notes/{note_id}",
            {"user_paper_id": second},
        ).status_code
        == 404
    )
