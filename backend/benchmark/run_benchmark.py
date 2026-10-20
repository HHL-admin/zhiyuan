"""
检索效果评测：在自建企业制度语料上对比"按关键词重合度二选一"的旧方案与 RRF 混合检索。

语料与问题均为人工构造（benchmark/corpus.json、qa.json），用于横向对比两种检索策略，
不代表线上真实流量。每次运行使用临时向量库，不会修改 data/ 下的数据。

    python benchmark/run_benchmark.py            # 打印表格并写入 benchmark/result.json
"""
import json
import os
import shutil
import sys
import tempfile
from collections import defaultdict

import jieba

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from app.core.config import settings

HERE = os.path.dirname(os.path.abspath(__file__))
TOP_K = 4
COMPANY_ID = 1
UPLOADER_ID = 1


def load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return json.load(f)


def build_store(corpus):
    tmp = tempfile.mkdtemp()
    settings.CHROMA_PERSIST_DIRECTORY = tmp
    from langchain_core.documents import Document
    from app.services.vectorstore_service import VectorStoreService

    store = VectorStoreService()
    docs = [Document(page_content=item["text"], metadata={"doc_id": item["id"]}) for item in corpus]
    store.add_documents(docs, "benchmark.txt", COMPANY_ID, UPLOADER_ID)
    return store, tmp


def old_search(store, question, scope):
    """旧方案：关键词重合度 >= 0.3 只走 TF-IDF，否则只走向量检索"""
    store._tfidf_search("warmup", 1, scope)  # 确保索引已构建
    words = list(jieba.cut(question))
    overlap = sum(w in store.tfidf_vectorizer.vocabulary_ for w in words) / len(words)
    if overlap >= 0.3:
        return "TF-IDF", store._tfidf_search(question, TOP_K, scope)
    return "向量", store._vector_search(question, TOP_K, scope)


def evaluate(store, qa, scope):
    metrics = {
        "old": {"hit": 0, "hit1": 0, "mrr": 0.0, "by_type": defaultdict(lambda: [0, 0])},
        "rrf": {"hit": 0, "hit1": 0, "mrr": 0.0, "by_type": defaultdict(lambda: [0, 0])},
    }
    details = []
    for item in qa:
        gold = set(item["gold"])
        path, old_results = old_search(store, item["q"], scope)
        new_results = store.search(item["q"], TOP_K, scope)

        row = {"question": item["q"], "type": item["type"], "gold": item["gold"], "old_path": path}
        for name, results in (("old", old_results), ("rrf", new_results)):
            ids = [d.metadata.get("doc_id") for d, _ in results]
            hit = bool(gold & set(ids))
            rank = next((i for i, g in enumerate(ids, 1) if g in gold), None)
            metrics[name]["hit"] += hit
            metrics[name]["hit1"] += bool(ids and ids[0] in gold)
            metrics[name]["mrr"] += (1.0 / rank) if rank else 0.0
            metrics[name]["by_type"][item["type"]][0] += hit
            metrics[name]["by_type"][item["type"]][1] += 1
            row[f"{name}_ids"] = ids
            row[f"{name}_hit"] = hit
        details.append(row)
    return metrics, details


def summarize(metrics, total):
    out = {}
    for name in ("old", "rrf"):
        m = metrics[name]
        out[name] = {
            "hit_rate_at_1": round(m["hit1"] / total, 4),
            "hit_rate": round(m["hit"] / total, 4),
            "mrr": round(m["mrr"] / total, 4),
            "by_type": {k: {"hit_rate": round(v[0] / v[1], 4), "n": v[1]} for k, v in m["by_type"].items()},
        }
    return out


def main():
    corpus, qa = load("corpus.json"), load("qa.json")
    store, tmp = build_store(corpus)
    scope = {"company_id": COMPANY_ID, "uploader_ids": None}
    try:
        metrics, details = evaluate(store, qa, scope)
    finally:
        del store
        shutil.rmtree(tmp, ignore_errors=True)

    result = {"corpus_size": len(corpus), "question_count": len(qa), "top_k": TOP_K,
              "strategy": summarize(metrics, len(qa)), "details": details}
    with open(os.path.join(HERE, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    s = result["strategy"]
    print(f"语料 {len(corpus)} 条，问题 {len(qa)} 条，Top-{TOP_K}\n")
    print(f"{'方案':<22}{'Hit@1':>10}{'Hit@' + str(TOP_K):>9}{'MRR':>9}")
    print(f"{'旧方案（二选一）':<18}{s['old']['hit_rate_at_1']:>11.1%}{s['old']['hit_rate']:>9.1%}{s['old']['mrr']:>9.3f}")
    print(f"{'RRF 混合检索':<20}{s['rrf']['hit_rate_at_1']:>11.1%}{s['rrf']['hit_rate']:>9.1%}{s['rrf']['mrr']:>9.3f}")
    print("\n分类型命中率：")
    for t in s["old"]["by_type"]:
        o, r = s["old"]["by_type"][t], s["rrf"]["by_type"][t]
        print(f"  {t:<8} 旧 {o['hit_rate']:>6.1%}  →  RRF {r['hit_rate']:>6.1%}  (n={r['n']})")
    worse = [d for d in details if d["old_hit"] and not d["rrf_hit"]]
    if worse:
        print("\nRRF 未命中的旧方案命中项：", [d["question"] for d in worse])
    print("\n结果已写入 benchmark/result.json")


if __name__ == "__main__":
    main()
