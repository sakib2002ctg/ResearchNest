import pytest
from fastapi import status

pytestmark = pytest.mark.parametrize("api_prefix", ["/api/v1", ""])


def create_paper(client, api_prefix):
    response = client.post(
        f"{api_prefix}/papers/",
        json={
            "title": "Attention Is All You Need",
            "authors": "Ashish Vaswani",
            "abstract": "Transformer architecture",
            "source": "NeurIPS",
            "url": "https://example.com/paper",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    return response.json()


# -------------------------
# CREATE
# -------------------------


def test_create_paper(api_prefix, authenticated_client):
    data = create_paper(authenticated_client, api_prefix)

    assert data["id"] > 0
    assert data["title"] == "Attention Is All You Need"
    assert data["authors"] == "Ashish Vaswani"


def test_create_paper_unauthorized(api_prefix, client):
    response = client.post(
        f"{api_prefix}/papers/",
        json={
            "title": "Paper",
            "authors": "Author",
            "abstract": "Abstract",
            "source": "IEEE",
            "url": "https://example.com",
        },
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# -------------------------
# GET
# -------------------------


def test_get_paper(api_prefix, authenticated_client):
    paper = create_paper(authenticated_client, api_prefix)

    response = authenticated_client.get(f"{api_prefix}/papers/{paper['id']}")

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["id"] == paper["id"]
    assert data["title"] == paper["title"]


def test_get_nonexistent_paper(api_prefix, authenticated_client):
    response = authenticated_client.get(f"{api_prefix}/papers/999")

    assert response.status_code == status.HTTP_404_NOT_FOUND


# -------------------------
# UPDATE
# -------------------------


def test_owner_can_update(api_prefix, authenticated_client):
    paper = create_paper(authenticated_client, api_prefix)

    response = authenticated_client.put(
        f"{api_prefix}/papers/{paper['id']}",
        json={
            "title": "Updated Title",
        },
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["title"] == "Updated Title"
    assert data["authors"] == "Ashish Vaswani"


def test_non_owner_cannot_update(
    api_prefix,
    client,
    access_token,
    another_access_token,
):
    response = client.post(
        f"{api_prefix}/papers/",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        json={
            "title": "Paper",
            "authors": "Author",
            "abstract": "Abstract",
            "source": "IEEE",
            "url": "https://example.com",
        },
    )

    assert response.status_code == status.HTTP_200_OK

    paper_id = response.json()["id"]

    response = client.put(
        f"{api_prefix}/papers/{paper_id}",
        headers={
            "Authorization": f"Bearer {another_access_token}",
        },
        json={
            "title": "Hack",
        },
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


# -------------------------
# DELETE
# -------------------------


def test_owner_can_delete(api_prefix, authenticated_client):
    paper = create_paper(authenticated_client, api_prefix)

    response = authenticated_client.delete(f"{api_prefix}/papers/{paper['id']}")

    assert response.status_code == status.HTTP_200_OK

    assert response.json() == {"message": "Paper deleted successfully"}

    response = authenticated_client.get(f"{api_prefix}/papers/{paper['id']}")

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_non_owner_cannot_delete(
    api_prefix,
    client,
    access_token,
    another_access_token,
):
    response = client.post(
        f"{api_prefix}/papers/",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        json={
            "title": "Paper",
            "authors": "Author",
            "abstract": "Abstract",
            "source": "IEEE",
            "url": "https://example.com",
        },
    )

    assert response.status_code == status.HTTP_200_OK

    paper_id = response.json()["id"]

    response = client.delete(
        f"{api_prefix}/papers/{paper_id}",
        headers={
            "Authorization": f"Bearer {another_access_token}",
        },
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


# -------------------------
# VALIDATION
# -------------------------


def test_create_validation_error(api_prefix, authenticated_client):
    response = authenticated_client.post(
        f"{api_prefix}/papers/",
        json={
            "title": "",
            "authors": "Author",
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# -------------------------
# PAGINATION
# -------------------------


def test_get_all_papers(api_prefix, authenticated_client):
    for i in range(3):
        authenticated_client.post(
            f"{api_prefix}/papers/",
            json={
                "title": f"Paper {i}",
                "authors": "Author",
                "abstract": "Abstract",
                "source": "IEEE",
                "url": f"https://example.com/{i}",
            },
        )

    response = authenticated_client.get(f"{api_prefix}/papers?page=1&size=2")

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["page"] == 1
    assert data["size"] == 2
    assert data["total"] == 3
    assert data["pages"] == 2
    assert len(data["items"]) == 2


# -------------------------
# SEARCH
# -------------------------


def test_search_papers(api_prefix, authenticated_client):
    authenticated_client.post(
        f"{api_prefix}/papers/",
        json={
            "title": "FastAPI Guide",
            "authors": "Sebastian",
            "abstract": "Framework",
            "source": "Docs",
            "url": "https://example.com/1",
        },
    )

    authenticated_client.post(
        f"{api_prefix}/papers/",
        json={
            "title": "Machine Learning",
            "authors": "Andrew",
            "abstract": "Neural Networks",
            "source": "Coursera",
            "url": "https://example.com/2",
        },
    )

    response = authenticated_client.get(f"{api_prefix}/papers/search?q=FastAPI")

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "FastAPI Guide"


def test_search_no_results(api_prefix, authenticated_client):
    create_paper(authenticated_client, api_prefix)

    response = authenticated_client.get(f"{api_prefix}/papers/search?q=TensorFlow")

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["total"] == 0
    assert data["items"] == []
    assert data["pages"] == 0
