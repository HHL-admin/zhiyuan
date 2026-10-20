from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import Optional
import json
from pathlib import Path
from loguru import logger

from app.models.schemas import (
    DocumentUploadResponse,
    QueryRequest,
    QueryResponse,
    SourceDocument,
    HealthResponse
)
from app.models.user_schemas import User
from app.auth.jwt import get_current_user
from app.auth.database import db
from app.services.document_service import DocumentService
from app.services.vectorstore_service import VectorStoreService
from app.services.rag_service import RAGService
from app.services.document_db import document_db
from app.services.hierarchical_rbac import hierarchical_rbac, COMPANY_OWNER
from app.core.config import settings

router = APIRouter()

# 初始化服务
document_service = DocumentService()
vectorstore_service = VectorStoreService()
rag_service = RAGService(vectorstore_service)


def _doc_scope(user: User) -> Optional[dict]:
    """当前用户可见的文档范围；平台老板/未分配层级的账号返回 None（什么都看不到）"""
    info = hierarchical_rbac.get_user(user.id)
    if not info or not info["company_id"]:
        return None
    return {
        "company_id": info["company_id"],
        "uploader_ids": hierarchical_rbac.visible_uploader_ids(user.id),
        "level": info["user_level"],
    }


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    vectorstore_status = "healthy" if vectorstore_service.health_check() else "unhealthy"

    return HealthResponse(
        status="healthy",
        vectorstore_status=vectorstore_status
    )


@router.get("/stats")
async def get_stats(current_user: User = Depends(get_current_user)):
    """统计信息：当前用户可见范围内的文档数、知识块数"""
    scope = _doc_scope(current_user)
    docs = document_db.list_documents(scope["company_id"], scope["uploader_ids"]) if scope else []
    company = hierarchical_rbac.get_company(scope["company_id"]) if scope else None
    return {
        "document_count": len(docs),
        "chunk_count": sum(d.get("chunk_count", 0) for d in docs),
        "organization_name": company["name"] if company else None,
        "vectorstore_status": "healthy" if vectorstore_service.health_check() else "unhealthy"
    }


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """上传文档（公司内所有级别都可上传）：保存 -> 解析 -> 分块 -> 向量化"""
    scope = _doc_scope(current_user)
    if not scope:
        raise HTTPException(status_code=403, detail="当前账号不属于任何公司，不能上传文档")

    filename = Path(file.filename or "").name
    allowed_extensions = {".pdf", ".txt", ".md", ".docx"}
    if Path(filename).suffix.lower() not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型。支持的类型: {', '.join(allowed_extensions)}"
        )

    company_id = scope["company_id"]
    existing = document_db.get_document(filename, company_id)
    if existing and existing["uploader_id"] != current_user.id and scope["level"] != COMPANY_OWNER:
        raise HTTPException(status_code=400, detail="公司内已有同名文档，请改名后再上传")

    content = await file.read()
    try:
        # 每个公司单独目录，避免不同公司同名文件互相覆盖
        company_dir = Path(settings.DOCUMENTS_DIRECTORY) / f"company_{company_id}"
        company_dir.mkdir(parents=True, exist_ok=True)
        file_path = company_dir / filename
        file_path.write_bytes(content)

        documents = document_service.load_document(file_path)
        chunks = document_service.split_documents(documents)

        # 同名重传：先清掉本公司旧向量，归属保持原上传者
        vectorstore_service.delete_by_source(filename, company_id)
        uploader_id = existing["uploader_id"] if existing else current_user.id
        chunk_count = vectorstore_service.add_documents(chunks, filename, company_id, uploader_id)
        document_db.add_document(filename, company_id, uploader_id, len(content), chunk_count)
    except Exception as e:
        logger.error(f"上传失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")

    return DocumentUploadResponse(
        filename=filename,
        size=len(content),
        chunks=chunk_count,
        message="文档上传并向量化成功，可用于智能问答"
    )


@router.get("/documents")
async def list_documents(current_user: User = Depends(get_current_user)):
    """文档列表：老板看全公司，高级用户看自己+低级用户，低级用户只看自己"""
    scope = _doc_scope(current_user)
    if not scope:
        return {"documents": [], "total": 0}
    result = []
    for d in document_db.list_documents(scope["company_id"], scope["uploader_ids"]):
        uploader = db.get_user_by_id(d["uploader_id"])
        result.append({
            "filename": d["filename"],
            "size": d["size"],
            "chunk_count": d["chunk_count"],
            "upload_time": d["upload_time"],
            "uploader_id": d["uploader_id"],
            "uploader": uploader["username"] if uploader else "(已删除用户)",
        })
    return {"documents": result, "total": len(result)}


@router.delete("/documents/{filename}")
async def delete_document(
    filename: str,
    current_user: User = Depends(get_current_user)
):
    """删除文档（仅公司老板，只能删本公司的）"""
    scope = _doc_scope(current_user)
    if not scope or scope["level"] != COMPANY_OWNER:
        raise HTTPException(status_code=403, detail="仅公司老板可以删除文档")

    filename = Path(filename).name
    company_id = scope["company_id"]
    if not document_db.get_document(filename, company_id):
        raise HTTPException(status_code=404, detail="文档不存在或无权删除")

    try:
        vectorstore_service.delete_by_source(filename, company_id)
        file_path = Path(settings.DOCUMENTS_DIRECTORY) / f"company_{company_id}" / filename
        if file_path.exists():
            file_path.unlink()
        document_db.delete_document(filename, company_id)
    except Exception as e:
        logger.error(f"删除文档失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除文档失败: {str(e)}")

    logger.info(f"文档删除成功: {filename}, 用户: {current_user.username}")
    return {"message": f"文档 {filename} 删除成功"}


@router.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    current_user: User = Depends(get_current_user)
):
    """查询问答（非流式）- 只检索自己可见范围内的文档"""
    try:
        answer, relevant_docs = await rag_service.query(
            request.question, request.top_k or settings.TOP_K, _doc_scope(current_user)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")

    return QueryResponse(
        answer=answer,
        sources=[
            SourceDocument(content=doc.page_content, metadata=doc.metadata, score=float(score))
            for doc, score in relevant_docs
        ],
        question=request.question
    )


@router.post("/query/stream")
async def query_stream(
    request: QueryRequest,
    current_user: User = Depends(get_current_user)
):
    """查询问答（流式）- 只检索自己可见范围内的文档"""
    scope = _doc_scope(current_user)
    logger.info(
        f"[query/stream] user={current_user.username} scope={scope} "
        f"api_key={'有' if request.api_key else '无'} base={request.api_base_url or '-'} model={request.model or '-'}"
    )

    def sse(event_type: str, data) -> str:
        return f"data: {json.dumps({'type': event_type, 'data': data}, ensure_ascii=False)}\n\n"

    async def generate():
        try:
            async for content, docs in rag_service.query_stream(
                request.question,
                request.top_k or settings.TOP_K,
                request.api_key,  # 传递用户的 API Key
                request.api_base_url,  # 传递 API 中转地址
                request.model,     # 传递模型选择
                request.temperature, # 传递温度参数
                scope              # 可见文档范围（公司 + 上传者）
            ):
                if docs:
                    yield sse("sources", [
                        {"content": d.page_content, "metadata": d.metadata, "score": float(s)}
                        for d, s in docs
                    ])
                if content:
                    yield sse("content", content)
        except Exception as e:
            yield sse("error", f"查询失败: {str(e)}")
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"}
    )
