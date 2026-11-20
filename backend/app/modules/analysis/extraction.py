"""Conservative offline extraction and provider-independent claim verification."""

import re
import unicodedata

from app.modules.ai.gateway import CitationClaim
from app.modules.analysis.schemas import (
    FIELD_NAMES,
    LIST_FIELDS,
    MISSING,
    Claim,
    ComparisonOutput,
    Extraction,
    Gap,
    PaperExtraction,
    SourceClaim,
    SynthesisClaim,
)

# These are attribution cues, not fabricated conclusions or a semantic model.
CUES = {
    "abstract_summary": ("abstract", "সারসংক্ষেপ"),
    "research_problem": (
        "research problem",
        "problem statement",
        "we address",
        "সমস্যা",
    ),
    "research_objectives": ("objective", "our aim", "we aim", "উদ্দেশ্য", "লক্ষ্য"),
    "methodology": ("methodology", "method", "methods", "we used", "পদ্ধতি"),
    "datasets": ("dataset", "data set", "mnist", "cifar", "ডেটাসেট", "তথ্যসেট"),
    "models_and_algorithms": (
        "algorithm",
        "model",
        "transformer",
        "মডেল",
        "অ্যালগরিদম",
    ),
    "evaluation_metrics": (
        "metric",
        "accuracy",
        "precision",
        "recall",
        "f1",
        "নির্ভুলতা",
        "মূল্যায়ন",
    ),
    "key_results": ("results", "we found", "ফলাফল"),
    "contributions": ("contribution", "অবদান"),
    "limitations": ("limitation", "সীমাবদ্ধতা"),
    "future_work": ("future work", "future research", "ভবিষ্যৎ"),
    "strengths": ("strength", "সবল", "শক্তিশালী"),
    "weaknesses": ("weakness", "weaknesses", "দুর্বল"),
}


def normalize(text):
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def has_cue(field, text):
    normalized = normalize(text)
    return any(
        re.search(
            r"(?<!\w)"
            + re.escape(cue)
            + (
                "s?"
                if cue.isascii() and cue[-1].isalpha() and not cue.endswith("s")
                else ""
            )
            + r"(?!\w)",
            normalized,
        )
        for cue in CUES[field]
    )


def snippets(source):
    # Verbatim offsets preserve punctuation, whitespace and Bangla combining marks.
    sentences = re.split(r"(?<=[.!?।])\s+|\n+", source.content)
    return [
        sentence[start : start + 600].strip()
        for sentence in sentences
        for start in range(0, len(sentence), 500)
        if len(sentence[start : start + 600].strip()) >= 10
    ]


def select_context(sources):
    """Balanced, section-diverse UTF-8 context, capped at 10k characters total."""
    groups = {}
    for source in sources:
        groups.setdefault(source.user_paper_id, []).append(source)
    offered = []
    per_paper = 10000 // max(1, len(groups))
    for rows in groups.values():
        candidates = [(source, quote) for source in rows for quote in snippets(source)]
        chosen, seen, size = [], set(), 0
        for field in FIELD_NAMES:
            candidate = next(
                (
                    (source, quote)
                    for source, quote in candidates
                    if (source.chunk_id, quote) not in seen
                    and has_cue(field, (source.section_heading or "") + " " + quote)
                ),
                None,
            )
            if candidate:
                source, quote = candidate
                if size + len(quote) <= per_paper:
                    chosen.append((source, quote))
                    seen.add((source.chunk_id, quote))
                    size += len(quote)
        for source, quote in candidates:
            if len(chosen) >= 24:
                break
            if (source.chunk_id, quote) not in seen and size + len(quote) <= per_paper:
                chosen.append((source, quote))
                seen.add((source.chunk_id, quote))
                size += len(quote)
        offered.extend(
            {
                "user_paper_id": s.user_paper_id,
                "chunk_id": s.chunk_id,
                "paper_title": s.paper_title,
                "page_number": s.page_number,
                "section_heading": s.section_heading,
                "content": quote,
            }
            for s, quote in chosen
        )
    return offered


def offline_extraction(passages):
    fields = {}
    for field in FIELD_NAMES:
        matches = [
            p
            for p in passages
            if has_cue(field, (p["section_heading"] or "") + " " + p["content"])
        ]
        if matches:
            # Quote sources without claiming translation or inferring absent fields.
            fields[field] = [
                Claim(
                    text=p["content"],
                    evidence=[
                        CitationClaim(
                            chunk_id=p["chunk_id"], quoted_snippet=p["content"]
                        )
                    ],
                )
                for p in matches[:2]
            ]
    return Extraction(fields=fields)


