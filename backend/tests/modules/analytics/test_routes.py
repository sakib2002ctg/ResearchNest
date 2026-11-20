from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.time import utc_now
from app.models.document_intelligence import Embedding
from app.models.library import PaperTag, Tag
from app.models.paper import Author, Paper, PaperAuthor, PaperSource, UserPaper
from app.models.projects import ProjectPaper, ProjectTask, ResearchProject
from app.models.research_paper import ResearchPaper
from app.models.writing import Citation
from app.modules.analytics import repository, service
from tests.modules.ai.test_assistant import authenticate, indexed_paper

BASE = "/api/v1/analytics"


def saved(db, owner, title="Plant biology", year=None, authors=None, doi=None):
    canonical = Paper(
        title=title,
        doi=doi,
        publication_date=date(year, 1, 1) if year else None,
    )
    db.add(canonical)
    db.flush()
    for position, name in enumerate(authors or []):
        author = Author(display_name=name, normalized_name=name.casefold())
        db.add(author)
        db.flush()
        db.add(
            PaperAuthor(paper_id=canonical.id, author_id=author.id, position=position)
        )
    legacy = ResearchPaper(owner_id=owner, title=title, source="arxiv")
    db.add(legacy)
    db.flush()
    item = UserPaper(user_id=owner, paper_id=canonical.id, legacy_paper_id=legacy.id)
    db.add(item)
    db.commit()
    return item, canonical


def project(db, owner, *papers, title="Owned workspace"):
    result = ResearchProject(user_id=owner, title=title, objectives=[])
    db.add(result)
    db.flush()
    for item in papers:
        db.add(ProjectPaper(user_id=owner, project_id=result.id, user_paper_id=item.id))
    db.commit()
    return result


def reference(db, owner, paper, *, year=2018, verified=True):
    key = uuid4().hex
    result = Citation(
        user_id=owner,
        user_paper_id=paper.id,
        cite_key=f"item{key}",
        identity_key=key,
        title_year_key=key,
        entry_type="article",
        title="Recorded reference",
        authors=["Reference Author"],
        year=year,
        venue="Nature",
        is_verified=verified,
    )
    db.add(result)
    db.commit()
    return result


@pytest.mark.parametrize("route", ["overview", "timeline", "knowledge-graph"])
def test_authentication_required(client, route):
    assert client.get(f"{BASE}/{route}").status_code == 401


def test_empty_library_overview_and_graph(client, access_token):
    authenticate(client, access_token)
    response = client.get(f"{BASE}/overview")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["totals"] == dict(
        saved_papers=0, indexed_papers=0, analyzed_papers=0, projects=0
    )
    assert data["publication_years"] == []
    assert data["unknown_publication_year_count"] == 0
    assert data["coverage"]["indexed_percent"] == 0
    assert response.headers["cache-control"] == "private, no-store"
    graph = client.get(f"{BASE}/knowledge-graph").json()
    assert graph["nodes"] == [] and graph["edges"] == []
    assert graph["truncated"] is False


def test_overview_real_years_authors_tags_and_user_isolation(
    client, db, test_user, another_user, access_token
):
    first, canonical = saved(db, test_user.id, year=2021, authors=["Ada", "Lin"])
    second, _ = saved(db, test_user.id, title="Plant ecology", authors=["Ada"])
    unknown, _ = saved(db, test_user.id, title="Marine ecology")
    unknown.reading_status = "completed"
    first.reading_status = "reading"
    reference(db, test_user.id, second)
    reference(db, test_user.id, unknown, year=1999, verified=False)
    secret, _ = saved(
        db, another_user.id, title="Classified work", year=2000, authors=["Hidden"]
    )
    tag = Tag(user_id=test_user.id, name="Plants", color="#123456")
    secret_tag = Tag(user_id=another_user.id, name="Secret", color="#111111")
    db.add_all([tag, secret_tag])
    db.flush()
    db.add_all(
        [
            PaperTag(user_id=test_user.id, user_paper_id=first.id, tag_id=tag.id),
            PaperTag(
                user_id=another_user.id, user_paper_id=secret.id, tag_id=secret_tag.id
            ),
            PaperSource(
                paper_id=canonical.id,
                provider="openalex",
                external_id="W1",
                metadata_json={"venue": "Journal of Plants"},
            ),
        ]
    )
    db.commit()
    authenticate(client, access_token)
    response = client.get(f"{BASE}/overview")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["totals"]["saved_papers"] == 3
    assert data["publication_years"] == [
        {"year": 2018, "count": 1, "provenance": "verified_citation"},
        {"year": 2021, "count": 1, "provenance": "provider_metadata"},
    ]
    assert data["unknown_publication_year_count"] == 1
    assert data["reading_funnel"] == [
        {"status": "unread", "count": 1},
        {"status": "reading", "count": 1},
        {"status": "completed", "count": 1},
    ]
    assert data["authors"] == [{"name": "Ada", "count": 2}, {"name": "Lin", "count": 1}]
    assert data["coauthors"] == [{"source": "Ada", "target": "Lin", "count": 1}]
    assert {v["name"] for v in data["venues"]} == {"Nature", "Journal of Plants"}
    assert data["tags"] == [
        {"id": tag.id, "name": "Plants", "color": "#123456", "count": 1}
    ]
    assert all(t["origin"] == "inferred_similarity" for t in data["topics"])
    assert "Hidden" not in response.text and "Secret" not in response.text


