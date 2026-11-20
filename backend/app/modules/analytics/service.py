"""Deterministic projections; no external provider calls or invented citations."""

import hashlib
import re
from collections import Counter, defaultdict
from datetime import UTC
from itertools import combinations

from sqlalchemy import and_, select

from app.models.projects import ProjectTask, ResearchProject
from app.modules.analytics import repository
from app.modules.discovery.gateway import normalize_doi

MAX_NODES = 1000
MAX_EDGES = 3000
STOPWORDS = frozenset(
    "about after also analysis approach based been between data from have into "
    "method methods paper research results study studies than that their these "
    "they this through using used were which with without your title".split()
)


def terms(title):
    """A small, explicitly inferred title-keyword heuristic, never an AI claim."""
    return sorted(
        {
            word.casefold()
            for word in re.findall(r"[^\W\d_]{4,}", title, flags=re.UNICODE)
            if word.casefold() not in STOPWORDS
        }
    )[:12]


def source_metadata(source):
    return source.metadata_json if isinstance(source.metadata_json, dict) else {}


def author_names(snapshot, saved, legacy):
    names = snapshot.authors.get(saved.id)
    if names:
        return names[:30], "provider_metadata"
    # The legacy projection is a user record, not externally verified metadata.
    # Commas can be part of a surname, so only unambiguous separators split it.
    return (
        [
            s.strip()
            for s in re.split(r";|\s+and\s+", legacy.authors or "")
            if s.strip()
        ][:30],
        "user_record",
    )


def ranked(counter, name="name", limit=30):
    return [
        {name: key, "count": value}
        for key, value in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[
            :limit
        ]
    ]


async def overview(db, owner, project_id=None):
    data = await repository.snapshot(db, owner, project_id)
    ids = [saved.id for saved, _, _ in data.rows]
    indexed, analyzed, freshness = await repository.coverage(db, owner, ids)
    years, authors, coauthors, venues, sources, topics, tags = (
        Counter() for _ in range(7)
    )
    funnel = Counter({"unread": 0, "reading": 0, "completed": 0})
    tag_metadata = {}
    for saved, legacy, canonical in data.rows:
        citation = data.citations.get(saved.id)
        if canonical and canonical.publication_date:
            years[(canonical.publication_date.year, "provider_metadata")] += 1
        elif citation and citation.year:
            years[(citation.year, "verified_citation")] += 1
        funnel[saved.reading_status] += 1
        names, _ = author_names(data, saved, legacy)
        authors.update(set(names))
        # At most 30 authors per paper; no unbounded coauthor cross product.
        coauthors.update(combinations(sorted(set(names)), 2))
        if citation and citation.venue:
            venues[(citation.venue, "verified_citation")] += 1
        for source in data.sources.get(saved.id, []):
            metadata = source_metadata(source)
            venue = metadata.get("venue")
            if not (citation and citation.venue) and isinstance(venue, str) and venue:
                venues[(venue[:500], "provider_metadata")] += 1
                break
        paper_sources = {s.provider for s in data.sources.get(saved.id, [])}
        if not paper_sources and legacy.source:
            paper_sources.add(legacy.source)
        sources.update(paper_sources)
        topics.update(terms(canonical.title if canonical else legacy.title))
        for tag in data.tags.get(saved.id, []):
            tags[tag.id] += 1
            tag_metadata[tag.id] = {"id": tag.id, "name": tag.name, "color": tag.color}
    count = len(data.rows)
    return {
        "totals": {
            "saved_papers": count,
            "indexed_papers": len(indexed),
            "analyzed_papers": len(analyzed),
            "projects": data.project_total,
        },
        "publication_years": [
            {"year": year, "count": value, "provenance": provenance}
            for (year, provenance), value in sorted(years.items())
        ],
        "unknown_publication_year_count": count - sum(years.values()),
        "reading_funnel": [
            {"status": status, "count": funnel[status]}
            for status in ("unread", "reading", "completed")
        ],
        "authors": ranked(authors),
        "coauthors": [
            {"source": a, "target": b, "count": value}
            for (a, b), value in sorted(
                coauthors.items(), key=lambda pair: (-pair[1], pair[0])
            )[:30]
        ],
        "venues": [
            {"name": name, "count": value, "provenance": provenance}
            for (name, provenance), value in sorted(
                venues.items(), key=lambda pair: (-pair[1], pair[0])
            )[:30]
        ],
        "sources": ranked(sources),
        "topics": [
            {**item, "origin": "inferred_similarity"} for item in ranked(topics)
        ],
        "tags": [
            {**tag_metadata[item["id"]], "count": item["count"]}
            for item in ranked(tags, "id")
        ],
        "coverage": {
            "saved": count,
            "indexed": len(indexed),
            "analyzed": len(analyzed),
            "indexed_percent": round(len(indexed) * 100 / count, 2) if count else 0,
            "analyzed_percent": round(len(analyzed) * 100 / count, 2) if count else 0,
            "analysis_freshness": freshness,
        },
        "scope": data.scope,
        "project_scope": data.project_scope,
        "metadata_limit": repository.OVERVIEW_PAPER_LIMIT,
        "notes": [
            "All metrics describe included owner-scoped papers; "
            "scope reports truncation.",
            "Publication years are known metadata, never dates inferred from saving.",
            "Topics are inferred title keywords; coauthors are metadata co-occurrence.",
            "Analyzed requires a completed, current-source-fingerprint analysis "
            "and live index.",
            "When analysis_freshness is truncated, analyzed is a verified lower bound.",
        ],
    }


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


