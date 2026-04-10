import sqlite3
import json
import ee
from loguru import logger

# --- CONFIGURAÇÕES ---
DB_FILE = "tasks_state.db"
GEE_URL = 'https://earthengine-highvolume.googleapis.com'

# --- LOGS ---
# Agora os erros críticos serão registrados apenas aqui
logger.add("app.log", rotation="500 MB", level="INFO")

# --- GEE ---
def init_gee(project_name=None):
    if not project_name:
        logger.warning("Nenhum projeto informado.")
        return
    try:
        ee.Initialize(project=project_name, opt_url=GEE_URL)
        logger.info(f"GEE inicializado: {project_name}")
    except Exception as e:
        logger.error(f"Erro GEE: {e}")

# --- BANCO DE DADOS (SQLite) ---
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
                usage_seconds REAL DEFAULT 0  -- 🟢 Nova Coluna
            )
        """)
init_db()

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
                    t.get("usage_seconds", 0) # 🟢 Novo valor
                ))
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"⚠️ Erro ao salvar banco: {e}")