@pytest.mark.parametrize("route", ["overview", "timeline", "knowledge-graph"])
def test_foreign_and_missing_project_404_even_without_owned_papers(
    client, db, another_user, access_token, route
):
    foreign = project(db, another_user.id, title="Confidential")
    authenticate(client, access_token)
    for project_id in (foreign.id, 999999):
        response = client.get(f"{BASE}/{route}?project_id={project_id}")
        assert response.status_code == 404
        assert "Confidential" not in response.text


def test_project_filter_counts_graph_and_empty_project(
    client, db, test_user, access_token
):
    first, _ = saved(db, test_user.id, title="Scoped first", year=2020)
    saved(db, test_user.id, title="Outside project", year=2010)
    owned = project(db, test_user.id, first)
    empty = project(db, test_user.id, title="Empty project")
    authenticate(client, access_token)
    data = client.get(f"{BASE}/overview?project_id={owned.id}").json()
    assert data["totals"]["saved_papers"] == 1 and data["totals"]["projects"] == 1
    graph_response = client.get(f"{BASE}/knowledge-graph?project_id={owned.id}")
    assert (
        "Outside project" not in graph_response.text
        and "Empty project" not in graph_response.text
    )
    assert any(e["type"] == "project_contains" for e in graph_response.json()["edges"])
    assert (
        client.get(f"{BASE}/overview?project_id={empty.id}").json()["totals"][
            "saved_papers"
        ]
        == 0
    )


def test_graph_provenance_actual_citations_and_no_cross_tenant_nodes(
    client, db, test_user, another_user, access_token
):
    first, canonical = saved(
        db, test_user.id, "Plant ecology", authors=["Ada"], doi="10.1234/a"
    )
    second, _ = saved(db, test_user.id, "Plant evolution", doi="10.1234/b")
    _, foreign = saved(db, another_user.id, "Classified secret", doi="10.1234/private")
    db.add(
        PaperSource(
            paper_id=canonical.id,
            provider="semantic_scholar",
            external_id="first",
            metadata_json={
                "citation_links": [
                    {"doi": "https://doi.org/10.1234/b"},
                    {"doi": foreign.doi},
                    {"title": "Plant evolution"},
                    "bad",
                ]
            },
        )
    )
    tag = Tag(user_id=test_user.id, name="Ecology")
    db.add(tag)
    db.flush()
    db.add(PaperTag(user_id=test_user.id, user_paper_id=first.id, tag_id=tag.id))
    db.commit()
    authenticate(client, access_token)
    response = client.get(f"{BASE}/knowledge-graph")
    assert response.status_code == 200, response.text
    data = response.json()
    assert "Classified" not in response.text
    assert {n["type"] for n in data["nodes"]} >= {"paper", "author", "topic", "tag"}
    for item in [*data["nodes"], *data["edges"]]:
        assert item["origin"] in {"verified_metadata", "inferred_similarity"}
        assert item["provenance"]
    citations = [e for e in data["edges"] if e["type"] == "cites_or_related"]
    assert len(citations) == 1
    assert citations[0]["source"] == f"paper:{first.id}"
    assert citations[0]["target"] == f"paper:{second.id}"
    assert citations[0]["provenance"] == "provider_citation:semantic_scholar"
    assert all(
        e["origin"] == "inferred_similarity"
        for e in data["edges"]
        if e["type"] == "shared_topic_inferred"
    )
    tag_node = next(n for n in data["nodes"] if n["type"] == "tag")
    assert tag_node["provenance"] == "user_record"
    assert data == client.get(f"{BASE}/knowledge-graph").json()


