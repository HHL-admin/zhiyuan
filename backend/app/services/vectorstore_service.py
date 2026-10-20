from typing import List, Optional, Tuple
from pathlib import Path
import jieba
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from loguru import logger

from app.core.config import settings
from app.services.local_embeddings import LocalBGEEmbeddings


class VectorStoreService:
    """向量存储服务（支持混合检索）"""

    def __init__(self):
        self.persist_directory = settings.CHROMA_PERSIST_DIRECTORY
        Path(self.persist_directory).mkdir(parents=True, exist_ok=True)

        self.embeddings = LocalBGEEmbeddings(settings.EMBEDDING_MODEL)

        self.vectorstore: Optional[Chroma] = None
        self._initialize_vectorstore()

        # TF-IDF 检索器（缓存，只在文档变更时重建）
        self.tfidf_vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix = None
        self.tfidf_documents: List[Document] = []
        self._tfidf_dirty = True  # 标记索引是否需要重建

    def _initialize_vectorstore(self):
        """初始化向量存储"""
        try:
            # BGE 向量已归一化，用余弦距离：score = 1 - 相似度
            self.vectorstore = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings,
                collection_metadata={"hnsw:space": "cosine"}
            )
            logger.info("向量存储初始化成功")
        except Exception as e:
            logger.error(f"向量存储初始化失败: {str(e)}")
            raise

    @staticmethod
    def _scope_match(meta: dict, scope: Optional[dict]) -> bool:
        """scope = {"company_id": int, "uploader_ids": Optional[list]}；uploader_ids 为 None 表示全公司"""
        if not scope or not meta:
            return False
        if meta.get("organization_id") != str(scope["company_id"]):
            return False
        uploader_ids = scope.get("uploader_ids")
        return uploader_ids is None or meta.get("uploader_id") in {str(i) for i in uploader_ids}

    @staticmethod
    def _scope_filter(scope: dict) -> dict:
        company = {"organization_id": {"$eq": str(scope["company_id"])}}
        uploader_ids = scope.get("uploader_ids")
        if uploader_ids is None:
            return company
        return {"$and": [company, {"uploader_id": {"$in": [str(i) for i in uploader_ids]}}]}

    def add_documents(self, documents: List[Document], filename: str, company_id: int, uploader_id: int) -> int:
        """添加文档到向量存储（记录公司和上传者，用于隔离）"""
        for doc in documents:
            doc.metadata["source"] = filename
            doc.metadata["organization_id"] = str(company_id)  # ChromaDB metadata 用字符串
            doc.metadata["uploader_id"] = str(uploader_id)

        self.vectorstore.add_documents(documents)
        self._tfidf_dirty = True
        logger.info(f"公司 {company_id} 用户 {uploader_id} 添加 {len(documents)} 个chunks到向量存储")
        return len(documents)

    # RRF 常数：k 越大，排名靠后的结果权重衰减越慢；60 是论文和业界的常用值
    RRF_K = 60
    # 每一路先多召回一些，再融合截断到 top_k
    CANDIDATES_PER_PATH = 20

    def search(self, query: str, top_k: int = 4, scope: Optional[dict] = None) -> List[tuple[Document, float]]:
        """
        混合检索：向量检索 + TF-IDF 两路并行召回，用 RRF（倒数排名融合）合并。

        两路分数量纲不同（余弦距离 vs TF-IDF 相似度），不能直接相加，
        RRF 只看各文档在每一路里的排名：score = Σ 1 / (k + rank)。
        返回的分数仍是原始距离（越小越相关），供前端展示相似度；排序以 RRF 为准。
        """
        if not self.vectorstore or not scope:
            return []
        if scope.get("uploader_ids") is not None and not scope["uploader_ids"]:
            return []

        vector_results = self._vector_search(query, self.CANDIDATES_PER_PATH, scope)
        keyword_results = self._tfidf_search(query, self.CANDIDATES_PER_PATH, scope)
        results = self._rrf_fuse([vector_results, keyword_results], top_k)

        logger.info(
            f"公司 {scope['company_id']} 检索：向量 {len(vector_results)} 条，"
            f"关键词 {len(keyword_results)} 条，RRF 融合后 {len(results)} 条"
        )
        return results

    def _vector_search(self, query: str, k: int, scope: dict) -> List[tuple[Document, float]]:
        """向量检索（只返回 scope 内的文档）"""
        try:
            results = self.vectorstore.similarity_search_with_score(
                query, k=k, filter=self._scope_filter(scope)
            )
        except Exception as e:
            logger.error(f"向量检索失败: {str(e)}")
            return []
        # 双保险：再按 scope 校验一遍
        return [(d, s) for d, s in results if self._scope_match(d.metadata, scope)]

    @staticmethod
    def _doc_key(doc: Document) -> tuple:
        """同一个文本块在两路里是不同的对象，用来源 + 内容判定是否同一块"""
        return (doc.metadata.get("source"), doc.page_content)

    @classmethod
    def _rrf_fuse(cls, ranked_lists: List[List[tuple[Document, float]]], top_k: int) -> List[tuple[Document, float]]:
        """RRF 融合多路已排序结果；保留每个文档在各路中的最小距离作为展示分数"""
        fused: dict = {}
        for results in ranked_lists:
            for rank, (doc, distance) in enumerate(results, start=1):
                key = cls._doc_key(doc)
                entry = fused.setdefault(key, {"doc": doc, "rrf": 0.0, "distance": float(distance)})
                entry["rrf"] += 1.0 / (cls.RRF_K + rank)
                entry["distance"] = min(entry["distance"], float(distance))

        ranked = sorted(fused.values(), key=lambda e: e["rrf"], reverse=True)[:top_k]
        return [(e["doc"], e["distance"]) for e in ranked]

    def _refresh_tfidf_index(self):
        """重建全库 TF-IDF 索引（检索时再按 scope 过滤，避免缓存串公司）"""
        try:
            results = self.vectorstore._collection.get(include=['documents', 'metadatas'])
            docs = results.get('documents') or []
            metas = results.get('metadatas') or []
            self.tfidf_documents = [
                Document(page_content=d, metadata=m or {}) for d, m in zip(docs, metas)
            ]
            if not self.tfidf_documents:
                self.tfidf_vectorizer = None
                self.tfidf_matrix = None
            else:
                corpus = [' '.join(jieba.cut(d.page_content)) for d in self.tfidf_documents]
                self.tfidf_vectorizer = TfidfVectorizer()
                self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(corpus)
            self._tfidf_dirty = False
        except Exception as e:
            logger.error(f"刷新 TF-IDF 索引失败: {str(e)}")
            self.tfidf_documents = []
            self.tfidf_vectorizer = None
            self.tfidf_matrix = None

    def _tfidf_search(self, query: str, top_k: int, scope: dict) -> List[tuple[Document, float]]:
        """TF-IDF 检索（只返回 scope 内的文档）"""
        try:
            if self._tfidf_dirty:
                self._refresh_tfidf_index()
            if not self.tfidf_documents or self.tfidf_matrix is None:
                return []
            query_vec = self.tfidf_vectorizer.transform([' '.join(jieba.cut(query))])
            similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

            results = []
            for idx in np.argsort(similarities)[::-1]:
                if similarities[idx] <= 0 or len(results) >= top_k:
                    break
                doc = self.tfidf_documents[idx]
                if self._scope_match(doc.metadata, scope):
                    results.append((doc, 1 - similarities[idx]))
            return results
        except Exception as e:
            logger.error(f"TF-IDF 检索失败: {str(e)}")
            return []

    def delete_by_source(self, filename: str, company_id: int) -> int:
        """删除某公司下某文件的所有向量"""
        collection = self.vectorstore._collection
        results = collection.get(include=['metadatas'])
        ids_to_delete = [
            id_ for id_, meta in zip(results.get('ids') or [], results.get('metadatas') or [])
            if meta and meta.get('source') == filename and meta.get('organization_id') == str(company_id)
        ]
        if ids_to_delete:
            collection.delete(ids=ids_to_delete)
            self._tfidf_dirty = True
        logger.info(f"公司 {company_id} 删除文档 {filename} 的 {len(ids_to_delete)} 个chunks")
        return len(ids_to_delete)

    def get_collection_count(self) -> int:
        """获取向量存储中的文档数量"""
        try:
            return self.vectorstore._collection.count()
        except:
            return 0

    def health_check(self) -> bool:
        """健康检查"""
        try:
            self.vectorstore._collection.count()
            return True
        except:
            return False

