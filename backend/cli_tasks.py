"""Claude CLI / Antigravity CLI 연동 작업 저장소.

CLI 훅(cli_hook_prompt.py / cli_hook_stop.py)이 등록하는 프롬프트·응답 기록을
SQLite에 보관한다. 메인 DB(DatabaseManager)와 분리된 경량 저장소로,
서버 스레드 여러 곳에서 접근하므로 연결은 호출 시마다 생성한다.
"""
import os
import sqlite3
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings", "cli_tasks.db")

VALID_TRIGGERS = ("claude_cli", "antigravity_cli")


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cli_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                prompt TEXT NOT NULL DEFAULT '',
                trigger_type TEXT NOT NULL DEFAULT 'claude_cli',
                session_id TEXT DEFAULT '',
                cwd TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'running',
                answer TEXT DEFAULT '',
                output TEXT DEFAULT '',
                model TEXT DEFAULT '',
                cli_session_id TEXT DEFAULT '',
                duration_ms INTEGER DEFAULT 0,
                log_lines TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)


def add_task(title, prompt, trigger_type="claude_cli", session_id="", cwd=""):
    if trigger_type not in VALID_TRIGGERS:
        trigger_type = "claude_cli"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO cli_tasks (title, prompt, trigger_type, session_id, cwd, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 'running', ?, ?)",
            (title, prompt, trigger_type, session_id, cwd, now, now),
        )
        return cur.lastrowid


def log_result(task_id, answer="", output="", status="done", model="",
               cli_session_id="", duration_ms=0, log_lines=None, trigger_type=None):
    fields = {
        "answer": answer or "",
        "output": output or "",
        "status": status or "done",
        "model": model or "",
        "cli_session_id": cli_session_id or "",
        "duration_ms": int(duration_ms or 0),
        "log_lines": json.dumps(log_lines or [], ensure_ascii=False),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if trigger_type in VALID_TRIGGERS:
        fields["trigger_type"] = trigger_type
    sets = ", ".join(f"{k} = ?" for k in fields)
    with _conn() as conn:
        cur = conn.execute(
            f"UPDATE cli_tasks SET {sets} WHERE id = ?",
            (*fields.values(), task_id),
        )
        return cur.rowcount > 0


def list_tasks(limit=50, trigger_type=None):
    sql = "SELECT id, title, trigger_type, session_id, status, model, duration_ms, created_at, updated_at FROM cli_tasks"
    params = []
    if trigger_type in VALID_TRIGGERS:
        sql += " WHERE trigger_type = ?"
        params.append(trigger_type)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(max(1, min(int(limit or 50), 500)))
    with _conn() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_task(task_id):
    with _conn() as conn:
        row = conn.execute("SELECT * FROM cli_tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            return None
        task = dict(row)
        try:
            task["log_lines"] = json.loads(task.get("log_lines") or "[]")
        except Exception:
            task["log_lines"] = []
        return task


def delete_task(task_id):
    with _conn() as conn:
        cur = conn.execute("DELETE FROM cli_tasks WHERE id = ?", (task_id,))
        return cur.rowcount > 0
