from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.models.assistant import AIUsage
from app.models.document_intelligence import ProcessingJob
from app.models.library import Document
from app.models.multimodal import AssetDeletion, DocumentAsset
from app.models.user_preference import UserPreference
from app.modules.documents.processing import DocumentProcessor
from app.modules.multimodal.cleanup import drain_asset_deletions
from app.modules.multimodal.extractor import extract_assets
from app.modules.multimodal.processing import AssetProcessor
from app.modules.multimodal.storage import AssetStorage
from tests.modules.ai.test_assistant import authenticate
from tests.modules.multimodal.test_extractor import sample_asset_pdf

BASE = "/api/v1/multimodal"


def indexed(client, db, token):
    authenticate(client, token)
    client.app.state.document_dispatcher = AsyncMock()
    response = client.post(
        "/api/v1/library/upload",
        files={"file": ("visual.pdf", sample_asset_pdf(), "application/pdf")},
    )
    assert response.status_code == 201, response.text
    doc = response.json()
    job = db.scalar(select(ProcessingJob).where(ProcessingJob.document_id == doc["id"]))
    db.commit()
    client.portal.call(
        DocumentProcessor(client.app.state.discovery_session_factory).process_job,
        job.id,
    )
    assert client.get(f"/api/v1/documents/{doc['id']}").json()["status"] == "completed"
    return doc


def extracted(client, db, token):
    doc = indexed(client, db, token)
    response = client.post(f"{BASE}/documents/{doc['id']}/extract")
    assert response.status_code == 202, response.text
    job = response.json()
    processor = AssetProcessor(
        client.app.state.discovery_session_factory, extractor=extract_assets
    )
    client.portal.call(processor.process_job, job["job_id"])
    listing = client.get(f"{BASE}/documents/{doc['id']}/assets")
    assert listing.status_code == 200, listing.text
    assert listing.json()["extraction"]["status"] == "completed", listing.text
    return doc, listing.json()["items"]


def test_real_assets_details_links_filters_private_images(client, db, access_token):
    doc, assets = extracted(client, db, access_token)
    assert {a["asset_type"] for a in assets} >= {"figure", "table", "equation"}
    assert all("storage_key" not in a and a["document_version"] == 1 for a in assets)
    table = next(a for a in assets if a["asset_type"] == "table")
    assert table["structured_data"]["headers"] and table["structured_data"]["rows"]
    detail = client.get(f"{BASE}/assets/{table['id']}")
    assert detail.headers["cache-control"] == "private, no-store"
    assert detail.json()["linked_chunks"]
    for asset in assets:
        filtered = client.get(
            f"{BASE}/documents/{doc['id']}/assets?asset_type={asset['asset_type']}&page_number={asset['page_number']}"
        ).json()["items"]
        assert all(
            a["asset_type"] == asset["asset_type"]
            and a["page_number"] == asset["page_number"]
            for a in filtered
        )
        image = client.get(f"{BASE}/assets/{asset['id']}/image")
        assert image.status_code == (200 if asset["has_image"] else 404)
        if image.status_code == 200:
            assert (
                image.content.startswith(b"\x89PNG")
                and image.headers["content-type"] == "image/png"
            )


def test_tenant_isolation_all_endpoints(client, db, access_token, another_access_token):
    doc, assets = extracted(client, db, another_access_token)
    authenticate(client, access_token)
    for method, path, payload in [
        ("POST", f"/documents/{doc['id']}/extract", {}),
        ("GET", f"/documents/{doc['id']}/assets", None),
        ("GET", f"/assets/{assets[0]['id']}", None),
        ("GET", f"/assets/{assets[0]['id']}/image", None),
        ("POST", f"/assets/{assets[0]['id']}/explain", {}),
        (
            "POST",
            f"/assets/{assets[0]['id']}/vqa",
            {"question": "What does this figure show?"},
        ),
    ]:
        response = client.request(
            method, BASE + path, **({"json": payload} if payload is not None else {})
        )
        assert response.status_code == 404, response.text


