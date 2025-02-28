from typing import Optional
from pydantic import BaseModel, Field, validator, field_validator


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    permissions: Optional[str] = "read_book"  # Made optional with default value


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class BookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    author: str = Field(..., min_length=1, max_length=100)
    isbn: str = Field(..., min_length=10, max_length=17)

    @validator('isbn')
    def validate_isbn(cls, v):
        # Remove hyphens and spaces for validation
        v_clean = v.replace('-', '').replace(' ', '')
        if not v_clean.isalnum():  # ISBN should only contain alphanumeric characters
            raise ValueError('ISBN must only contain alphanumeric characters, hyphens, or spaces')
        return v


class BookSchema(BookCreate):
    id: int

    class Config:
        from_attributes = True

class BookUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    author: Optional[str] = Field(None, min_length=1, max_length=100)
    isbn: Optional[str] = Field(None, min_length=10, max_length=17)

    @validator('isbn')
    def validate_isbn(cls, v):
        if v is None:
            return v
        # Remove hyphens and spaces for validation
        v_clean = v.replace('-', '').replace(' ', '')
        if not v_clean.isalnum():  # ISBN should only contain alphanumeric characters
            raise ValueError('ISBN must only contain alphanumeric characters, hyphens, or spaces')
        return v