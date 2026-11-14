from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

EmailType = str

class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=128)

class UserLogin(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
