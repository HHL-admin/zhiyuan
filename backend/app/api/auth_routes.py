from fastapi import APIRouter, HTTPException, Depends, status
from datetime import timedelta

from app.models.user_schemas import UserLogin, Token, User, UserRole
from app.auth.jwt import authenticate_user, create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES

# 账号的创建、升降级、删除统一走层级权限接口（/api/v2），这里只保留登录相关
router = APIRouter()


@router.post("/login", response_model=Token, summary="用户登录")
async def login(user_data: UserLogin):
    """
    用户登录

    - **username**: 用户名
    - **password**: 密码

    返回访问令牌
    """
    user = authenticate_user(user_data.username, user_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 创建访问令牌
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"], "uid": user["id"], "role": user["role"]},
        expires_delta=access_token_expires
    )

    user_obj = User(
        id=user["id"],
        username=user["username"],
        email=user["email"],
        role=UserRole(user["role"]),
        created_at=user["created_at"],
        is_active=bool(user["is_active"])
    )

    return Token(access_token=access_token, user=user_obj)


@router.get("/me", response_model=User, summary="获取当前用户信息")
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户的信息"""
    return current_user
