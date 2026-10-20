import os
import secrets
import sqlite3
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from passlib.context import CryptContext
from loguru import logger


class Database:
    """SQLite 数据库管理"""

    def __init__(self, db_path: str = "./data/users.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 用户表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                organization_id INTEGER,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 旧表的 username 是全局唯一，改为允许不同公司同名（公司内唯一由业务层校验）
        table_sql = cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'users'"
        ).fetchone()[0]
        if "username TEXT UNIQUE" in table_sql:
            old_cols = [row[1] for row in cursor.execute("PRAGMA table_info(users)")]
            cursor.execute("""
                CREATE TABLE users_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    organization_id INTEGER,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cols = ", ".join(c for c in old_cols if c in (
                "id", "username", "email", "hashed_password", "role",
                "organization_id", "is_active", "created_at"))
            cursor.execute(f"INSERT INTO users_new ({cols}) SELECT {cols} FROM users")
            cursor.execute("DROP TABLE users")
            cursor.execute("ALTER TABLE users_new RENAME TO users")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
            logger.info("users 表已迁移：用户名允许跨公司重复")

        # 检查是否有管理员用户，没有则创建默认管理员
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
        admin_count = cursor.fetchone()[0]

        if admin_count == 0:
            # 首次启动创建平台管理员；初始密码取环境变量，未设置时随机生成并打印一次
            initial_password = os.getenv("ADMIN_INITIAL_PASSWORD") or secrets.token_urlsafe(12)
            hashed_password = self.pwd_context.hash(initial_password)
            cursor.execute("""
                INSERT INTO users (username, email, hashed_password, role)
                VALUES (?, ?, ?, ?)
            """, ("admin", "admin@example.com", hashed_password, "admin"))
            logger.warning(f"已创建平台管理员账号，初始密码: {initial_password}（请登录后尽快修改）")

        conn.commit()
        conn.close()

    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """生成密码哈希"""
        return self.pwd_context.hash(password)

    def create_user(self, username: str, email: str, password: str, role: str = "user") -> Optional[dict]:
        """创建用户"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            hashed_password = self.get_password_hash(password)

            cursor.execute("""
                INSERT INTO users (username, email, hashed_password, role)
                VALUES (?, ?, ?, ?)
            """, (username, email, hashed_password, role))

            user_id = cursor.lastrowid
            conn.commit()

            # 获取创建的用户
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            user = dict(cursor.fetchone())
            conn.close()

            logger.info(f"用户创建成功: {username}")
            return user

        except sqlite3.IntegrityError as e:
            logger.error(f"创建用户失败: {str(e)}")
            return None

    def get_user_by_username(self, username: str) -> Optional[dict]:
        """根据用户名获取用户"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()

        return dict(user) if user else None

    def get_users_by_username(self, username: str) -> List[dict]:
        """用户名可能在不同公司重复，返回所有同名用户"""
        conn = self.get_connection()
        rows = conn.execute("SELECT * FROM users WHERE username = ? ORDER BY id", (username,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_user_by_id(self, user_id: int) -> Optional[dict]:
        """根据ID获取用户"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()

        return dict(user) if user else None

    def get_user_by_email(self, email: str) -> Optional[dict]:
        """根据邮箱获取用户"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        return dict(user) if user else None

    def get_all_users(self) -> List[dict]:
        """获取所有用户"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
        users = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return users

    def update_user_role(self, user_id: int, role: str) -> bool:
        """更新用户角色"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
            conn.commit()
            conn.close()

            logger.info(f"用户角色更新成功: ID={user_id}, role={role}")
            return True

        except Exception as e:
            logger.error(f"更新用户角色失败: {str(e)}")
            return False

    def delete_user(self, user_id: int) -> bool:
        """删除用户"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            conn.close()

            logger.info(f"用户删除成功: ID={user_id}")
            return True

        except Exception as e:
            logger.error(f"删除用户失败: {str(e)}")
            return False

    def update_user_password(self, user_id: int, new_password: str) -> bool:
        """更新用户密码"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            hashed_password = self.get_password_hash(new_password)
            cursor.execute("UPDATE users SET hashed_password = ? WHERE id = ?",
                         (hashed_password, user_id))
            conn.commit()
            conn.close()

            logger.info(f"用户密码更新成功: ID={user_id}")
            return True

        except Exception as e:
            logger.error(f"更新用户密码失败: {str(e)}")
            return False

    def update_user_organization(self, user_id: int, organization_id: Optional[int]) -> bool:
        """更新用户所属组织（支持 None 表示移除组织）"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("UPDATE users SET organization_id = ? WHERE id = ?",
                         (organization_id, user_id))
            conn.commit()
            conn.close()

            logger.info(f"用户组织更新成功: user_id={user_id}, org_id={organization_id}")
            return True

        except Exception as e:
            logger.error(f"更新用户组织失败: {str(e)}")
            return False


# 全局数据库实例
db = Database()
