from typing import List

import torch
from langchain_core.embeddings import Embeddings
from transformers import AutoModel, AutoTokenizer


class LocalBGEEmbeddings(Embeddings):
    """本地 BGE 向量模型，向量化不依赖外部 API"""

    # BGE 官方建议：检索时给"问题"加上这段指令，文档本身不加
    QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："

    def __init__(self, model_name: str, batch_size: int = 32):
        # 只读本地缓存，避免每次启动都去连 huggingface.co
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
        self.model = AutoModel.from_pretrained(model_name, local_files_only=True)
        self.model.eval()
        self.batch_size = batch_size

    def _encode(self, texts: List[str]) -> List[List[float]]:
        vectors: List[List[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = self.tokenizer(
                texts[i:i + self.batch_size],
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            )
            with torch.no_grad():
                # BGE 取 [CLS] 向量并归一化
                cls = self.model(**batch).last_hidden_state[:, 0]
            vectors.extend(torch.nn.functional.normalize(cls, dim=-1).tolist())
        return vectors

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._encode(texts)

    def embed_query(self, text: str) -> List[float]:
        return self._encode([self.QUERY_INSTRUCTION + text])[0]
