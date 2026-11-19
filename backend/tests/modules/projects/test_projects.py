from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.models.assistant import Conversation, Message
from app.models.library import Collection
from app.models.paper import Author, Paper, PaperAuthor, UserPaper
from app.models.projects import ProjectPaper, ProjectTask, ResearchNote, ResearchProject
from app.models.research_paper import ResearchPaper
from app.models.writing import Citation
from tests.modules.ai.test_assistant import authenticate

BASE = "/api/v1/projects"


def paper(db, owner, title="Owner research"):
    legacy = ResearchPaper(owner_id=owner, title=title, authors="Ada Lovelace")
    db.add(legacy)
    db.flush()
    item = UserPaper(user_id=owner, legacy_paper_id=legacy.id)
    db.add(item)
    db.commit()
    return item


def project(client, title="Study", **values):
    response = client.post(BASE, json={"title": title, **values})
    assert response.status_code == 201, response.text
    return response.json()


def test_project_crud_filters_revision_and_input(client, test_user, access_token):
    authenticate(client, access_token)
    created = project(
        client, description="Study design", objectives=["Compare methods"]
    )
    assert created["status"] == "planning"
    assert created["progress_percent"] == 0 and created["revision"] == 1
    assert created["papers"] == created["notes"] == created["tasks"] == []
    assert client.get(BASE).json()[0]["id"] == created["id"]
    assert client.get(BASE + "?status=active").json() == []
    path = f"{BASE}/{created['id']}"
    updated = client.put(
        path, json={"title": "Renamed", "status": "active", "expected_revision": 1}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "Renamed" and updated.json()["revision"] == 2
    stale = client.put(path, json={"title": "Stale", "expected_revision": 1})
    assert stale.status_code == 409
    assert client.get(path).json()["title"] == "Renamed"
    assert client.get(path).headers["cache-control"] == "private, no-store"
    for body in ({"title": None}, {"status": None}, {"objectives": None}):
        assert client.put(path, json=body).status_code == 422
    for body in (
        {"title": ""},
        {"title": "X", "user_id": test_user.id},
        {"title": "X", "progress_percent": 100},
        {"title": "X", "status": "unknown"},
    ):
        assert client.post(BASE, json=body).status_code == 422
    assert client.get(BASE + "?limit=0").status_code == 422
    deleted = client.delete(path)
    assert deleted.status_code == 204
    assert deleted.headers["cache-control"] == "private, no-store"
    assert client.get(path).status_code == 404


def test_tasks_progress_completion_reopening_and_milestones(client, access_token):
    authenticate(client, access_token)
    item = project(client, status="active")
    path = f"{BASE}/{item['id']}"
    first = client.post(path + "/tasks", json={"title": "Read", "is_milestone": True})
    second = client.post(path + "/tasks", json={"title": "Write", "status": "done"})
    assert first.status_code == second.status_code == 201
    assert first.json()["completed_at"] is None
    assert second.json()["completed_at"] is not None
    detail = client.get(path).json()
    assert detail["progress_percent"] == 50 and detail["task_count"] == 2
    assert detail["completed_task_count"] == 1
    tpath = f"{path}/tasks/{first.json()['id']}"
    done = client.put(tpath, json={"status": "done"})
    assert done.status_code == 200 and done.json()["completed_at"] is not None
    assert client.get(path).json()["progress_percent"] == 100
    assert client.get(path).json()["status"] == "completed"
    reopened = client.put(
        tpath, json={"status": "in_progress", "description": "Review"}
    )
    assert reopened.json()["completed_at"] is None
    assert client.get(path).json()["status"] == "active"
    assert len(client.get(path + "/tasks").json()) == 2
    client.put(path, json={"status": "archived"})
    client.put(tpath, json={"status": "done"})
    assert client.get(path).json()["status"] == "archived"
    deleted = client.delete(tpath)
    assert deleted.status_code == 204
    assert deleted.headers["cache-control"] == "private, no-store"
    assert client.delete(f"{path}/tasks/{second.json()['id']}").status_code == 204
    assert client.get(path).json()["progress_percent"] == 0


def test_papers_notes_links_and_cascade(client, db, test_user, access_token):
    saved = paper(db, test_user.id)
    collection = Collection(user_id=test_user.id, name="Methods")
    db.add(collection)
    db.commit()
    authenticate(client, access_token)
    item = project(client, collection_id=collection.id)
    path = f"{BASE}/{item['id']}"
    link = client.post(
        path + "/papers",
        json={"user_paper_id": saved.id, "role_in_project": "methodology"},
    )
    assert link.status_code == 201, link.text
    assert link.json()["title"] == "Owner research"
    assert (
        client.post(path + "/papers", json={"user_paper_id": saved.id}).status_code
        == 201
    )
    assert client.get(path).json()["paper_count"] == 1
    removed = client.delete(f"{path}/papers/{saved.id}")
    assert removed.status_code == 204
    assert removed.headers["cache-control"] == "private, no-store"
    assert client.delete(f"{path}/papers/{saved.id}").status_code == 404
    assert (
        client.post(path + "/papers", json={"user_paper_id": saved.id}).status_code
        == 201
    )
    note = client.post(
        path + "/notes",
        json={"title": "Finding", "content": "Evidence", "user_paper_id": saved.id},
    )
    assert note.status_code == 201, note.text
    npath = f"{path}/notes/{note.json()['id']}"
    assert (
        client.put(npath, json={"content": "Reviewed"}).json()["content"] == "Reviewed"
    )
    assert len(client.get(path + "/notes").json()) == 1
    db.execute(delete(Collection).where(Collection.id == collection.id))
    db.commit()
    assert client.get(path).json()["collection_id"] is None
    db.execute(delete(UserPaper).where(UserPaper.id == saved.id))
    db.commit()
    detail = client.get(path).json()
    assert detail["papers"] == [] and detail["notes"][0]["user_paper_id"] is None
    deleted = client.delete(npath)
    assert deleted.status_code == 204
    assert deleted.headers["cache-control"] == "private, no-store"
    client.post(path + "/tasks", json={"title": "Work"})
    client.post(path + "/notes", json={"title": "Keep"})
    assert client.delete(path).status_code == 204
    assert (
        db.scalar(select(ResearchNote).where(ResearchNote.project_id == item["id"]))
        is None
    )
    assert (
        db.scalar(select(ProjectTask).where(ProjectTask.project_id == item["id"]))
        is None
    )


def test_export_owned_content_bibliography_and_conversation_link(
    client,
    db,
    test_user,
    another_user,
    access_token,
):
    saved = paper(db, test_user.id)
    other = paper(db, another_user.id, "Secret other paper")
    canonical = Paper(title="Owner research", doi="10.1234/project-export")
    db.add(canonical)
    db.flush()
    saved.paper_id = canonical.id
    db.get(ResearchPaper, saved.legacy_paper_id).url = "https://example.org/owned.pdf"
    conversation = Conversation(
        user_id=test_user.id,
        title="Planning dialogue",
        scope_type="single_paper",
        scope_paper_ids=[saved.id],
    )
    db.add(conversation)
    db.flush()
    db.add(
        Message(
            user_id=test_user.id,
            conversation_id=conversation.id,
            request_id=str(uuid4()),
            role="assistant",
            content="Owner discussion",
        )
    )
    db.add_all(
        [
            Citation(
                user_id=test_user.id,
                user_paper_id=saved.id,
                cite_key="Ada2025",
                identity_key="a" * 64,
                title_year_key="b" * 64,
                title="Owner research",
                authors=["Ada Lovelace"],
                year=2025,
                venue="Methods",
                is_verified=True,
            ),
            Citation(
                user_id=another_user.id,
                user_paper_id=other.id,
                cite_key="Secret2025",
                identity_key="c" * 64,
                title_year_key="d" * 64,
                title="Secret other paper",
                authors=["Other Author"],
                year=2025,
                venue="Private",
            ),
        ]
    )
    db.commit()
    authenticate(client, access_token)
    item = project(
        client,
        objectives=["Compare models"],
        description="Protocol",
        target_deadline="2027-01-30T12:00:00Z",
    )
    path = f"{BASE}/{item['id']}"
    client.post(path + "/papers", json={"user_paper_id": saved.id})
    client.post(
        path + "/notes", json={"title": "Findings", "content": "My private note"}
    )
    task = client.post(
        path + "/tasks",
        json={
            "title": "Synthesize",
            "is_milestone": True,
            "status": "done",
            "due_date": "2027-01-20T09:30:00Z",
        },
    ).json()
    link = client.post(f"{path}/conversations/{conversation.id}")
    assert link.status_code == 200, link.text
    assert len(client.get(path).json()["conversations"]) == 1
    response = client.get(path + "/export")
    assert response.status_code == 200, response.text
    bundle = response.json()
    assert bundle["objectives"] == ["Compare models"]
    assert bundle["notes"][0]["content"] == "My private note"
    assert "2025" in bundle["bibliography"]["bibliography"][0]
    assert bundle["conversation_summaries"][0]["summary"] == "Owner discussion"
    assert "Secret" not in response.text
    markdown = client.get(path + "/export?format=markdown&citation_style=ieee")
    assert markdown.status_code == 200
    assert markdown.headers["content-type"].startswith("text/markdown")
    assert markdown.headers["cache-control"] == "private, no-store"
    assert "# Study" in markdown.text and "My private note" in markdown.text
    assert "[1]" in markdown.text and "Synthesize" in markdown.text
    assert "Target deadline: 2027-01-30T12:00:00" in markdown.text
    assert "Due: 2027-01-20T09:30:00" in markdown.text
    assert f"Completed: {task['completed_at']}" in markdown.text
    assert "Authors: Ada Lovelace" in markdown.text
    assert "DOI: 10.1234/project-export" in markdown.text
    assert "URL: https://example.org/owned.pdf" in markdown.text
    assert "Reading status: unread" in markdown.text
    assert "Owner discussion" in markdown.text and "Secret" not in markdown.text
    assert client.delete(path).status_code == 204
    db.expire_all()
    assert db.get(Conversation, conversation.id).project_id is None


@pytest.mark.parametrize(
    "method,suffix,body",
    [
        ("get", "", None),
        ("put", "", {"title": "Stolen"}),
        ("delete", "", None),
        ("get", "/notes", None),
        ("post", "/notes", {"title": "Stolen"}),
        ("get", "/tasks", None),
        ("post", "/tasks", {"title": "Stolen"}),
        ("post", "/papers", {"user_paper_id": 1}),
        ("delete", "/papers/1", None),
        ("put", "/notes/1", {"content": "Stolen"}),
        ("delete", "/notes/1", None),
        ("put", "/tasks/1", {"status": "done"}),
        ("delete", "/tasks/1", None),
        ("post", "/conversations/1", None),
        ("get", "/export", None),
        ("get", "/export?format=markdown", None),
    ],
)
def test_all_project_resources_deny_other_owner(
    client,
    db,
    another_user,
    access_token,
    method,
    suffix,
    body,
):
    foreign = ResearchProject(user_id=another_user.id, title="Secret project")
    db.add(foreign)
    db.commit()
    authenticate(client, access_token)
    response = client.request(method, f"{BASE}/{foreign.id}{suffix}", json=body)
    assert response.status_code == 404, response.text
    assert client.get(BASE).json() == []
    db.refresh(foreign)
    assert foreign.title == "Secret project" and foreign.status == "planning"


def test_cross_owner_and_wrong_project_associations_rejected(
    client,
    db,
    test_user,
    another_user,
    access_token,
):
    other_paper = paper(db, another_user.id)
    foreign_collection = Collection(user_id=another_user.id, name="Secret")
    foreign_conversation = Conversation(
        user_id=another_user.id,
        title="Secret",
        scope_type="single_paper",
        scope_paper_ids=[],
    )
    db.add_all([foreign_collection, foreign_conversation])
    db.commit()
    authenticate(client, access_token)
    assert (
        client.post(
            BASE, json={"title": "Bad", "collection_id": foreign_collection.id}
        ).status_code
        == 404
    )
    first, second = project(client), project(client, title="Second")
    path, other_path = f"{BASE}/{first['id']}", f"{BASE}/{second['id']}"
    assert (
        client.put(path, json={"collection_id": foreign_collection.id}).status_code
        == 404
    )
    assert (
        client.post(
            path + "/papers", json={"user_paper_id": other_paper.id}
        ).status_code
        == 404
    )
    assert (
        client.post(
            path + "/notes", json={"title": "Bad", "user_paper_id": other_paper.id}
        ).status_code
        == 404
    )
    assert (
        client.post(f"{path}/conversations/{foreign_conversation.id}").status_code
        == 404
    )
    note = client.post(path + "/notes", json={"title": "Mine"}).json()
    task = client.post(path + "/tasks", json={"title": "Mine"}).json()
    assert (
        client.put(
            f"{path}/notes/{note['id']}", json={"user_paper_id": other_paper.id}
        ).status_code
        == 404
    )
    for kind, row in (("notes", note), ("tasks", task)):
        nested = f"{other_path}/{kind}/{row['id']}"
        assert client.put(nested, json={"title": "Bad"}).status_code == 404
        assert client.delete(nested).status_code == 404


@pytest.mark.parametrize(
    "method,suffix,body",
    [
        ("get", "", None),
        ("post", "", {"title": "Test"}),
        ("get", "/1", None),
        ("put", "/1", {"title": "Test"}),
        ("delete", "/1", None),
        ("post", "/1/papers", {"user_paper_id": 1}),
        ("delete", "/1/papers/1", None),
        ("get", "/1/notes", None),
        ("post", "/1/notes", {"title": "Test"}),
        ("put", "/1/notes/1", {"title": "T"}),
        ("delete", "/1/notes/1", None),
        ("get", "/1/tasks", None),
        ("post", "/1/tasks", {"title": "Test"}),
        ("put", "/1/tasks/1", {"status": "done"}),
        ("delete", "/1/tasks/1", None),
        ("post", "/1/conversations/1", None),
        ("get", "/1/export", None),
    ],
)
def test_project_endpoints_require_authentication(client, method, suffix, body):
    assert client.request(method, BASE + suffix, json=body).status_code == 401


def test_composite_foreign_keys_prevent_cross_owner_links(db, test_user, another_user):
    item = ResearchProject(user_id=test_user.id, title="Owned")
    other_paper = paper(db, another_user.id)
    db.add(item)
    db.commit()
    db.add(
        ProjectPaper(
            user_id=test_user.id, project_id=item.id, user_paper_id=other_paper.id
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(
        ProjectTask(user_id=another_user.id, project_id=item.id, title="Wrong owner")
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_export_fallback_metadata_and_stale_source_summary(
    client,
    db,
    test_user,
    access_token,
):
    from tests.modules.analysis.test_routes import paper as indexed_paper

    saved, document, _ = indexed_paper(db, test_user.id)
    authenticate(client, access_token)
    analyzed = client.post(f"/api/v1/analysis/{saved.id}", json={})
    assert analyzed.status_code == 200, analyzed.text
    item = project(client)
    path = f"{BASE}/{item['id']}"
    client.post(path + "/papers", json={"user_paper_id": saved.id})
    exported = client.get(path + "/export").json()
    assert exported["paper_summaries"][0]["is_stale"] is False
    assert exported["bibliography"]["warnings"]
    assert "Compact classifier" in exported["bibliography"]["bibliography"][0]
    document.version += 1
    db.commit()
    exported = client.get(path + "/export").json()
    assert exported["paper_summaries"][0]["is_stale"] is True
    assert (
        "stale after source changes"
        in client.get(path + "/export?format=markdown").text
    )


def test_null_required_nested_fields_and_invalid_payloads(client, access_token):
    authenticate(client, access_token)
    item = project(client)
    path = f"{BASE}/{item['id']}"
    note = client.post(path + "/notes", json={"title": "Note"}).json()
    task = client.post(path + "/tasks", json={"title": "Task"}).json()
    for values in ({"title": None}, {"content": None}):
        assert client.put(f"{path}/notes/{note['id']}", json=values).status_code == 422
    for values in ({"title": None}, {"status": None}, {"is_milestone": None}):
        assert client.put(f"{path}/tasks/{task['id']}", json=values).status_code == 422
    assert (
        client.post(path + "/notes", json={"title": "Bad", "user_id": 1}).status_code
        == 422
    )
    assert (
        client.post(
            path + "/tasks", json={"title": "Bad", "status": "invalid"}
        ).status_code
        == 422
    )
    assert client.get(path + "/export?citation_style=invalid").status_code == 422


def test_export_bibliography_uses_structured_authors_preserves_surname_comma(
    client,
    db,
    test_user,
    access_token,
):
    structured = paper(db, test_user.id, "Structured authors")
    legacy = paper(db, test_user.id, "Legacy surname comma")
    db.get(ResearchPaper, structured.legacy_paper_id).authors = "Wrong legacy text"
    db.get(ResearchPaper, legacy.legacy_paper_id).authors = "Smith, John"
    canonical = Paper(title="Structured authors")
    db.add(canonical)
    db.flush()
    structured.paper_id = canonical.id
    for position, name in enumerate(["Grace Hopper", "Ada Lovelace"]):
        author = Author(display_name=name, normalized_name=name.casefold())
        db.add(author)
        db.flush()
        db.add(
            PaperAuthor(paper_id=canonical.id, author_id=author.id, position=position)
        )
    db.commit()
    authenticate(client, access_token)
    item = project(client)
    path = f"{BASE}/{item['id']}"
    for saved in (structured, legacy):
        assert (
            client.post(path + "/papers", json={"user_paper_id": saved.id}).status_code
            == 201
        )
    bibliography = client.get(path + "/export").json()["bibliography"]["bibliography"]
    assert bibliography[0].startswith("Hopper, G., & Lovelace, A. (n.d.).")
    assert bibliography[1].startswith("Smith, J. (n.d.).")
    assert "Wrong legacy" not in " ".join(bibliography)
