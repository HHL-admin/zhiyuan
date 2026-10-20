"""
层级权限系统：平台老板(1) -> 公司老板(2) -> 高级用户(3) -> 低级用户(4)

- 平台老板：生成注册密钥（只有添加功能，看不到任何公司的文档）
- 公司老板：凭密钥自助注册公司；上传/删除/查看全公司文档；创建、升级、降级、删除下级用户
- 高级用户：上传；查看自己和本公司低级用户的文档；创建低级用户
- 低级用户：上传；只看自己的文档
所有操作都限定在同一 company_id 内，跨公司一律拒绝。
"""
import sqlite3
import secrets
from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger

PLATFORM_OWNER = 1
COMPANY_OWNER = 2
ADVANCED_USER = 3
BASIC_USER = 4

LEVEL_NAMES = {
    PLATFORM_OWNER: "平台老板",
    COMPANY_OWNER: "公司老板",
    ADVANCED_USER: "高级用户",
    BASIC_USER: "低级用户",
}


class HierarchicalRBAC:
    def __init__(self, db_path: str = "./data/hierarchical_rbac.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS registration_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_code TEXT UNIQUE NOT NULL,
                created_by INTEGER NOT NULL,
                used BOOLEAN DEFAULT 0,
                used_by INTEGER,
                used_at TIMESTAMP,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                owner_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_hierarchy (
                user_id INTEGER PRIMARY KEY,
                user_level INTEGER NOT NULL,
                company_id INTEGER,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    # ==================== 注册密钥 ====================

    def generate_key(self, created_by: int, expires_days: int = 7) -> Dict:
        key_code = secrets.token_hex(4).upper()
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO registration_keys (key_code, created_by, expires_at) "
            "VALUES (?, ?, datetime('now', ?))",
            (key_code, created_by, f"+{int(expires_days)} days"),
        )
        conn.commit()
        cur.execute("SELECT * FROM registration_keys WHERE key_code = ?", (key_code,))
        row = dict(cur.fetchone())
        conn.close()
        logger.info(f"生成注册密钥 {key_code}，有效期 {expires_days} 天")
        return row

    def validate_key(self, key_code: str) -> Optional[Dict]:
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM registration_keys WHERE key_code = ? AND used = 0 "
            "AND expires_at > datetime('now')",
            (key_code.strip().upper(),),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def mark_key_used(self, key_code: str, used_by: int):
        conn = self._conn()
        conn.execute(
            "UPDATE registration_keys SET used = 1, used_by = ?, used_at = datetime('now') "
            "WHERE key_code = ?",
            (used_by, key_code.strip().upper()),
        )
        conn.commit()
        conn.close()

    def list_keys(self, created_by: int) -> List[Dict]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT k.*, c.name AS company_name FROM registration_keys k "
            "LEFT JOIN user_hierarchy h ON h.user_id = k.used_by "
            "LEFT JOIN companies c ON c.id = h.company_id "
            "WHERE k.created_by = ? ORDER BY k.created_at DESC",
            (created_by,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def delete_key(self, key_id: int, created_by: int) -> bool:
        conn = self._conn()
        cur = conn.execute(
            "DELETE FROM registration_keys WHERE id = ? AND created_by = ? AND used = 0",
            (key_id, created_by),
        )
        conn.commit()
        conn.close()
        return cur.rowcount > 0

    # ==================== 公司 ====================

    def create_company(self, name: str, owner_id: int) -> int:
        conn = self._conn()
        cur = conn.execute("INSERT INTO companies (name, owner_id) VALUES (?, ?)", (name, owner_id))
        company_id = cur.lastrowid
        conn.commit()
        conn.close()
        return company_id

    def get_company(self, company_id: int) -> Optional[Dict]:
        conn = self._conn()
        row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def list_companies(self) -> List[Dict]:
        """平台老板用：只返回公司名和人数，不含任何文档信息"""
        conn = self._conn()
        rows = conn.execute(
            "SELECT c.id, c.name, c.owner_id, c.created_at, "
            "(SELECT COUNT(*) FROM user_hierarchy h WHERE h.company_id = c.id) AS member_count "
            "FROM companies c ORDER BY c.created_at DESC"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ==================== 用户层级 ====================

    def set_user(self, user_id: int, level: int, company_id: Optional[int], created_by: Optional[int]):
        conn = self._conn()
        conn.execute(
            "INSERT OR REPLACE INTO user_hierarchy (user_id, user_level, company_id, created_by) "
            "VALUES (?, ?, ?, ?)",
            (user_id, level, company_id, created_by),
        )
        conn.commit()
        conn.close()

    def get_user(self, user_id: int) -> Optional[Dict]:
        conn = self._conn()
        row = conn.execute("SELECT * FROM user_hierarchy WHERE user_id = ?", (user_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def update_level(self, user_id: int, level: int):
        conn = self._conn()
        conn.execute("UPDATE user_hierarchy SET user_level = ? WHERE user_id = ?", (level, user_id))
        conn.commit()
        conn.close()

    def remove_user(self, user_id: int):
        conn = self._conn()
        conn.execute("DELETE FROM user_hierarchy WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

    def list_company_users(self, company_id: int, max_level_visible: int) -> List[Dict]:
        """列出公司内级别数字 >= max_level_visible 的用户（即同级或更低级）"""
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM user_hierarchy WHERE company_id = ? AND user_level >= ? "
            "ORDER BY user_level, created_at",
            (company_id, max_level_visible),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def company_user_ids(self, company_id: int, levels: List[int]) -> List[int]:
        conn = self._conn()
        marks = ",".join("?" * len(levels))
        rows = conn.execute(
            f"SELECT user_id FROM user_hierarchy WHERE company_id = ? AND user_level IN ({marks})",
            (company_id, *levels),
        ).fetchall()
        conn.close()
        return [r["user_id"] for r in rows]

    # ==================== 权限判断 ====================

    def visible_uploader_ids(self, user_id: int) -> Optional[List[int]]:
        """
        返回当前用户能看到哪些上传者的文档：
        - None 表示能看全公司（公司老板）
        - [] 表示什么都看不到（平台老板 / 未分配）
        """
        info = self.get_user(user_id)
        if not info or not info["company_id"]:
            return []
        level = info["user_level"]
        if level == COMPANY_OWNER:
            return None
        if level == ADVANCED_USER:
            return sorted(set([user_id] + self.company_user_ids(info["company_id"], [BASIC_USER])))
        return [user_id]

    def can_manage(self, actor_id: int, target_id: int) -> bool:
        """actor 能否管理 target：同公司，且 actor 级别严格高于 target"""
        actor = self.get_user(actor_id)
        target = self.get_user(target_id)
        if not actor or not target or actor_id == target_id:
            return False
        if not actor["company_id"] or actor["company_id"] != target["company_id"]:
            return False
        return actor["user_level"] < target["user_level"]


hierarchical_rbac = HierarchicalRBAC()