def test_explain_vqa_bangla_usage_and_replay(client, db, access_token, test_user):
    _, assets = extracted(client, db, access_token)
    asset = next(a for a in assets if a["asset_type"] == "table")
    payload = {"language": "bn", "request_id": str(uuid4())}
    response = client.post(f"{BASE}/assets/{asset['id']}/explain", json=payload)
    assert response.status_code == 200, response.text
    result = response.json()
    assert (
        result["extracted_facts"]
        and result["evidence"]["page_number"] == asset["page_number"]
    )
    assert result["language"] == "bn" and result["provider_used"] == "offline"
    assert (
        client.post(f"{BASE}/assets/{asset['id']}/explain", json=payload).json()
        == result
    )
    absent = client.post(
        f"{BASE}/assets/{asset['id']}/vqa",
        json={
            "question": "Does this table prove quantum teleportation across galaxies?"
        },
    )
    assert absent.status_code == 200, absent.text
    assert absent.json()["evidence_status"] == "insufficient_evidence"
    db.expire_all()
    assert all(
        u.feature == "multimodal"
        for u in db.scalars(select(AIUsage).where(AIUsage.user_id == test_user.id))
    )


def test_cloud_consent_and_quota_before_bytes_dispatch(
    client, db, access_token, test_user, monkeypatch
):
    _, assets = extracted(client, db, access_token)
    asset = assets[0]
    fake = AsyncMock()
    fake.name = "cloud"
    fake.model = "mock"
    client.app.state.ai_gateway.cloud = fake
    response = client.post(
        f"{BASE}/assets/{asset['id']}/explain", json={"provider": "cloud"}
    )
    assert response.status_code == 403
    fake.generate_vision.assert_not_awaited()
    db.add(UserPreference(user_id=test_user.id, allow_external_ai=True))
    db.commit()
    monkeypatch.setattr(settings, "AI_DAILY_TOKEN_LIMIT", 1)
    assert (
        client.post(
            f"{BASE}/assets/{asset['id']}/explain", json={"provider": "cloud"}
        ).status_code
        == 429
    )
    fake.generate_vision.assert_not_awaited()


@pytest.mark.parametrize("deletion", ["pdf", "paper", "account"])
def test_deletion_queues_and_removes_private_pngs(
    client, db, access_token, test_user, deletion
):
    doc, assets = extracted(client, db, access_token)
    owner = test_user.id
    db.expire_all()
    objects = [
        (a.storage_key, a.image_size_bytes)
        for a in db.scalars(
            select(DocumentAsset).where(DocumentAsset.document_id == doc["id"])
        )
        if a.storage_key
    ]
    assert objects
    db.commit()
    if deletion == "pdf":
        response = client.delete(f"/api/v1/library/papers/{doc['user_paper_id']}/pdf")
    elif deletion == "paper":
        document = db.get(Document, doc["id"])
        from app.models.paper import UserPaper

        legacy = db.get(UserPaper, document.user_paper_id).legacy_paper_id
        db.commit()
        response = client.delete(f"/api/v1/papers/{legacy}")
    else:
        response = client.delete("/api/v1/users/me")
    assert response.status_code in (200, 204), response.text

    async def drain():
        async with client.app.state.discovery_session_factory() as session:
            await drain_asset_deletions(session)

    client.portal.call(drain)
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(DocumentAsset)) == 0
    assert db.scalar(select(func.count()).select_from(AssetDeletion)) == 0
    for key, size in objects:
        with pytest.raises(FileNotFoundError):
            AssetStorage(owner).read(key, size)


def test_reextract_replaces_files_and_old_assets_and_reindex_denies_stale(
    client, db, access_token
):
    doc, assets = extracted(client, db, access_token)
    response = client.post(f"{BASE}/documents/{doc['id']}/extract")
    duplicate = client.post(f"{BASE}/documents/{doc['id']}/extract")
    assert response.json() == duplicate.json()
    client.portal.call(
        AssetProcessor(
            client.app.state.discovery_session_factory, extractor=extract_assets
        ).process_job,
        response.json()["job_id"],
    )
    db.expire_all()
    document = db.get(Document, doc["id"])
    document.version += 1
    db.commit()
    assert client.get(f"{BASE}/assets/{assets[0]['id']}").status_code == 404
    listing = client.get(f"{BASE}/documents/{doc['id']}/assets").json()
    assert listing["items"] == [] and listing["is_stale"]


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/documents/1/extract"),
        ("GET", "/documents/1/assets"),
        ("GET", "/assets/1"),
        ("GET", "/assets/1/image"),
        ("POST", "/assets/1/explain"),
        ("POST", "/assets/1/vqa"),
    ],
)
def test_authentication_required(client, method, path):
    assert client.request(method, BASE + path).status_code == 401
