"""
混合检索（RRF）离线测试：在临时向量库里对比"按关键词重合度二选一"的旧方案和 RRF 融合。
不依赖后端服务，也不会改动 data/ 下的真实数据：
    python tests/test_rrf_retrieval.py
"""
import os, sys, tempfile, shutil, jieba
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
from app.core.config import settings
tmp = tempfile.mkdtemp()
settings.CHROMA_PERSIST_DIRECTORY = tmp           # 临时库，不碰真实数据
from langchain_core.documents import Document
from app.services.vectorstore_service import VectorStoreService

vs = VectorStoreService()
A = [  # 公司 1
    "周二值班的是张三，负责机房巡检。",
    "星期二轮岗人员为王五，处理客户来电。",
    "报销需在每月25号前提交发票。",
    "年假按工龄计算，满一年五天。",
    "会议室预约请提前一天在系统登记。",
]
B = ["B公司周二值班的是赵六。"]  # 公司 2，绝不能被公司 1 检索到
vs.add_documents([Document(page_content=t) for t in A], "a.txt", 1, 10)
vs.add_documents([Document(page_content=t) for t in B], "b.txt", 2, 20)
scope = {"company_id": 1, "uploader_ids": None}

def old_search(q, k=4):
    """复现旧方案：按关键词重合度二选一"""
    vs._tfidf_search("x", 1, scope)  # 触发索引构建
    words = list(jieba.cut(q))
    overlap = sum(w in vs.tfidf_vectorizer.vocabulary_ for w in words) / len(words)
    if overlap >= 0.3:
        return "TF-IDF", vs._tfidf_search(q, k, scope)
    return "向量", vs._vector_search(q, k, scope)

ok = True
for q, must in [("周二谁值班", ["张三", "王五"]), ("星期二谁轮岗", ["王五", "张三"]), ("发票什么时候交", ["25号"])]:
    path, old = old_search(q)
    new = vs.search(q, 4, scope)
    hit = lambda rs: [m for m in must if any(m in d.page_content for d, _ in rs)]
    print(f"\n问题：{q}")
    print(f"  旧方案（只走{path}）命中 {hit(old)} / 期望 {must}")
    print(f"  RRF 融合        命中 {hit(new)}")
    print("  RRF 排序：", [d.page_content[:12] for d, _ in new])
    leak = any(d.metadata.get("organization_id") != "1" for d, _ in new)
    ok &= len(hit(new)) >= len(hit(old)) and not leak
    print("  跨公司泄露：", leak)

# 低级用户范围：只能看自己（uploader 99 没有任何文档）
ok &= vs.search("周二谁值班", 4, {"company_id": 1, "uploader_ids": [99]}) == []
ok &= vs.search("周二谁值班", 4, {"company_id": 1, "uploader_ids": []}) == []
# 分数仍是距离，前端 1-score 显示相似度
ok &= all(0 <= s <= 2 for _, s in vs.search("周二谁值班", 4, scope))
print("\nRESULT:", "ALL PASS" if ok else "FAIL")
del vs; shutil.rmtree(tmp, ignore_errors=True)
sys.exit(0 if ok else 1)