def offline_comparison(passages, paper_ids, language):
    papers = [
        PaperExtraction(
            user_paper_id=pid,
            **offline_extraction(
                [p for p in passages if p["user_paper_id"] == pid]
            ).model_dump(),
        )
        for pid in paper_ids
    ]
    findings, unresolved = [], []
    for paper in papers:
        fields = paper.fields
        finding = next(
            (
                fields[field][0]
                for field in ("key_results", "methodology", "abstract_summary")
                if fields.get(field)
            ),
            None,
        )
        limitation = next(
            (
                fields[field][0]
                for field in ("limitations", "future_work")
                if fields.get(field)
            ),
            None,
        )
        for claim, target in ((finding, findings), (limitation, unresolved)):
            if claim:
                target.append((paper.user_paper_id, claim))

    def references(items):
        return [
            SourceClaim(user_paper_id=pid, **claim.evidence[0].model_dump())
            for pid, claim in items
        ]

    synthesis = []
    if len(findings) >= 2:
        synthesis = [
            SynthesisClaim(
                text=(
                    "Evidence from the selected papers only:\n"
                    if language == "en"
                    else "শুধু নির্বাচিত গবেষণাপত্রের প্রমাণ:\n"
                )
                + "\n".join(claim.text[:480] for _, claim in findings),
                evidence=references(findings),
            )
        ]
    gaps = []
    if len(unresolved) >= 2:
        gaps = [
            Gap(
                title=(
                    "Reported limitations to investigate"
                    if language == "en"
                    else "অনুসন্ধানের জন্য উল্লিখিত সীমাবদ্ধতা"
                ),
                text=(
                    "These selected sources report unresolved issues; "
                    "follow-up research can investigate them:\n"
                    if language == "en"
                    else "নির্বাচিত উৎসগুলোতে অনিষ্পন্ন সমস্যার উল্লেখ আছে; "
                    "পরবর্তী গবেষণায় এগুলো অনুসন্ধান করা যেতে পারে:\n"
                )
                + "\n".join(claim.text[:480] for _, claim in unresolved),
                evidence=references(unresolved),
            )
        ]
    return ComparisonOutput(
        papers=papers, literature_synthesis=synthesis, research_gaps=gaps
    )


def evidence_for(claim, offered, *, field, expected_paper=None):
    matches = [
        p
        for p in offered
        if p["chunk_id"] == claim.chunk_id
        and (expected_paper is None or p["user_paper_id"] == expected_paper)
        and claim.quoted_snippet in p["content"]
    ]
    if not matches or len(claim.quoted_snippet.strip()) < 10:
        raise ValueError("Unverified source attribution.")
    passage = matches[0]
    return {
        "field": field,
        "user_paper_id": passage["user_paper_id"],
        "chunk_id": passage["chunk_id"],
        "paper_title": passage["paper_title"],
        "page_number": passage["page_number"],
        "section_heading": passage["section_heading"],
        "quoted_snippet": claim.quoted_snippet,
    }


def validate_extraction(output, offered, paper_id):
    values, statuses, links = {}, {}, []
    for field in FIELD_NAMES:
        claims = output.fields.get(field, [])
        if not claims:
            values[field] = [MISSING] if field in LIST_FIELDS else MISSING
            statuses[field] = "not_specified"
            continue
        field_links = []
        verbatim = True
        for claim in claims:
            if re.search(r"https?://|\[[^\]]+\]", claim.text):
                raise ValueError("Unverified inline reference.")
            evidence = [
                evidence_for(c, offered, field=field, expected_paper=paper_id)
                for c in claim.evidence
            ]
            if not any(
                has_cue(
                    field,
                    (item["section_heading"] or "") + " " + item["quoted_snippet"],
                )
                for item in evidence
            ):
                raise ValueError("Unmentioned field attribution.")
            literal = any(
                normalize(claim.text) in normalize(item["quoted_snippet"])
                for item in evidence
            )
            if (
                field in {"datasets", "models_and_algorithms", "evaluation_metrics"}
                and not literal
            ):
                raise ValueError("Unverified technical detail.")
            verbatim &= literal
            field_links.extend(evidence)
        values[field] = (
            [c.text for c in claims]
            if field in LIST_FIELDS
            else "\n\n".join(c.text for c in claims)
        )
        statuses[field] = "supported" if verbatim else "partial_interpretation"
        links.extend(field_links)
    return values, statuses, links


def validate_comparison(output, offered, paper_ids):
    if len(output.papers) != len(paper_ids) or {
        p.user_paper_id for p in output.papers
    } != set(paper_ids):
        raise ValueError("Unverified comparison scope.")
    matrix, links, gaps = [], [], []
    for paper in output.papers:
        values, statuses, evidence = validate_extraction(
            paper, offered, paper.user_paper_id
        )
        title = next(
            p["paper_title"]
            for p in offered
            if p["user_paper_id"] == paper.user_paper_id
        )
        matrix.append(
            {
                "user_paper_id": paper.user_paper_id,
                "paper_title": title,
                **values,
                "field_statuses": statuses,
                "evidence_links": evidence,
            }
        )
        links.extend(evidence)
    synthesis = []
    for kind, claims in (
        ("literature_synthesis", output.literature_synthesis),
        ("research_gaps", output.research_gaps),
    ):
        for claim in claims:
            if re.search(
                r"https?://|\[[^\]]+\]", claim.text + " " + getattr(claim, "title", "")
            ):
                raise ValueError("Unverified synthesis reference.")
            evidence = [
                evidence_for(c, offered, field=kind, expected_paper=c.user_paper_id)
                for c in claim.evidence
            ]
            if len({e["user_paper_id"] for e in evidence}) < 2:
                raise ValueError("Cross-paper claims require two different sources.")
            if kind == "research_gaps" and not all(
                any(
                    has_cue(f, (e["section_heading"] or "") + " " + e["quoted_snippet"])
                    for f in ("limitations", "future_work")
                )
                for e in evidence
            ):
                raise ValueError(
                    "Research gaps require explicit limitation or future-work evidence."
                )
            links.extend(evidence)
            if kind == "research_gaps":
                gaps.append(
                    {
                        "title": claim.title,
                        "description": claim.text,
                        "scope": "selected_papers_only",
                        "evidence_status": "partial_interpretation",
                        "evidence_links": evidence,
                    }
                )
            else:
                synthesis.append(claim.text)
    return matrix, synthesis, gaps, links
