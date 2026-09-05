"""도우미 채팅 백엔드 — Claude CLI(claude -p) 기반 대화.

easy_project4의 handle_chat_stream 방식을 이식한 것으로, 대시보드의 도우미
마스코트 채팅창이 사용한다. Claude CLI를 stream-json 모드로 실행해
토큰 단위 델타를 SSE(event: delta/replace/done/error)로 흘려보낸다.
대화 이력은 SQLite(chat_messages)에 보관한다.
"""
import os
import re
import json
import shutil
import sqlite3
import subprocess
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings", "helper_chat.db")

# 채팅용 claude subprocess가 콘솔 창을 띄우지 않도록 하는 플래그 (Windows)
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0

SYSTEM_PROMPT = """당신은 jbrain_trader(단타 매매 시스템) 웹 대시보드의 도우미입니다.

## 시스템 개요
- 한국 주식 자동매매/모의매매 시스템 (키움증권, 한국투자증권 KIS 지원)
- 웹 대시보드 탭: 계정, 로그, 보유종목, 관심종목, 데이터, 전략, 수집기, 매매일지, CLI 작업, 환경 설정
- 전략: strategy/ 폴더의 INI 형식 텍스트 파일로 정의 (예: 마틴게일 복합 전략 COMPLEX_MARTINGALE_PYRAMID)
- 백테스트, 모의매매, 실전매매와 틱/분봉 데이터 수집 기능 제공
- CLI 작업 탭: Claude CLI / Antigravity CLI에서 이 프로젝트에 실행한 작업 기록 조회

## 응답 규칙
- 한국어로 간결하게 2~3문장으로 답변한다.
- 시스템 사용법과 기능 안내 중심으로 답한다.
- 특정 종목의 매수/매도 추천 등 투자 판단은 하지 않는다.
"""


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


def get_history(limit=50):
    with _conn() as conn:
        rows = conn.execute(
            "SELECT role, text FROM chat_messages ORDER BY id DESC LIMIT ?",
            (max(1, min(int(limit or 50), 200)),),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def add_message(role, text):
    if role not in ("user", "assistant") or not (text or "").strip():
        return False
    with _conn() as conn:
        conn.execute(
            "INSERT INTO chat_messages (role, text, created_at) VALUES (?, ?, ?)",
            (role, text.strip(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
    return True


def clear_history():
    with _conn() as conn:
        conn.execute("DELETE FROM chat_messages")


def _sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def stream_chat(message, history=None):
    """SSE 문자열 제너레이터. Claude CLI가 없거나 실패하면 error 이벤트를 보낸다."""
    message = (message or "").strip()
    if not message:
        yield _sse("error", {"error": "빈 메시지"})
        return

    claude_bin = shutil.which("claude")
    if not claude_bin:
        yield _sse("error", {"error": "Claude CLI를 찾을 수 없습니다. PATH에 claude가 있는지 확인하세요."})
        return

    conv_lines = []
    for h in (history or [])[-6:]:
        role = h.get("role", "")
        text = (h.get("text") or "").strip()
        if not text:
            continue
        conv_lines.append(("사용자" if role == "user" else "도우미") + f": {text}")

    parts = [SYSTEM_PROMPT]
    if conv_lines:
        parts.append("\n## 이전 대화\n" + "\n".join(conv_lines))
    parts.append(f"\n## 현재 질문\n{message}")
    full_prompt = "\n".join(parts)

    model = os.environ.get("JBRAIN_CHAT_MODEL", "haiku")
    done_sent = False
    try:
        proc = subprocess.Popen(
            [claude_bin, "-p", full_prompt, "--model", model,
             "--output-format", "stream-json",
             "--verbose", "--include-partial-messages"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            creationflags=_NO_WINDOW,
        )
        full_text = ""
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            msg_type = obj.get("type")
            if msg_type == "assistant":
                for block in (obj.get("message") or {}).get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "text":
                        new_text = block.get("text", "")
                        if len(new_text) > len(full_text):
                            yield _sse("delta", {"text": new_text[len(full_text):]})
                            full_text = new_text
            elif msg_type == "result":
                result_text = obj.get("result", "")
                if result_text and not full_text:
                    full_text = result_text
                    yield _sse("delta", {"text": result_text})
                yield _sse("done", {"text": full_text})
                done_sent = True
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        if not done_sent:
            err = (proc.stderr.read() or "").strip()[:300] if proc.stderr else ""
            yield _sse("error", {"error": err or "Claude CLI 응답이 없습니다."})
    except Exception as e:
        yield _sse("error", {"error": str(e)})
