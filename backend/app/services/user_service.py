from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate


class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def create_user(self, user_data: UserCreate) -> User:
        existing_email = self.repository.get_by_email(user_data.email)
        if existing_email:
            raise ValueError("Email already exists.")

        existing_username = self.repository.get_by_username(user_data.username)
        if existing_username:
            raise ValueError("Username already exists.")

        user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=user_data.password,
        )

        return self.repository.create(user)