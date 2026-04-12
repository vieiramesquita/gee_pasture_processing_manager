# core.py

import sqlite3
import json
import ee
from loguru import logger

DB_FILE = "tasks_state.db"
GEE_URL = 'https://earthengine-highvolume.googleapis.com'

logger.add("app.log", rotation="500 MB", level="INFO")

def init_gee(project_name=None):
    if not project_name:
        logger.warning("Nenhum projeto informado.")
        return False
    try:
        ee.Initialize(project=project_name, opt_url=GEE_URL)
        logger.info(f"GEE inicializado: {project_name}")
        return True
    except Exception as e:
        logger.error(f"Erro GEE: {e}")
        return False

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                name TEXT PRIMARY KEY, 
                gee_id TEXT, 
                state TEXT, 
                retries INTEGER, 
                error_msg TEXT, 
                config TEXT,
                usage_seconds REAL DEFAULT 0
            )
        """)
        # 🟢 Nova tabela para guardar a configuração do projeto
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
init_db()

# 🟢 Novas funções para salvar e recuperar o projeto
def save_setting(key, value):
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()

def get_setting(key):
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

def load_state():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM tasks").fetchall()
        tasks = [dict(r) for r in rows]
        for t in tasks:
            t["config"] = json.loads(t["config"]) if t.get("config") else {}
        return tasks

def save_state(tasks):
    try:
        with get_db() as conn: 
            if not tasks:
                conn.execute("DELETE FROM tasks")
            else:
                for t in tasks:
                    conn.execute("""
                    INSERT OR REPLACE INTO tasks (name, gee_id, state, retries, error_msg, config, usage_seconds)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    t.get("name"), t.get("gee_id"), t.get("state", "IN_QUEUE"), 
                    t.get("retries", 0), t.get("error_msg", ""), 
                    json.dumps(t.get("config", {}).to_dict() if hasattr(t.get("config"), 'to_dict') else t.get("config", {})),
                    t.get("usage_seconds", 0)
                ))
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"⚠️ Erro ao salvar banco: {e}")