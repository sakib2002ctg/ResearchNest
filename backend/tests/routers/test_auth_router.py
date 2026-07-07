def test_register_user(client, user_payload):
    response = client.post(
        "/auth/register",
        json=user_payload,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["username"] == user_payload["username"]
    assert data["email"] == user_payload["email"]
    assert "id" in data


def test_register_duplicate_email(client, user_payload):
    client.post(
        "/auth/register",
        json=user_payload,
    )

    response = client.post(
        "/auth/register",
        json=user_payload,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Email already exists."


def test_register_duplicate_username(client, user_payload):
    client.post(
        "/auth/register",
        json=user_payload,
    )

    response = client.post(
        "/auth/register",
        json={
            "username": user_payload["username"],
            "email": "another@example.com",
            "password": user_payload["password"],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Username already exists."


def test_login_success(client, user_payload, login_payload):
    client.post(
        "/auth/register",
        json=user_payload,
    )

    response = client.post(
        "/auth/login",
        json=login_payload,
    )

    assert response.status_code == 200

    data = response.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_password(client, user_payload):
    client.post(
        "/auth/register",
        json=user_payload,
    )

    response = client.post(
        "/auth/login",
        json={
            "email": user_payload["email"],
            "password": "wrongpassword",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_login_unknown_email(client):
    response = client.post(
        "/auth/login",
        json={
            "email": "unknown@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_get_current_user(authenticated_client):
    response = authenticated_client.get(
        "/auth/me",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["username"] == "sakib"
    assert data["email"] == "sakib@example.com"


def test_get_current_user_unauthorized(client):
    response = client.get(
        "/auth/me",
    )

    assert response.status_code == 401