async def timeline(db, owner, project_id=None, limit=100):
    await repository.require_project(db, owner, project_id)
    rows = (
        await db.execute(
            repository.paper_query(owner, project_id)
            .order_by(
                repository.UserPaper.saved_at.desc(), repository.UserPaper.id.desc()
            )
            .limit(limit + 1)
        )
    ).all()
    events = [
        {
            "id": f"saved:{saved.id}",
            "type": "paper_saved",
            "title": legacy.title,
            "occurred_at": utc(saved.saved_at),
            "user_paper_id": saved.id,
            "project_id": project_id,
            "provenance": "user_record",
        }
        for saved, legacy, _ in rows
    ]
    projects_query = select(ResearchProject).where(ResearchProject.user_id == owner)
    tasks_query = (
        select(ProjectTask)
        .join(
            ResearchProject,
            and_(
                ResearchProject.id == ProjectTask.project_id,
                ResearchProject.user_id == owner,
            ),
        )
        .where(ProjectTask.user_id == owner)
    )
    if project_id is not None:
        projects_query = projects_query.where(ResearchProject.id == project_id)
        tasks_query = tasks_query.where(ProjectTask.project_id == project_id)
    projects = list(
        await db.scalars(
            projects_query.order_by(ResearchProject.created_at.desc()).limit(limit + 1)
        )
    )
    created_tasks = list(
        await db.scalars(
            tasks_query.order_by(ProjectTask.created_at.desc()).limit(limit + 1)
        )
    )
    completed_tasks = list(
        await db.scalars(
            tasks_query.where(
                ProjectTask.status == "done", ProjectTask.completed_at.is_not(None)
            )
            .order_by(ProjectTask.completed_at.desc())
            .limit(limit + 1)
        )
    )
    for project in projects:
        events.append(
            {
                "id": f"project:{project.id}",
                "type": "project_created",
                "title": project.title,
                "occurred_at": utc(project.created_at),
                "project_id": project.id,
                "provenance": "user_record",
            }
        )
    for items, event_type, date_field in (
        (created_tasks, "task_created", "created_at"),
        (completed_tasks, "task_completed", "completed_at"),
    ):
        for task in items:
            events.append(
                {
                    "id": f"{event_type}:{task.id}",
                    "type": event_type,
                    "title": task.title,
                    "occurred_at": utc(getattr(task, date_field)),
                    "project_id": task.project_id,
                    "provenance": "user_record",
                }
            )
    events.sort(key=lambda e: (e["occurred_at"], e["id"]), reverse=True)
    return {
        "items": events[:limit],
        "truncated": len(events) > limit,
        "limit": limit,
        "project_id": project_id,
        "notes": ["Reading completion has no event timestamp and is not fabricated."],
    }


def stable_id(kind, text):
    return f"{kind}:{hashlib.sha256(text.casefold().encode()).hexdigest()[:20]}"


