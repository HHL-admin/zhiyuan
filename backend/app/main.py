import os

# 本地向量模型已缓存，禁止 HuggingFace 联网检查更新（在导入 transformers 之前设置）
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import sys

from app.core.config import settings
from app.api.routes import router
from app.api.auth_routes import router as auth_router
from app.api.hierarchical_routes import router as hierarchical_router

# 配置日志
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO"
)

# 创建 FastAPI 应用
app = FastAPI(
    title="RAG 知识库检索系统（用户权限管理）",
    description="基于 LangChain 和 ChromaDB 的知识库问答系统，支持特权用户和一般用户管理",
    version="2.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_router, prefix="/api/auth", tags=["认证"])
app.include_router(hierarchical_router, prefix="/api/v2", tags=["层级用户管理"])
app.include_router(router, prefix="/api", tags=["知识库"])


@app.on_event("startup")
async def startup_event():
    """启动事件"""
    # 全新部署时还没有平台老板：把最早创建的系统管理员登记为平台老板
    from app.auth.database import db
    from app.models.user_schemas import UserRole
    from app.services.hierarchical_rbac import hierarchical_rbac, PLATFORM_OWNER
    users = db.get_all_users()
    if not any((hierarchical_rbac.get_user(u["id"]) or {}).get("user_level") == PLATFORM_OWNER for u in users):
        admins = sorted((u for u in users if u["role"] == UserRole.ADMIN.value), key=lambda u: u["id"])
        if admins:
            hierarchical_rbac.set_user(admins[0]["id"], PLATFORM_OWNER, None, None)
            logger.info(f"已将系统管理员 {admins[0]['username']} 设为平台老板")
    logger.info("=" * 50)
    logger.info("RAG 知识库检索系统启动中...")
    logger.info(f"OpenAI API Base: {settings.OPENAI_API_BASE}")
    logger.info(f"Model: {settings.OPENAI_MODEL}")
    logger.info(f"Embedding Model: {settings.EMBEDDING_MODEL}")
    logger.info(f"向量存储目录: {settings.CHROMA_PERSIST_DIRECTORY}")
    logger.info(f"文档存储目录: {settings.DOCUMENTS_DIRECTORY}")
    logger.info("用户认证系统已启用")
    logger.info("=" * 50)


@app.on_event("shutdown")
async def shutdown_event():
    """关闭事件"""
    logger.info("RAG 知识库检索系统关闭")


@app.get("/")
async def root():
    """后端根路径（前端已独立部署）"""
    return {"message": "RAG 知识库检索系统 API", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD
    )
