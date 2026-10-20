from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """应用配置"""

    # OpenAI 兼容 API 配置（从 .env 读取，作为默认值）
    # 用户在前端设置的配置会覆盖这些默认值
    OPENAI_API_KEY: str = ""
    OPENAI_API_BASE: str = "https://api.deepseek.com"
    OPENAI_MODEL: str = "deepseek-chat"

    # 向量模型（本地 HuggingFace 模型，向量化不依赖外部 API）
    EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"

    # 向量数据库配置（换向量模型后维度会变，必须换新目录）
    CHROMA_PERSIST_DIRECTORY: str = "./data/vectorstore_bge"

    # 文档存储
    DOCUMENTS_DIRECTORY: str = "./data/documents"

    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = True

    # CORS 配置
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # JWT 签名密钥（生产环境必须设置为随机长字符串）
    JWT_SECRET_KEY: str = ""

    # 检索配置
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    TOP_K: int = 4

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