def build_graph(data):
    nodes, edges = {}, {}
    truncated = data.total > len(data.rows) or data.project_scope["truncated"]

    def node(key, kind, label, origin, provenance, **extra):
        nonlocal truncated
        if key not in nodes:
            if len(nodes) >= MAX_NODES:
                truncated = True
                return False
            nodes[key] = {
                "id": key,
                "type": kind,
                "label": label,
                "origin": origin,
                "provenance": provenance,
                **extra,
            }
        return True

    def edge(source, target, kind, origin, provenance):
        nonlocal truncated
        if source == target or source not in nodes or target not in nodes:
            return
        key = f"{source}|{kind}|{target}"
        if key not in edges:
            if len(edges) >= MAX_EDGES:
                truncated = True
                return
            edges[key] = {
                "id": key,
                "source": source,
                "target": target,
                "type": kind,
                "origin": origin,
                "provenance": provenance,
            }

    topics = defaultdict(list)
    by_doi = {}
    for saved, legacy, canonical in data.rows:
        key = f"paper:{saved.id}"
        node(
            key,
            "paper",
            canonical.title if canonical else legacy.title,
            "verified_metadata",
            "provider_metadata" if canonical else "user_record",
            user_paper_id=saved.id,
        )
        doi = normalize_doi(canonical.doi) if canonical else None
        if doi:
            by_doi[doi] = key
    for saved, legacy, canonical in data.rows:
        key = f"paper:{saved.id}"
        names, provenance = author_names(data, saved, legacy)
        for name in names:
            author_id = stable_id("author", name)
            node(author_id, "author", name, "verified_metadata", provenance)
            edge(key, author_id, "authored_by", "verified_metadata", provenance)
        for tag in data.tags.get(saved.id, []):
            tag_id = f"tag:{tag.id}"
            node(tag_id, "tag", tag.name, "verified_metadata", "user_record")
            edge(key, tag_id, "tagged_with", "verified_metadata", "user_record")
        for topic in terms(canonical.title if canonical else legacy.title):
            topic_id = stable_id("topic", topic)
            node(topic_id, "topic", topic, "inferred_similarity", "title_keyword")
            edge(
                key,
                topic_id,
                "shared_topic_inferred",
                "inferred_similarity",
                "title_keyword",
            )
            topics[topic].append(key)
        for source in data.sources.get(saved.id, []):
            links = source_metadata(source).get("citation_links", [])
            if not isinstance(links, list):
                continue
            for link in links[:100]:
                if not isinstance(link, dict) or not isinstance(link.get("doi"), str):
                    continue
                target = by_doi.get(normalize_doi(link["doi"]))
                if target:
                    edge(
                        key,
                        target,
                        "cites_or_related",
                        "verified_metadata",
                        f"provider_citation:{source.provider}",
                    )
    # Connect adjacent papers per shared keyword, rather than an O(n²) clique.
    for topic, paper_ids in sorted(topics.items()):
        paper_ids = sorted(set(paper_ids))
        for source, target in zip(paper_ids, paper_ids[1:]):
            edge(
                source,
                target,
                "shared_topic_inferred",
                "inferred_similarity",
                "shared_title_keyword",
            )
    for project in data.projects:
        node(
            f"project:{project.id}",
            "project",
            project.title,
            "verified_metadata",
            "user_record",
            project_id=project.id,
        )
    for project_id, paper_id in data.memberships:
        edge(
            f"project:{project_id}",
            f"paper:{paper_id}",
            "project_contains",
            "verified_metadata",
            "user_record",
        )
    return {
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "truncated": truncated,
        "scope": data.scope,
        "project_scope": data.project_scope,
        "limits": {
            "papers": repository.GRAPH_PAPER_LIMIT,
            "nodes": MAX_NODES,
            "edges": MAX_EDGES,
            "projects": repository.PROJECT_LIMIT,
        },
        "project_id": data.project_id,
        "legend": {
            "verified_metadata": "Recorded provider metadata or user records; "
            "provenance distinguishes them.",
            "inferred_similarity": "Title-keyword similarity only; "
            "never a verified citation.",
            "cites_or_related": "Provider-recorded link; incoming citations may "
            "mean the target cites this paper, not an outgoing reference.",
        },
    }


async def knowledge_graph(db, owner, project_id=None):
    return build_graph(
        await repository.snapshot(db, owner, project_id, repository.GRAPH_PAPER_LIMIT)
    )
