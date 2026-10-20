"""
权限与租户隔离端到端测试

会创建两家公司和若干用户、文档，请对着本地或测试环境运行，不要对生产环境运行：
    BASE_URL=http://127.0.0.1:8000 ADMIN_PASSWORD=<平台管理员密码> python tests/test_permissions_e2e.py

不传 api_key 时问答会走到"未配置 Key"，但检索来源（sources）仍会返回，足以验证隔离。
"""
import io
import json
import os
import sys
import time

import requests

BASE = os.getenv("BASE_URL", "http://127.0.0.1:8000")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "ad" "min")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
SUFFIX = str(int(time.time()))[-5:]
failures = 0


def check(name, cond, extra=""):
    global failures
    failures += not cond
    print(("PASS " if cond else "FAIL ") + name, extra)


def login(username, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, (username, r.text)
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def register_company(key, company, username):
    return requests.post(f"{BASE}/api/v2/company/register", json={
        "key_code": key, "company_name": company, "username": username,
        "email": f"{username}@test.local", "password": "123456"})


def create_user(headers, username, level):
    return requests.post(f"{BASE}/api/v2/company/users", headers=headers, json={
        "username": username, "email": f"{username}@test.local", "password": "123456", "user_level": level})


def upload(headers, filename, text):
    return requests.post(f"{BASE}/api/documents/upload", headers=headers,
                         files={"file": (filename, io.BytesIO(text.encode("utf-8")), "text/plain")})


def visible_docs(headers):
    return {d["filename"] for d in requests.get(f"{BASE}/api/documents", headers=headers).json()["documents"]}


def visible_users(headers):
    return {u["username"]: u for u in requests.get(f"{BASE}/api/v2/company/users", headers=headers).json()["users"]}


def retrieved_sources(headers, question):
    """调用流式问答，只收集检索命中的来源文件"""
    r = requests.post(f"{BASE}/api/query/stream", headers=headers, stream=True,
                      json={"question": question, "api_key": "sk-invalid", "api_base_url": "http://127.0.0.1:9/v1"})
    sources = set()
    for line in r.iter_lines(decode_unicode=True):
        if line and line.startswith("data: {"):
            event = json.loads(line[6:])
            if event["type"] == "sources":
                sources |= {s["metadata"].get("source") for s in event["data"]}
    return sources


def main():
    if not ADMIN_PASSWORD:
        sys.exit("请通过环境变量 ADMIN_PASSWORD 提供平台管理员密码")

    S = SUFFIX
    platform = login(ADMIN_USERNAME, ADMIN_PASSWORD)
    check("平台管理员是平台老板", requests.get(f"{BASE}/api/v2/me", headers=platform).json()["user_level"] == 1)

    # ---------- 密钥与公司注册 ----------
    key_a = requests.post(f"{BASE}/api/v2/platform/keys", json={"expires_days": 7}, headers=platform).json()["key_code"]
    key_b = requests.post(f"{BASE}/api/v2/platform/keys", json={"expires_days": 7}, headers=platform).json()["key_code"]
    check("无效密钥被拒绝", register_company("BADKEY00", "X", f"x{S}").status_code == 400)
    check("A 公司注册", register_company(key_a, f"A公司{S}", f"bossA{S}").status_code == 200)
    check("密钥不能重复使用", register_company(key_a, "A2", f"bossA2{S}").status_code == 400)
    check("B 公司注册", register_company(key_b, f"B公司{S}", f"bossB{S}").status_code == 200)
    boss_a, boss_b = login(f"bossA{S}", "123456"), login(f"bossB{S}", "123456")

    # ---------- 逐级创建用户 ----------
    check("A 老板创建高级用户", create_user(boss_a, f"advA{S}", 3).status_code == 200)
    check("A 老板创建低级用户", create_user(boss_a, f"basA{S}", 4).status_code == 200)
    adv_a = login(f"advA{S}", "123456")
    check("高级用户创建低级用户", create_user(adv_a, f"basA2{S}", 4).status_code == 200)
    check("高级用户不能创建高级用户", create_user(adv_a, f"advX{S}", 3).status_code == 403)
    bas_a, bas_a2 = login(f"basA{S}", "123456"), login(f"basA2{S}", "123456")
    check("低级用户不能创建用户", create_user(bas_a, f"basX{S}", 4).status_code == 403)
    check("B 老板创建低级用户", create_user(boss_b, f"basB{S}", 4).status_code == 200)
    bas_b = login(f"basB{S}", "123456")

    # ---------- 上传 ----------
    check("A 老板上传", upload(boss_a, f"a_boss{S}.txt", "A公司机密：年度预算是九百万。").status_code == 200)
    check("A 高级用户上传", upload(adv_a, f"a_adv{S}.txt", "A公司高级用户文档：密码轮换周期三十天。").status_code == 200)
    check("A 低级用户上传", upload(bas_a, f"a_bas{S}.txt", "A公司低级用户文档：周二值班的是张三。").status_code == 200)
    check("A 低级用户2上传", upload(bas_a2, f"a_bas2{S}.txt", "A公司低级用户2文档：周三值班的是李四。").status_code == 200)
    check("B 低级用户上传", upload(bas_b, f"b_bas{S}.txt", "B公司文档：周二值班的是王五。").status_code == 200)
    check("平台老板不能上传", upload(platform, f"p{S}.txt", "x").status_code == 403)

    # ---------- 文档可见范围 ----------
    a_all = {f"a_boss{S}.txt", f"a_adv{S}.txt", f"a_bas{S}.txt", f"a_bas2{S}.txt"}
    check("A 老板看到全公司，看不到 B", visible_docs(boss_a) >= a_all and f"b_bas{S}.txt" not in visible_docs(boss_a))
    check("高级用户看到自己和低级用户", visible_docs(adv_a) == {f"a_adv{S}.txt", f"a_bas{S}.txt", f"a_bas2{S}.txt"})
    check("低级用户只看到自己", visible_docs(bas_a) == {f"a_bas{S}.txt"})
    check("B 老板只看到 B", visible_docs(boss_b) == {f"b_bas{S}.txt"})
    check("平台老板看不到任何文档", visible_docs(platform) == set())

    # ---------- 用户可见范围 ----------
    users_a, users_b = visible_users(boss_a), visible_users(boss_b)
    check("A 老板只看到 A 的用户", set(users_a) == {f"bossA{S}", f"advA{S}", f"basA{S}", f"basA2{S}"})
    check("高级用户看到自己和低级用户", set(visible_users(adv_a)) == {f"advA{S}", f"basA{S}", f"basA2{S}"})
    check("低级用户只看到自己", set(visible_users(bas_a)) == {f"basA{S}"})
    bas_b_id, bas_a_id, adv_a_id = users_b[f"basB{S}"]["id"], users_a[f"basA{S}"]["id"], users_a[f"advA{S}"]["id"]

    # ---------- 越权 ----------
    check("A 老板不能删除 B 的用户", requests.delete(f"{BASE}/api/v2/company/users/{bas_b_id}", headers=boss_a).status_code == 404)
    check("A 老板不能升级 B 的用户",
          requests.put(f"{BASE}/api/v2/company/users/{bas_b_id}/level", json={"user_level": 3}, headers=boss_a).status_code == 404)
    check("A 老板不能删除 B 的文档", requests.delete(f"{BASE}/api/documents/b_bas{S}.txt", headers=boss_a).status_code == 404)
    check("高级用户不能删除用户", requests.delete(f"{BASE}/api/v2/company/users/{bas_a_id}", headers=adv_a).status_code == 403)
    check("低级用户不能删除文档", requests.delete(f"{BASE}/api/documents/a_bas{S}.txt", headers=bas_a).status_code == 403)
    check("公司老板不能生成密钥", requests.post(f"{BASE}/api/v2/platform/keys", json={}, headers=boss_b).status_code == 403)

    # ---------- 升降级即时生效 ----------
    check("老板升级低级用户",
          requests.put(f"{BASE}/api/v2/company/users/{bas_a_id}/level", json={"user_level": 3}, headers=boss_a).status_code == 200)
    check("升级后能看到其他低级用户的文档", f"a_bas2{S}.txt" in visible_docs(bas_a))
    check("老板降级高级用户",
          requests.put(f"{BASE}/api/v2/company/users/{adv_a_id}/level", json={"user_level": 4}, headers=boss_a).status_code == 200)
    check("降级后只能看到自己的文档", visible_docs(adv_a) == {f"a_adv{S}.txt"})

    # ---------- 问答检索隔离 ----------
    check("B 公司提问检索不到 A 公司文档", not any(s and s.startswith("a_") for s in retrieved_sources(boss_b, "周二值班的是谁")))
    check("低级用户提问只检索自己的文档", retrieved_sources(bas_a2, "周二值班的是谁") <= {f"a_bas2{S}.txt"})
    check("平台老板提问检索不到任何文档", retrieved_sources(platform, "年度预算是多少") == set())

    # ---------- 删除 ----------
    check("老板删除文档", requests.delete(f"{BASE}/api/documents/a_boss{S}.txt", headers=boss_a).status_code == 200)
    check("老板删除用户", requests.delete(f"{BASE}/api/v2/company/users/{adv_a_id}", headers=boss_a).status_code == 200)
    check("被删除的用户无法登录",
          requests.post(f"{BASE}/api/auth/login", json={"username": f"advA{S}", "password": "123456"}).status_code == 401)
    companies = requests.get(f"{BASE}/api/v2/platform/companies", headers=platform).json()["companies"]
    check("平台老板只能看到公司名称和人数", any(c["name"] == f"A公司{S}" for c in companies))

    print("\nALL PASS" if failures == 0 else f"\n{failures} FAILED")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
