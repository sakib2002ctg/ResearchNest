from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import Token, UserCreate


class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def create_user(self, user_data: UserCreate) -> User:
        if self.repository.get_by_email(user_data.email):
            raise ValueError("Email already exists.")

        if self.repository.get_by_username(user_data.username):
            raise ValueError("Username already exists.")

        user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hash_password(user_data.password),
        )

        return self.repository.create(user)

    def authenticate_user(
        self,
        email: str,
        password: str,
    ) -> Token:
        user = self.repository.get_by_email(email)

        if not user:
            raise ValueError("Invalid email or password.")

        if not verify_password(
            password,
            user.hashed_password,
        ):
            raise ValueError("Invalid email or password.")

        access_token = create_access_token(data={"sub": user.email})

        return Token(
            access_token=access_token,
            token_type="bearer",
        )
