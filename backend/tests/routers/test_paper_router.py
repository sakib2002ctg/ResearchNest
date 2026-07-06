from fastapi import status


def create_paper(client):
    response = client.post(
        "/papers/",
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

def test_create_paper(authenticated_client):
    data = create_paper(authenticated_client)

    assert data["id"] > 0
    assert data["title"] == "Attention Is All You Need"
    assert data["authors"] == "Ashish Vaswani"


def test_create_paper_unauthorized(client):
    response = client.post(
        "/papers/",
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

def test_get_paper(authenticated_client):
    paper = create_paper(authenticated_client)

    response = authenticated_client.get(
        f"/papers/{paper['id']}"
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["id"] == paper["id"]
    assert data["title"] == paper["title"]


def test_get_nonexistent_paper(client):
    response = client.get("/papers/999")

    assert response.status_code == status.HTTP_404_NOT_FOUND


# -------------------------
# UPDATE
# -------------------------

def test_owner_can_update(authenticated_client):
    paper = create_paper(authenticated_client)

    response = authenticated_client.put(
        f"/papers/{paper['id']}",
        json={
            "title": "Updated Title",
        },
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["title"] == "Updated Title"
    assert data["authors"] == "Ashish Vaswani"


def test_non_owner_cannot_update(
    client,
    access_token,
    another_access_token,
):
    response = client.post(
        "/papers/",
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
        f"/papers/{paper_id}",
        headers={
            "Authorization": f"Bearer {another_access_token}",
        },
        json={
            "title": "Hack",
        },
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


# -------------------------
# DELETE
# -------------------------

def test_owner_can_delete(authenticated_client):
    paper = create_paper(authenticated_client)

    response = authenticated_client.delete(
        f"/papers/{paper['id']}"
    )

    assert response.status_code == status.HTTP_200_OK

    assert response.json() == {
        "message": "Paper deleted successfully"
    }

    response = authenticated_client.get(
        f"/papers/{paper['id']}"
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_non_owner_cannot_delete(
    client,
    access_token,
    another_access_token,
):
    response = client.post(
        "/papers/",
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
        f"/papers/{paper_id}",
        headers={
            "Authorization": f"Bearer {another_access_token}",
        },
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


# -------------------------
# VALIDATION
# -------------------------

def test_create_validation_error(authenticated_client):
    response = authenticated_client.post(
        "/papers/",
        json={
            "title": "",
            "authors": "Author",
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# -------------------------
# PAGINATION
# -------------------------

def test_get_all_papers(authenticated_client):
    for i in range(3):
        authenticated_client.post(
            "/papers/",
            json={
                "title": f"Paper {i}",
                "authors": "Author",
                "abstract": "Abstract",
                "source": "IEEE",
                "url": f"https://example.com/{i}",
            },
        )

    response = authenticated_client.get(
        "/papers?page=1&size=2"
    )

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

def test_search_papers(authenticated_client):
    authenticated_client.post(
        "/papers/",
        json={
            "title": "FastAPI Guide",
            "authors": "Sebastian",
            "abstract": "Framework",
            "source": "Docs",
            "url": "https://example.com/1",
        },
    )

    authenticated_client.post(
        "/papers/",
        json={
            "title": "Machine Learning",
            "authors": "Andrew",
            "abstract": "Neural Networks",
            "source": "Coursera",
            "url": "https://example.com/2",
        },
    )

    response = authenticated_client.get(
        "/papers/search?q=FastAPI"
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "FastAPI Guide"


def test_search_no_results(authenticated_client):
    create_paper(authenticated_client)

    response = authenticated_client.get(
        "/papers/search?q=TensorFlow"
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["total"] == 0
    assert data["items"] == []
    assert data["pages"] == 0