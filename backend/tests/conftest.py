import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.database.database import Base, get_db
from app.main import app
from app.models.user import User


SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


@pytest.fixture(scope="function")
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# -------------------------
# User Fixtures
# -------------------------

@pytest.fixture
def user_payload():
    return {
        "username": "sakib",
        "email": "sakib@example.com",
        "password": "password123",
    }


@pytest.fixture
def login_payload():
    return {
        "email": "sakib@example.com",
        "password": "password123",
    }


@pytest.fixture(scope="function")
def test_user(db):
    user = User(
        username="sakib",
        email="sakib@example.com",
        hashed_password=hash_password("password123"),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@pytest.fixture(scope="function")
def access_token(test_user):
    return create_access_token(
        data={
            "sub": test_user.email,
        }
    )


@pytest.fixture(scope="function")
def authenticated_client(client, access_token):
    client.headers.update(
        {
            "Authorization": f"Bearer {access_token}",
        }
    )

    return client


# -------------------------
# Paper Fixtures
# -------------------------

@pytest.fixture
def paper_payload():
    return {
        "title": "Attention Is All You Need",
        "authors": "Ashish Vaswani",
        "abstract": "Transformer architecture",
        "source": "NeurIPS",
        "url": "https://example.com/paper",
    }