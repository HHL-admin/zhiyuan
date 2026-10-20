import os
from pathlib import Path
from typing import List, BinaryIO
from datetime import datetime

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
)
from langchain_core.documents import Document
from loguru import logger

from app.core.config import settings


class DocumentService:
    """文档处理服务"""

    def __init__(self):
        self.documents_dir = Path(settings.DOCUMENTS_DIRECTORY)
        self.documents_dir.mkdir(parents=True, exist_ok=True)

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            length_function=len,
        )

    def save_file(self, filename: str, content: bytes) -> Path:
        """保存上传的文件"""
        file_path = self.documents_dir / filename

        with open(file_path, "wb") as f:
            f.write(content)

        logger.info(f"文件已保存: {file_path}")
        return file_path

    def load_document(self, file_path: Path) -> List[Document]:
        """根据文件类型加载文档"""
        suffix = file_path.suffix.lower()

        try:
            if suffix == ".pdf":
                loader = PyPDFLoader(str(file_path))
            elif suffix == ".docx":
                loader = Docx2txtLoader(str(file_path))
            elif suffix in (".txt", ".md"):
                # Markdown 按纯文本处理；中文 Windows 下的文本常是 GBK，UTF-8 解不开时按 GB18030 读
                raw = file_path.read_bytes()
                try:
                    text = raw.decode("utf-8-sig")
                except UnicodeDecodeError:
                    text = raw.decode("gb18030")
                documents = [Document(page_content=text, metadata={"source": str(file_path)})]
                logger.info(f"文档加载成功: {file_path.name}")
                return documents
            else:
                raise ValueError(f"不支持的文件类型: {suffix}")

            documents = loader.load()
            logger.info(f"文档加载成功: {file_path.name}, 页数/段落数: {len(documents)}")
            return documents

        except Exception as e:
            logger.error(f"加载文档失败: {file_path.name}, 错误: {str(e)}")
            raise

    def split_documents(self, documents: List[Document]) -> List[Document]:
        """分割文档为chunks"""
        chunks = self.text_splitter.split_documents(documents)
        logger.info(f"文档已分割为 {len(chunks)} 个chunks")
        return chunks

    def list_documents(self) -> List[dict]:
        """列出所有已上传的文档"""
        documents = []

        for file_path in self.documents_dir.iterdir():
            if file_path.is_file() and not file_path.name.startswith('.'):
                stat = file_path.stat()
                documents.append({
                    "filename": file_path.name,
                    "size": stat.st_size,
                    "upload_time": datetime.fromtimestamp(stat.st_mtime)
                })

        documents.sort(key=lambda x: x["upload_time"], reverse=True)
        return documents

    def delete_document(self, filename: str) -> bool:
        """删除文档"""
        file_path = self.documents_dir / filename

        if file_path.exists():
            file_path.unlink()
            logger.info(f"文档已删除: {filename}")
            return True

        return False
