from typing import List, AsyncGenerator, Optional
import httpx
import json
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from loguru import logger

from app.core.config import settings
from app.services.vectorstore_service import VectorStoreService
from app.services.faq_service import FAQService


class RAGService:
    """RAG 问答服务"""

    def __init__(self, vectorstore_service: VectorStoreService):
        self.vectorstore_service = vectorstore_service
        self.faq_service = FAQService()

        # 从 .env 读取默认配置（当用户未提供时使用）
        self.api_base = settings.OPENAI_API_BASE.rstrip('/')
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL

        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", """你是一个专业的知识库助手。请根据参考资料理解后用自己的话回答用户的问题。

参考资料：
{context}

回答要求：
1. **必须用中文回答所有问题**
2. 理解参考资料的含义，用清晰、自然的语言重新组织回答
3. 不要照搬原文，要提炼关键信息并用通俗易懂的方式表达
4. 如果参考资料不足以回答问题，明确说明缺少哪方面信息
5. 如果涉及数字、日期等关键信息，必须准确引用
6. 回答要简洁，避免冗余和重复
7. 如果材料有的话,你要在结尾标记来源
"""),
            ("human", "{question}")
        ])

    async def query(self, question: str, top_k: int = 4, scope: Optional[dict] = None) -> tuple[str, List[tuple[Document, float]]]:
        """查询问答（非流式，按组织隔离）"""
        try:
            # 1. 检索相关文档（按组织ID过滤）
            relevant_docs = self.vectorstore_service.search(question, top_k, scope)

            if not relevant_docs:
                return "抱歉，我在知识库中没有找到相关信息。", []

            # 2. 构建上下文
            context = self._build_context(relevant_docs)

            # 3. 生成回答
            messages = self.prompt_template.format_messages(
                context=context,
                question=question
            )

            response = await self.llm.ainvoke(messages)
            answer = response.content

            logger.info(f"问答完成，问题: {question[:50]}...")
            return answer, relevant_docs

        except Exception as e:
            logger.error(f"查询失败: {str(e)}")
            raise

    async def query_stream(
        self,
        question: str,
        top_k: int = 4,
        api_key: Optional[str] = None,
        api_base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        scope: Optional[dict] = None
    ) -> AsyncGenerator[tuple[Optional[str], Optional[List[tuple[Document, float]]]], None]:
        """
        查询问答（流式，按组织隔离）

        参数：
        - question: 用户问题
        - top_k: 检索文档数
        - api_key: 用户提供的 API Key（优先级高）
        - api_base_url: 用户提供的 API 中转地址（优先级高）
        - model: 用户选择的模型（优先级高）
        - temperature: 温度参数
        - scope: 组织ID（数据隔离）
        """
        try:
            # 打印前端传来的所有参数（调试用）
            logger.info(f"收到前端参数:")
            logger.info(f"  - question: {question[:50]}...")
            logger.info(f"  - api_key: {'有' if api_key else '无'}")
            logger.info(f"  - api_base_url: {api_base_url}")
            logger.info(f"  - model: {model}")
            logger.info(f"  - temperature: {temperature}")
            logger.info(f"  - scope: {scope}")

            # 1. 先检查 FAQ：如果问题相似度高，直接返回预设答案
            faq_answer = self.faq_service.search_faq(
                question,
                self.vectorstore_service.embeddings,
                similarity_threshold=0.85  # 相似度阈值：85% 以上直接返回
            )

            if faq_answer:
                # FAQ 命中：不检索文档，不调用 AI，直接流式返回预设答案
                logger.info(f"FAQ 命中，直接返回预设答案")
                for char in faq_answer:
                    yield char, None
                return

            # 2. 检索相关文档（按组织隔离）
            relevant_docs = self.vectorstore_service.search(question, top_k, scope)

            if not relevant_docs:
                # 没有检索到相关文档：直接返回提示，不返回 sources
                no_result_msg = "抱歉，我在知识库中没有找到相关信息。\n\n如果您想询问技术问题，我很乐意帮忙！"
                for char in no_result_msg:
                    yield char, None
                return

            # 3. 构建上下文
            context = self._build_context(relevant_docs)

            # 4. 决定使用哪个 API 配置
            logger.info("=" * 80)
            logger.info("🔍 API 配置优先级判断:")
            logger.info(f"   前端传来的 api_key: {api_key[:20] + '...' if api_key else '(None)'}")
            logger.info(f"   前端传来的 api_base_url: {api_base_url if api_base_url else '(None)'}")
            logger.info(f"   前端传来的 model: {model if model else '(None)'}")
            logger.info(f"   .env 配置的 self.api_key: {self.api_key[:20] + '...' if self.api_key else '(None)'}")
            logger.info(f"   .env 配置的 self.api_base: {self.api_base}")
            logger.info(f"   .env 配置的 self.model: {self.model}")

            if api_key is not None:
                # 用户配置了自己的 Key
                use_api_key = api_key
                use_api_base = api_base_url if api_base_url is not None else self.api_base
                use_model = model if model is not None else self.model
                logger.info(f"✅ 使用用户配置: {use_model} @ {use_api_base}")
            else:
                # 使用 .env 文件的默认配置
                use_api_key = self.api_key
                use_api_base = self.api_base
                use_model = self.model
                logger.info(f"⚠️ 使用 .env 默认配置: {use_model} @ {use_api_base}")
            logger.info("=" * 80)

            if not use_api_key:
                error_msg = "错误：未配置 API Key。请在设置中填写您的 API Key。"
                for char in error_msg:
                    yield char, None
                return

            # 5. 构建 prompt
            messages = self.prompt_template.format_messages(
                context=context,
                question=question
            )

            # 转成 OpenAI 格式
            payload = {
                "model": use_model,
                "messages": [{"role": m.type, "content": m.content} for m in messages],
                "temperature": temperature if temperature is not None else 0.7,
                "stream": True
            }

            # 先返回相关文档
            yield "", relevant_docs

            # 6. 流式调用 AI API
            async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
                async with client.stream(
                    "POST",
                    f"{use_api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {use_api_key}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue

                        data = line[6:].strip()
                        if data == "[DONE]":
                            break

                        try:
                            chunk = json.loads(data)
                            content = chunk["choices"][0]["delta"].get("content", "")
                            if content:
                                yield content, None
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

            logger.info(f"流式问答完成，问题: {question[:50]}...")

        except Exception as e:
            import traceback
            logger.error(f"流式查询失败: {type(e).__name__}: {str(e)}")
            logger.error(f"详细堆栈:\n{traceback.format_exc()}")
            raise

    def _build_context(self, docs_with_scores: List[tuple[Document, float]]) -> str:
        """构建上下文"""
        context_parts = []

        for i, (doc, score) in enumerate(docs_with_scores, 1):
            source = doc.metadata.get("source", "未知来源")
            content = doc.page_content
            context_parts.append(f"[参考资料 {i}] (来源: {source})\n{content}\n")

        return "\n".join(context_parts)
