# ResearchNest v2 Feature Status Register

This register tracks the twelve functional modules and thirteen requested roadmap
phases. **Implemented & Verified** means the deliverable exists and its repository
checks have run; it does not certify an untested public deployment, model quality,
external provider availability, or unlimited scale. Historical architecture and
baseline documents remain available; milestone reports describe the actual scope
and verification limits of each phase.

## Functional modules

| Module | Status | Implemented scope and evidence |
| --- | --- | --- |
| 01 — Accounts and identity | Implemented & Verified | Argon2id, session-bound JWTs, verification/reset/change flows, profile/preferences, device revocation, account export/dashboard; [Phases 01–02](../milestones/PHASE_02.md), identity/router/PostgreSQL tests |
| 02 — Research discovery | Implemented & Verified | Async arXiv, OpenAlex, Crossref, Semantic Scholar and PubMed adapters, unified results, caching, deduplication, verified library saves; [Phase 03](../milestones/PHASE_03.md), mocked adapter/gateway tests |
| 03 — Personal research library | Implemented & Verified | Private PDF upload/download, collections, tags, notes/highlights and reading progress; [Phase 04](../milestones/PHASE_04.md), storage/tenant-isolation tests |
| 04 — Document intelligence | Implemented & Verified | Durable versioned extraction/OCR, pages/chunks, embeddings, retry/recovery and private retrieval; [Phase 05](../milestones/PHASE_05.md), extraction/worker/PostgreSQL tests |
| 05 — AI research assistant | Implemented & Verified | Owned-source RAG, conversations, exact citations, consent, quotas, local/cloud/offline routing; [Phase 06](../milestones/PHASE_06.md), gateway/evidence/replay/tenant tests |
| 06 — Paper intelligence | Implemented & Verified | Structured paper extraction, source-linked comparisons and scoped synthesis/gaps with freshness checks; [Phase 07](../milestones/PHASE_07.md), analysis/evidence/ownership tests |
| 07 — Citation manager | Implemented & Verified | Private references, BibTeX/RIS import/export, supported academic formatting and metadata warnings; [Phase 08](../milestones/PHASE_08.md), citation/parser/formatting tests |
| 08 — Academic writing studio | Implemented & Verified | Bilingual drafts, outlines, versions, source-grounded suggestions and document exports; [Phase 08](../milestones/PHASE_08.md), version/concurrency/export tests |
| 09 — Multimodal research intelligence | Implemented & Verified | Bounded PDF figures/tables/equations, private PNGs, chunk links, evidence-separated explanations/VQA and durable cleanup; [Phase 09](../milestones/PHASE_09.md), native extraction/storage/fencing tests |
| 10 — Projects and collaboration | Implemented & Verified | Project papers/tasks/milestones/notes/chats/exports and explicit owner/editor/viewer team sharing; [Phase 10](../milestones/PHASE_10.md), [Phase 11](../milestones/PHASE_11.md), project/team/SQL ACL/concurrency tests |
| 11 — Analytics and knowledge graph | Implemented & Verified | Owned/project publication trends, reading/index/analysis coverage, timelines and graph provenance; [Phase 10](../milestones/PHASE_10.md), aggregation/freshness/budget/origin tests |
| 12 — Bilingual research education | Implemented & Verified | Five guides, step progress, eighteen glossary terms and owned-paper beginner explanations with explicit offline limits; [Phase 11](../milestones/PHASE_11.md), bilingual/progress/evidence/quota tests |

Operational administration is a supporting module. Phase 12 adds explicit database
admin privileges, audited operational metadata, emergency revocation and safely
versioned job recovery; it does not grant administrators unrestricted document or
prompt browsing.

## Roadmap phases

| Phase | Status | Deliverable and verification record |
| --- | --- | --- |
| 00 — Baseline/specification | Implemented & Verified | [Audit, reconciliation register, debt/security gaps](../milestones/PHASE_00.md), root engineering rules and architecture documents; source/document inspection |
| 01 — Foundation/security | Implemented & Verified | [Versioned API, migration repair, tenant isolation, identity/security entities](../milestones/PHASE_01.md) |
| 02 — Public platform | Implemented & Verified | [Identity lifecycle, privacy export/dashboard, bilingual Next.js foundation](../milestones/PHASE_02.md) |
| 03 — Discovery | Implemented & Verified | [Academic adapters, cache, deduplication and Discover UI](../milestones/PHASE_03.md) |
| 04 — Personal library | Implemented & Verified | [PDF/collections/tags/annotations/progress and Library UI](../milestones/PHASE_04.md) |
| 05 — Document intelligence | Implemented & Verified | [Extraction/OCR, indexing, durable jobs and versioned sources](../milestones/PHASE_05.md) |
| 06 — AI assistant | Implemented & Verified | [Source-grounded chat, citations, routing and usage controls](../milestones/PHASE_06.md) |
| 07 — Paper intelligence | Implemented & Verified | [Structured analyses, comparisons and scoped synthesis](../milestones/PHASE_07.md) |
| 08 — Citations/writing | Implemented & Verified | [References, academic writing, versions and exports](../milestones/PHASE_08.md) |
| 09 — Multimodal | Implemented & Verified | [Private assets, extraction, visual explanations and VQA](../milestones/PHASE_09.md) |
| 10 — Projects/insights | Implemented & Verified | [Workspaces, project export, analytics and graph](../milestones/PHASE_10.md) |
| 11 — Education/teams | Implemented & Verified | [Bilingual learning and explicit collaboration ACLs](../milestones/PHASE_11.md) |
| 12 — Production maturity | Implemented & Verified | [Administration, security, observability, deployment, recovery and launch checks](../milestones/PHASE_12.md); 901 backend/37 frontend tests, real isolated SQL recovery and local benchmark; target deployment qualification remains required |

## Deployment qualification

Deployment acceptance remains separate from functional status. Operators must
validate the Compose images and services, live PostgreSQL/pgvector and Redis,
TLS/proxy trust, SMTP/scanning and any enabled external providers, private storage,
off-host encrypted backup recovery, alerting, and realistic workload capacity in
the target environment. The Phase 12 report records which checks ran locally and
which require that environment. No public deployment or external message was
performed as part of these repository changes.
