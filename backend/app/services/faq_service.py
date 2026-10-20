"""FAQ 服务：预设常见问题答案，通过向量相似度快速回答"""
from typing import Optional, List, Tuple
from langchain_core.documents import Document
from loguru import logger


class FAQService:
    """FAQ 常见问题服务"""

    def __init__(self):
        # 预设的常见问题和答案
        self.faq_pairs = [
            {
                "question": "你是谁",
                "answer": "我是知识库助手,专门帮助您检索和理解技术文档。我可以回答技术问题、梳理知识点、查找资料等。😊"
            },
            {
                "question": "你能做什么",
                "answer": "我可以帮您:\n1. 检索技术文档和知识库内容\n2. 解答编程和技术相关问题\n3. 梳理和总结知识点\n4. 查找相关资料和代码示例\n\n有什么具体需求,尽管告诉我！"
            },
            {
                "question": "你好",
                "answer": "你好！我是知识库助手。有什么可以帮助你的吗？比如解答技术问题、梳理知识点等。😊"
            },
            {
                "question": "谢谢",
                "answer": "不客气！很高兴能帮到你。如果还有其他问题,随时问我。😊"
            },
            {
                "question": "你叫什么名字",
                "answer": "我是知识库助手,您可以叫我小助手。我的职责是帮助您快速找到需要的技术知识和资料。"
            },
            {
                "question": "再见",
                "answer": "再见！祝您工作顺利,有需要随时回来找我。👋"
            },
        ]

    def search_faq(
        self,
        question: str,
        embeddings,
        similarity_threshold: float = 0.85
    ) -> Optional[str]:
        """
        在 FAQ 中搜索相似问题

        Args:
            question: 用户问题
            embeddings: 向量模型
            similarity_threshold: 相似度阈值,超过此值直接返回答案

        Returns:
            如果找到高相似度问题,返回答案;否则返回 None
        """
        try:
            # 对用户问题向量化
            question_vector = embeddings.embed_query(question)

            max_similarity = 0.0
            best_answer = None

            # 遍历所有 FAQ
            for faq in self.faq_pairs:
                # 对 FAQ 问题向量化
                faq_vector = embeddings.embed_query(faq["question"])

                # 计算余弦相似度
                similarity = self._cosine_similarity(question_vector, faq_vector)

                if similarity > max_similarity:
                    max_similarity = similarity
                    best_answer = faq["answer"]

            logger.info(f"FAQ 匹配相似度: {max_similarity:.3f}, 阈值: {similarity_threshold}")

            # 如果相似度超过阈值,直接返回答案
            if max_similarity >= similarity_threshold:
                logger.info(f"FAQ 命中,直接返回答案")
                return best_answer

            return None

        except Exception as e:
            logger.error(f"FAQ 搜索失败: {e}")
            return None

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        import math

        # 点积
        dot_product = sum(a * b for a, b in zip(vec1, vec2))

        # 模长
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        # 余弦相似度
        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)
