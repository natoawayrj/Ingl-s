"""Acesso ao MySQL local via PyMySQL. Conexões curtas por request."""
import pymysql
from pymysql.cursors import DictCursor

from . import config


def get_conn():
    """Abre uma conexão nova. Feche com .close() (use o context manager abaixo)."""
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=True,
    )


def query_one(sql: str, params: tuple = ()):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()
    finally:
        conn.close()


def query_all(sql: str, params: tuple = ()):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def execute(sql: str, params: tuple = ()) -> int:
    """Executa INSERT/UPDATE/DELETE. Retorna lastrowid (INSERT) ou rowcount."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.lastrowid or cur.rowcount
    finally:
        conn.close()


def ping() -> bool:
    """Testa se o banco está no ar."""
    try:
        conn = get_conn()
        conn.ping(reconnect=False)
        conn.close()
        return True
    except Exception:
        return False
