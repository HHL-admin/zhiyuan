from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    """用户角色"""
    ADMIN = "admin"  # 特权用户
    USER = "user"    # 一般用户


class UserBase(BaseModel):
    """用户基础模型"""
    username: str = Field(..., min_length=2, max_length=50)
    email: str
    role: UserRole = UserRole.USER


class UserCreate(UserBase):
    """创建用户"""
    password: str = Field(..., min_length=6)


class UserUpdate(BaseModel):
    """更新用户"""
    email: Optional[str] = None
    password: Optional[str] = Field(None, min_length=6)
    role: Optional[UserRole] = None


class UserLogin(BaseModel):
    """用户登录"""
    username: str
    password: str


class User(UserBase):
    """用户模型"""
    id: int
    created_at: datetime
    is_active: bool = True

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Token响应"""
    access_token: str
    token_type: str = "bearer"
    user: User


class TokenData(BaseModel):
    """Token数据"""
    username: Optional[str] = None
    role: Optional[UserRole] = None


class UserListResponse(BaseModel):
    """用户列表响应"""
    users: List[User]
    total: int