def test_saved_dates_never_become_publication_years_or_read_events(
    client, db, test_user, access_token
):
    item, _ = saved(db, test_user.id)
    item.saved_at = utc_now() - timedelta(days=100)
    item.reading_status = "completed"
    owned = project(db, test_user.id, item)
    completed = utc_now() - timedelta(hours=1)
    db.add(
        ProjectTask(
            user_id=test_user.id,
            project_id=owned.id,
            title="Real completed task",
            status="done",
            completed_at=completed,
        )
    )
    db.commit()
    authenticate(client, access_token)
    overview = client.get(f"{BASE}/overview").json()
    assert overview["publication_years"] == []
    data = client.get(f"{BASE}/timeline").json()
    assert {e["type"] for e in data["items"]} == {
        "paper_saved",
        "project_created",
        "task_created",
        "task_completed",
    }
    assert all(e["provenance"] == "user_record" for e in data["items"])
    event = next(e for e in data["items"] if e["type"] == "task_completed")
    assert event["occurred_at"].startswith(completed.isoformat()[:19])
    one = client.get(f"{BASE}/timeline?limit=1").json()
    assert len(one["items"]) == 1 and one["truncated"] is True


def test_timeline_does_not_leak_foreign_events(client, db, another_user, access_token):
    item, _ = saved(db, another_user.id, "Private saved paper")
    owned = project(db, another_user.id, item, title="Secret project")
    db.add(
        ProjectTask(user_id=another_user.id, project_id=owned.id, title="Secret task")
    )
    db.commit()
    authenticate(client, access_token)
    response = client.get(f"{BASE}/timeline")
    assert response.json()["items"] == []
    assert "Secret" not in response.text and "Private saved" not in response.text


def test_coverage_requires_current_embedding_and_fresh_completed_analysis(
    client, db, test_user, access_token
):
    item, document, chunk = indexed_paper(db, test_user.id)
    authenticate(client, access_token)
    result = client.post(f"/api/v1/analysis/{item.id}", json={"provider": "offline"})
    assert result.status_code == 200, result.text
    data = client.get(f"{BASE}/overview").json()
    assert data["coverage"] == {
        "saved": 1,
        "indexed": 1,
        "analyzed": 1,
        "indexed_percent": 100.0,
        "analyzed_percent": 100.0,
        "analysis_freshness": {
            "checked_papers": 1,
            "unchecked_papers": 0,
            "truncated": False,
            "paper_limit": 100,
            "chunk_limit": 20000,
            "chunk_rows_budgeted": 1,
        },
    }
    # Even without a version bump, changed text invalidates the stored fingerprint.
    chunk.content = "Changed text means the existing analysis is stale."
    db.commit()
    assert client.get(f"{BASE}/overview").json()["coverage"]["analyzed"] == 0
    db.expire_all()
    embedding = db.scalar(select(Embedding).where(Embedding.chunk_id == chunk.id))
    embedding.document_version = 2
    db.commit()
    coverage = client.get(f"{BASE}/overview").json()["coverage"]
    assert coverage["indexed"] == 0 and coverage["analyzed"] == 0


def test_graph_limits_report_truncation_without_dangling_edges(monkeypatch):
    rows = [
        (
            SimpleNamespace(id=i),
            SimpleNamespace(title=f"Biology ecology {i}", authors="Ada; Lin"),
            None,
        )
        for i in range(1, 20)
    ]
    data = repository.LibrarySnapshot(rows, 50, None)
    monkeypatch.setattr(service, "MAX_NODES", 22)
    monkeypatch.setattr(service, "MAX_EDGES", 4)
    graph = service.build_graph(data)
    assert graph["truncated"] is True
    assert len(graph["nodes"]) == 22 and len(graph["edges"]) == 4
    nodes = {n["id"] for n in graph["nodes"]}
    assert all(e["source"] in nodes and e["target"] in nodes for e in graph["edges"])


