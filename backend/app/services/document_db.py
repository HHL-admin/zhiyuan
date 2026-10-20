import sqlite3
from pathlib import Path
from typing import Optional, List, Dict
from loguru import logger


class DocumentDatabase:
    """文档元数据（按公司 + 上传者隔离）"""

    def __init__(self, db_path: str = "./data/documents.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        # 旧的 documents 表结构不兼容（缺 organization_id），改用新表
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS company_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                company_id INTEGER NOT NULL,
                uploader_id INTEGER NOT NULL,
                size INTEGER NOT NULL,
                chunk_count INTEGER DEFAULT 0,
                upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(filename, company_id)
            )
        """)
        conn.commit()
        conn.close()
        logger.info("文档数据库初始化完成")

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def add_document(self, filename: str, company_id: int, uploader_id: int, size: int, chunk_count: int) -> Optional[int]:
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM company_documents WHERE filename = ? AND company_id = ?",
                (filename, company_id),
            )
            cur.execute(
                "INSERT INTO company_documents (filename, company_id, uploader_id, size, chunk_count) "
                "VALUES (?, ?, ?, ?, ?)",
                (filename, company_id, uploader_id, size, chunk_count),
            )
            doc_id = cur.lastrowid
            conn.commit()
            conn.close()
            logger.info(f"文档记录已保存: {filename}, company={company_id}, uploader={uploader_id}")
            return doc_id
        except Exception as e:
            logger.error(f"添加文档记录失败: {str(e)}")
            raise

    def get_document(self, filename: str, company_id: int) -> Optional[Dict]:
        conn = self.get_connection()
        row = conn.execute(
            "SELECT * FROM company_documents WHERE filename = ? AND company_id = ?",
            (filename, company_id),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def list_documents(self, company_id: int, uploader_ids: Optional[List[int]] = None) -> List[Dict]:
        """uploader_ids 为 None 表示全公司"""
        if uploader_ids is not None and not uploader_ids:
            return []
        sql = "SELECT * FROM company_documents WHERE company_id = ?"
        params: list = [company_id]
        if uploader_ids is not None:
            sql += f" AND uploader_id IN ({','.join('?' * len(uploader_ids))})"
            params += list(uploader_ids)
        sql += " ORDER BY upload_time DESC"
        conn = self.get_connection()
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def delete_document(self, filename: str, company_id: int) -> bool:
        conn = self.get_connection()
        cur = conn.execute(
            "DELETE FROM company_documents WHERE filename = ? AND company_id = ?",
            (filename, company_id),
        )
        conn.commit()
        conn.close()
        return cur.rowcount > 0


document_db = DocumentDatabase()
