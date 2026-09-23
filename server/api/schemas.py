from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    firstName: str = Field(min_length=1, max_length=100)
    lastName: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AccessTokenResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    accessToken: str


class RegisterResponse(BaseModel):
    id: str


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None
    email: str | None
    firstName: str | None
    lastName: str | None
    role: str | None
