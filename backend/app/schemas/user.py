from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=50,
    )
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(
        min_length=8,
        max_length=128,
    )


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=128,
    )


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: str | None = None


class UserResponse(UserBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
