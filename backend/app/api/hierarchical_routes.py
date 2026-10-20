"""
层级用户管理 API（/api/v2）
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from loguru import logger

from app.auth.jwt import get_current_user
from app.auth.database import db
from app.models.user_schemas import User
from app.services.hierarchical_rbac import (
    hierarchical_rbac as rbac,
    PLATFORM_OWNER, COMPANY_OWNER, ADVANCED_USER, BASIC_USER, LEVEL_NAMES,
)

router = APIRouter()


class GenerateKeyRequest(BaseModel):
    expires_days: int = Field(7, ge=1, le=365)


class CompanyRegisterRequest(BaseModel):
    key_code: str = Field(..., min_length=4)
    company_name: str = Field(..., min_length=1, max_length=100)
    username: str = Field(..., min_length=2, max_length=50)
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)
    user_level: int = Field(BASIC_USER, ge=ADVANCED_USER, le=BASIC_USER)


class ChangeLevelRequest(BaseModel):
    user_level: int = Field(..., ge=ADVANCED_USER, le=BASIC_USER)


def _require_info(user: User) -> dict:
    info = rbac.get_user(user.id)
    if not info:
        raise HTTPException(status_code=403, detail="账号未分配层级，请联系上级")
    return info


def _require_platform_owner(user: User) -> dict:
    info = _require_info(user)
    if info["user_level"] != PLATFORM_OWNER:
        raise HTTPException(status_code=403, detail="仅平台老板可操作")
    return info


def _user_view(user_id: int, info: dict) -> Optional[dict]:
    u = db.get_user_by_id(user_id)
    if not u:
        return None
    return {
        "id": u["id"],
        "username": u["username"],
        "email": u["email"],
        "user_level": info["user_level"],
        "level_name": LEVEL_NAMES.get(info["user_level"], "未知"),
        "created_by": info["created_by"],
        "created_at": info["created_at"],
    }


@router.get("/me", summary="当前用户的层级信息")
async def my_info(current_user: User = Depends(get_current_user)):
    info = rbac.get_user(current_user.id)
    level = info["user_level"] if info else None
    company = rbac.get_company(info["company_id"]) if info and info["company_id"] else None
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "user_level": level,
        "level_name": LEVEL_NAMES.get(level, "未分配"),
        "company_id": company["id"] if company else None,
        "company_name": company["name"] if company else None,
        "permissions": {
            "generate_keys": level == PLATFORM_OWNER,
            "upload_document": level in (COMPANY_OWNER, ADVANCED_USER, BASIC_USER),
            "delete_document": level == COMPANY_OWNER,
            "manage_users": level in (COMPANY_OWNER, ADVANCED_USER),
            "creatable_levels": (
                [ADVANCED_USER, BASIC_USER] if level == COMPANY_OWNER
                else [BASIC_USER] if level == ADVANCED_USER else []
            ),
            "change_level": level == COMPANY_OWNER,
            "delete_user": level == COMPANY_OWNER,
        },
    }


# ==================== 平台老板 ====================

@router.post("/platform/keys", summary="生成公司注册密钥（平台老板）")
async def generate_key(req: GenerateKeyRequest, current_user: User = Depends(get_current_user)):
    _require_platform_owner(current_user)
    return rbac.generate_key(current_user.id, req.expires_days)


@router.get("/platform/keys", summary="我生成的密钥（平台老板）")
async def list_keys(current_user: User = Depends(get_current_user)):
    _require_platform_owner(current_user)
    keys = rbac.list_keys(current_user.id)
    for k in keys:
        used_by = db.get_user_by_id(k["used_by"]) if k["used_by"] else None
        k["used_by_username"] = used_by["username"] if used_by else None
    return {"keys": keys, "total": len(keys)}


@router.delete("/platform/keys/{key_id}", summary="作废未使用的密钥（平台老板）")
async def delete_key(key_id: int, current_user: User = Depends(get_current_user)):
    _require_platform_owner(current_user)
    if not rbac.delete_key(key_id, current_user.id):
        raise HTTPException(status_code=404, detail="密钥不存在或已被使用")
    return {"message": "密钥已作废"}


@router.get("/platform/companies", summary="公司列表（平台老板，只含名称和人数）")
async def list_companies(current_user: User = Depends(get_current_user)):
    _require_platform_owner(current_user)
    companies = rbac.list_companies()
    for c in companies:
        owner = db.get_user_by_id(c["owner_id"])
        c["owner_username"] = owner["username"] if owner else None
    return {"companies": companies, "total": len(companies)}


# ==================== 公司注册（公开，凭密钥） ====================

@router.post("/company/register", summary="凭密钥注册公司老板账号")
async def register_company(req: CompanyRegisterRequest):
    key = rbac.validate_key(req.key_code)
    if not key:
        raise HTTPException(status_code=400, detail="密钥无效、已使用或已过期")
    # 新公司，用户名无需和其他公司去重
    if db.get_user_by_email(req.email):
        raise HTTPException(status_code=400, detail="邮箱已被使用")

    user = db.create_user(req.username, req.email, req.password, role="user")
    if not user:
        raise HTTPException(status_code=400, detail="创建用户失败")

    company_id = rbac.create_company(req.company_name, user["id"])
    rbac.set_user(user["id"], COMPANY_OWNER, company_id, key["created_by"])
    rbac.mark_key_used(req.key_code, user["id"])
    logger.info(f"公司注册成功: {req.company_name} (id={company_id}), 老板 {req.username}")
    return {"message": "公司注册成功，请登录", "company_id": company_id, "username": req.username}


# ==================== 公司内用户管理 ====================

@router.get("/company/users", summary="查看本人可见的下级用户")
async def list_users(current_user: User = Depends(get_current_user)):
    info = _require_info(current_user)
    if not info["company_id"]:
        return {"users": [], "total": 0}
    rows = rbac.list_company_users(info["company_id"], info["user_level"])
    users = []
    for r in rows:
        # 只能看自己和比自己级别低的用户
        if r["user_id"] != current_user.id and r["user_level"] <= info["user_level"]:
            continue
        view = _user_view(r["user_id"], r)
        if view:
            view["is_self"] = r["user_id"] == current_user.id
            users.append(view)
    return {"users": users, "total": len(users)}


@router.post("/company/users", summary="创建下级用户")
async def create_user(req: CreateUserRequest, current_user: User = Depends(get_current_user)):
    info = _require_info(current_user)
    level = info["user_level"]
    if level not in (COMPANY_OWNER, ADVANCED_USER) or not info["company_id"]:
        raise HTTPException(status_code=403, detail="无权创建用户")
    if req.user_level <= level:
        raise HTTPException(status_code=403, detail="只能创建比自己级别低的用户")
    # 用户名只要求在本公司内唯一，不同公司可以重名
    for same in db.get_users_by_username(req.username):
        other = rbac.get_user(same["id"])
        if other and other["company_id"] == info["company_id"]:
            raise HTTPException(status_code=400, detail="本公司已有同名用户")
    if db.get_user_by_email(req.email):
        raise HTTPException(status_code=400, detail="邮箱已被使用")

    user = db.create_user(req.username, req.email, req.password, role="user")
    if not user:
        raise HTTPException(status_code=400, detail="创建用户失败")
    rbac.set_user(user["id"], req.user_level, info["company_id"], current_user.id)
    logger.info(f"{current_user.username} 创建了 {LEVEL_NAMES[req.user_level]} {req.username}")
    return {"message": f"{LEVEL_NAMES[req.user_level]} {req.username} 创建成功", "id": user["id"]}


@router.put("/company/users/{user_id}/level", summary="升级/降级用户（公司老板）")
async def change_level(user_id: int, req: ChangeLevelRequest, current_user: User = Depends(get_current_user)):
    info = _require_info(current_user)
    if info["user_level"] != COMPANY_OWNER:
        raise HTTPException(status_code=403, detail="仅公司老板可升级/降级用户")
    if not rbac.can_manage(current_user.id, user_id):
        raise HTTPException(status_code=404, detail="用户不存在或不属于本公司")
    rbac.update_level(user_id, req.user_level)
    return {"message": f"已调整为{LEVEL_NAMES[req.user_level]}"}


@router.delete("/company/users/{user_id}", summary="删除用户（公司老板）")
async def delete_user(user_id: int, current_user: User = Depends(get_current_user)):
    info = _require_info(current_user)
    if info["user_level"] != COMPANY_OWNER:
        raise HTTPException(status_code=403, detail="仅公司老板可删除用户")
    if not rbac.can_manage(current_user.id, user_id):
        raise HTTPException(status_code=404, detail="用户不存在或不属于本公司")
    target = db.get_user_by_id(user_id)
    rbac.remove_user(user_id)
    db.delete_user(user_id)
    return {"message": f"用户 {target['username'] if target else user_id} 已删除"}
