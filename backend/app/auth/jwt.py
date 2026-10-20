import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from loguru import logger

from app.models.user_schemas import TokenData, UserRole, User
from app.auth.database import db
from app.core.config import settings

# JWT 配置：生产环境必须设置环境变量 JWT_SECRET_KEY（否则任何人都能伪造登录凭证）
_DEV_SECRET = "your-secret-key-change-this-in-production-2024"
SECRET_KEY = os.getenv("JWT_SECRET_KEY") or settings.JWT_SECRET_KEY or _DEV_SECRET
if SECRET_KEY == _DEV_SECRET:
    logger.warning("未设置 JWT_SECRET_KEY，正在使用开发用默认密钥，切勿用于生产环境")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24小时

security = HTTPBearer()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[TokenData]:
    """验证令牌"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")

        if username is None:
            return None

        return TokenData(username=username, role=UserRole(role))

    except JWTError:
        return None


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """获取当前用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    token_data = verify_token(token)

    if token_data is None or token_data.username is None:
        raise credentials_exception

    # 用户名可能跨公司重复，优先按 token 里的用户ID查找
    try:
        uid = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]).get("uid")
    except JWTError:
        raise credentials_exception
    if uid is not None:
        user = db.get_user_by_id(uid)
    else:
        same_name = db.get_users_by_username(token_data.username)
        user = same_name[0] if len(same_name) == 1 else None
    if user is None:
        raise credentials_exception

    return User(
        id=user["id"],
        username=user["username"],
        email=user["email"],
        role=UserRole(user["role"]),
        created_at=user["created_at"],
        is_active=bool(user["is_active"])
    )


def authenticate_user(login: str, password: str) -> Optional[dict]:
    """认证用户：login 可以是用户名或邮箱；同名账号用密码区分，仍无法区分时要求用邮箱登录"""
    candidates = db.get_users_by_username(login)
    if not candidates:
        by_email = db.get_user_by_email(login)
        candidates = [by_email] if by_email else []

    matched = [u for u in candidates if db.verify_password(password, u["hashed_password"])]
    if len(matched) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="多个公司存在同名账号，请改用邮箱登录"
        )
    return matched[0] if matched else None
