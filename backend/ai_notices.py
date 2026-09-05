# -*- coding: utf-8 -*-
"""AI Notice — 메신저(디스코드)로 나가는 AI 알림을 함께 보관하는 저장소.

전략 이탈 감시 알림, 매매일지 AI 복기, 아침 브리핑 등이 발송될 때 여기에도
기록되어 웹/모바일의 'AI Notice' 탭에서 조회할 수 있다.
(디스코드 전송 성공 여부와 무관하게 기록된다.)
"""
import os
import json
import sqlite3
import logging
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "settings", "ai_notices.db")

CATEGORIES = ["전략감시", "복기", "브리핑"]
MAX_KEEP = 1000  # 오래된 알림 자동 정리 기준


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                category TEXT NOT NULL,      -- 전략감시 / 복기 / 브리핑
                level TEXT NOT NULL,         -- info / warning / critical / good
                title TEXT NOT NULL,
                message TEXT NOT NULL,       -- 메신저로 발송된 본문 (텍스트)
                meta_json TEXT               -- 구조화 데이터 (선택)
            )
        """)
        # 마이그레이션: market 컬럼 추가 (국내/해외 구분, 기본 국내)
        try:
            conn.execute("ALTER TABLE notices ADD COLUMN market TEXT DEFAULT 'DOMESTIC'")
        except sqlite3.OperationalError:
            pass  # 이미 존재


def add(category, title, message, level="info", meta=None, market="DOMESTIC"):
    """알림 1건 기록. 실패해도 호출 측 흐름을 막지 않는다."""
    if market not in ("DOMESTIC", "OVERSEAS"):
        market = "DOMESTIC"
    try:
        with _conn() as conn:
            conn.execute(
                "INSERT INTO notices (created_at, category, level, title, message, meta_json, market) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 str(category), str(level), str(title), str(message),
                 json.dumps(meta, ensure_ascii=False) if meta is not None else None,
                 market))
            # 오래된 알림 정리
            conn.execute(
                "DELETE FROM notices WHERE id NOT IN "
                "(SELECT id FROM notices ORDER BY id DESC LIMIT ?)", (MAX_KEEP,))
        return True
    except Exception as e:
        logging.warning(f"[AiNotices] 알림 기록 실패: {e}")
        return False


def list_notices(limit=100, category=None, after_id=None, market=None):
    """최신순 알림 목록. after_id를 주면 그 이후(신규)만 반환 (폴링용)."""
    q = "SELECT * FROM notices"
    cond, args = [], []
    if category:
        cond.append("category = ?")
        args.append(category)
    if market in ("DOMESTIC", "OVERSEAS"):
        cond.append("market = ?")
        args.append(market)
    if after_id:
        cond.append("id > ?")
        args.append(int(after_id))
    if cond:
        q += " WHERE " + " AND ".join(cond)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(max(1, min(int(limit or 100), 500)))
    with _conn() as conn:
        rows = conn.execute(q, args).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["meta"] = json.loads(d.pop("meta_json") or "null")
        except Exception:
            d["meta"] = None
        out.append(d)
    return out


def clear_all():
    with _conn() as conn:
        cur = conn.execute("DELETE FROM notices")
        return cur.rowcount
