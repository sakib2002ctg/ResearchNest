from fastapi import status


def test_create_paper(client):
    response = client.post(
        "/papers/",
        json={
            "title": "GPT-4 Technical Report",
            "authors": "OpenAI",
            "abstract": "Large language model.",
            "source": "OpenAI",
            "url": "https://arxiv.org/abs/2303.08774",
        },
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["id"] is not None
    assert data["title"] == "GPT-4 Technical Report"
    assert data["authors"] == "OpenAI"


def test_get_all_papers(client):
    client.post(
        "/papers/",
        json={
            "title": "Paper One",
            "authors": "Author",
            "abstract": "Test",
            "source": "IEEE",
            "url": "https://example.com",
        },
    )

    response = client.get("/papers/")

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 1


def test_get_paper_by_id(client):
    create = client.post(
        "/papers/",
        json={
            "title": "Paper",
            "authors": "Author",
            "abstract": "Test",
            "source": "IEEE",
            "url": "https://example.com",
        },
    )

    paper_id = create.json()["id"]

    response = client.get(f"/papers/{paper_id}")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == paper_id


def test_update_paper(client):
    create = client.post(
        "/papers/",
        json={
            "title": "Old Title",
            "authors": "Old Author",
            "abstract": "Test",
            "source": "IEEE",
            "url": "https://example.com",
        },
    )

    paper_id = create.json()["id"]

    response = client.put(
        f"/papers/{paper_id}",
        json={
            "authors": "New Author"
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["authors"] == "New Author"
    assert response.json()["title"] == "Old Title"


def test_delete_paper(client):
    create = client.post(
        "/papers/",
        json={
            "title": "Delete Me",
            "authors": "Author",
            "abstract": "Test",
            "source": "IEEE",
            "url": "https://example.com",
        },
    )

    paper_id = create.json()["id"]

    response = client.delete(f"/papers/{paper_id}")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "Paper deleted successfully"