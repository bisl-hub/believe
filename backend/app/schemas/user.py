from pydantic import BaseModel
from typing import Optional

class UserCreate(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    is_active: bool
    class Config:
        orm_mode = True

class UserUpdateEmail(BaseModel):
    email: str
    current_password: str

class UserUpdatePassword(BaseModel):
    current_password: str
    new_password: str
