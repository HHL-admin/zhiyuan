from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class DocumentUploadResponse(BaseModel):
    """文档上传响应"""
    filename: str
    size: int
    chunks: int
    message: str


class QueryRequest(BaseModel):
    """查询请求"""
    question: str = Field(..., min_length=1, description="用户问题")
    top_k: Optional[int] = Field(4, ge=1, le=10, description="返回的相关文档数量")
    api_key: Optional[str] = Field(None, description="用户自己的 API Key")
    api_base_url: Optional[str] = Field(None, description="API 中转地址")
    model: Optional[str] = Field("gpt-5.6-sol", description="AI 模型选择")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="温度参数")


class SourceDocument(BaseModel):
    """来源文档"""
    content: str
    metadata: dict
    score: Optional[float] = None


class QueryResponse(BaseModel):
    """查询响应"""
    answer: str
    sources: List[SourceDocument]
    question: str
    timestamp: datetime = Field(default_factory=datetime.now)


class DocumentListItem(BaseModel):
    """文档列表项"""
    filename: str
    size: int
    upload_time: datetime
    chunk_count: Optional[int] = None


class DocumentListResponse(BaseModel):
    """文档列表响应"""
    documents: List[DocumentListItem]
    total: int


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str = "1.0.0"
    vectorstore_status: str