def test_metadata_and_graph_query_caps_are_explicit(
    client, db, test_user, access_token, monkeypatch
):
    saved(db, test_user.id, "Older paper")
    saved(db, test_user.id, "Newest paper")
    monkeypatch.setattr(repository, "GRAPH_PAPER_LIMIT", 1)
    authenticate(client, access_token)
    graph = client.get(f"{BASE}/knowledge-graph").json()
    assert graph["scope"] == {
        "project_id": None,
        "total_papers": 2,
        "included_papers": 1,
        "truncated": True,
    }
    assert graph["limits"]["papers"] == 1
    assert graph["truncated"] is True


@pytest.mark.parametrize(
    "query",
    [
        "project_id=0",
        "project_id=-1",
        "project_id=hello",
        "project_id=2147483648",
        "limit=0",
        "limit=201",
    ],
)
def test_invalid_timeline_query_rejected(client, access_token, query):
    authenticate(client, access_token)
    assert client.get(f"{BASE}/timeline?{query}").status_code == 422


def test_keyword_heuristic_and_legacy_author_provenance():
    assert service.terms("A Study of Plant Biology using Data") == ["biology", "plant"]
    snapshot = repository.LibrarySnapshot([], 0, None)
    saved_row = SimpleNamespace(id=1)
    names, provenance = service.author_names(
        snapshot, saved_row, SimpleNamespace(authors="Smith, J.; Li")
    )
    assert names == ["Smith, J.", "Li"] and provenance == "user_record"


def test_malformed_dois_and_source_metadata_never_create_citation_edges():
    rows = [
        (
            SimpleNamespace(id=i),
            SimpleNamespace(title="Ecology", authors=None),
            SimpleNamespace(title="Ecology", doi="not-a-doi"),
        )
        for i in (1, 2)
    ]
    snapshot = repository.LibrarySnapshot(rows, 2, None)
    snapshot.sources[1] = [
        SimpleNamespace(metadata_json=["malformed"]),
        SimpleNamespace(metadata_json={"citation_links": "not-a-list"}),
        SimpleNamespace(metadata_json={"citation_links": [{"doi": "also-invalid"}]}),
    ]
    graph = service.build_graph(snapshot)
    assert not any(edge["type"] == "cites_or_related" for edge in graph["edges"])


def test_project_totals_and_truncation_are_explicit(
    client, db, test_user, access_token, monkeypatch
):
    project(db, test_user.id, title="First")
    project(db, test_user.id, title="Second")
    monkeypatch.setattr(repository, "PROJECT_LIMIT", 1)
    authenticate(client, access_token)
    expected = {"total_projects": 2, "included_projects": 1, "truncated": True}
    overview = client.get(f"{BASE}/overview").json()
    assert overview["totals"]["projects"] == 2
    assert overview["project_scope"] == expected
    graph = client.get(f"{BASE}/knowledge-graph").json()
    assert graph["project_scope"] == expected
    assert graph["truncated"] is True
    assert len(graph["nodes"]) == 1


def test_analysis_freshness_paper_and_chunk_budgets_report_lower_bound(
    client, db, test_user, access_token, monkeypatch
):
    from sqlalchemy import func

    from app.models.assistant import AIUsage

    authenticate(client, access_token)
    for index in range(2):
        item, _, _ = indexed_paper(db, test_user.id, title=f"Indexed {index}")
        result = client.post(
            f"/api/v1/analysis/{item.id}", json={"provider": "offline"}
        )
        assert result.status_code == 200, result.text
    monkeypatch.setattr(repository, "FRESHNESS_PAPER_LIMIT", 1)
    coverage = client.get(f"{BASE}/overview").json()["coverage"]
    assert coverage["indexed"] == 2 and coverage["analyzed"] == 1
    assert coverage["analysis_freshness"]["checked_papers"] == 1
    assert coverage["analysis_freshness"]["unchecked_papers"] == 1
    assert coverage["analysis_freshness"]["truncated"] is True
    monkeypatch.setattr(repository, "FRESHNESS_PAPER_LIMIT", 100)
    monkeypatch.setattr(repository, "FRESHNESS_CHUNK_LIMIT", 0)
    coverage = client.get(f"{BASE}/overview").json()["coverage"]
    assert coverage["indexed"] == 2 and coverage["analyzed"] == 0
    assert coverage["analysis_freshness"]["unchecked_papers"] == 2
    assert coverage["analysis_freshness"]["chunk_rows_budgeted"] == 0
    assert coverage["analysis_freshness"]["truncated"] is True
    db.expire_all()
    # Analytics never reserves usage or invokes any AI provider.
    assert db.scalar(select(func.count()).select_from(AIUsage)) == 2
