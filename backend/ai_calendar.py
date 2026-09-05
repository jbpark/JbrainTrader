# -*- coding: utf-8 -*-
"""AI 캘린더 — 날짜별 주요 일정과 관련 종목, 일정 기반 매매 타이밍을 AI에게 묻는다.

AI 종목(ai_picks) / AI 매매(ai_trades)와 같은 구조(프로파일 + Claude CLI 실행)이며,
결과는 일정(events)과 일정 기반 관심 종목(watchlist) 두 가지로 받는다.
"""
import os
import re
import json
import shutil
import sqlite3
import logging
import threading
import subprocess
from datetime import datetime

try:
    from backend.ai_picks import AVAILABLE_MODELS, DEFAULT_MODEL, RUN_TIMEOUT_SEC
except ImportError:
    from ai_picks import AVAILABLE_MODELS, DEFAULT_MODEL, RUN_TIMEOUT_SEC

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings", "ai_calendar.db")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0

DEFAULT_PROFILES = [
    {
        "name": "이번달_주요일정",
        "prompt": (
            "앞으로 한 달간 한국 증시에 영향을 줄 주요 일정을 날짜별로 정리해줘.\n"
            "실적 발표, 금통위·FOMC 등 통화정책, 지수 정기변경, 배당 기준일, "
            "대형 공시나 이벤트, 주요 경제지표 발표를 포함해줘.\n"
            "각 일정마다 영향을 받을 종목과 그 이유를 함께 알려주고, "
            "일정을 활용해 언제 매수하고 언제 매도하면 좋을지 구체적으로 제시해줘."
        ),
    },
]

OUTPUT_FORMAT_GUIDE = """

## 출력 형식 (반드시 준수)
- 대상은 한국 주식(코스피/코스닥)이다.
- 오늘 날짜를 기준으로 일정과 최신 정보는 반드시 웹 검색으로 확인하라.
- 날짜는 모두 YYYY-MM-DD 형식으로 쓰라. 기간 일정은 시작일로 적으라.
- 결과는 아래 JSON 형식만 출력하라. JSON 앞뒤에 다른 설명 문장을 붙이지 마라.

```json
{"calendar": {
  "events": [
    {
      "date": "2026-08-20",
      "title": "삼성전자 2분기 실적 발표",
      "category": "실적",
      "importance": "높음",
      "description": "일정 내용과 시장에 주는 의미를 1~2문장으로",
      "stocks": [
        {"ticker": "005930", "name": "삼성전자", "impact": "긍정",
         "reason": "이 일정이 이 종목에 미치는 영향 1문장"}
      ]
    }
  ],
  "watchlist": [
    {
      "ticker": "005930",
      "name": "삼성전자",
      "event_date": "2026-08-20",
      "event": "2분기 실적 발표",
      "buy_timing": "실적 발표 3거래일 전인 8/17 전후 분할 매수",
      "sell_timing": "발표 당일 장중 급등 시 절반, 나머지는 8/25까지 청산",
      "target_price": 300000,
      "stop_loss": 262000,
      "expected_return": "+9%",
      "confidence": "중간",
      "reason": "이 타이밍을 제시한 근거 1~2문장"
    }
  ]
}}
```

- category: "실적" | "정책" | "지수" | "배당" | "공시" | "경제지표" | "기타"
- importance / confidence: "높음" | "중간" | "낮음"
- impact: "긍정" | "부정" | "중립"
- target_price / stop_loss: 숫자(원 단위). 판단이 어려우면 null
- events는 날짜순으로 10~20개, watchlist는 5~10개 제시하라.
- events의 각 stocks는 1~4개, 종목코드 6자리를 정확히 쓰라.
"""


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                prompt TEXT NOT NULL,
                model TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                profile_id INTEGER PRIMARY KEY,
                status TEXT NOT NULL,          -- running / done / error
                events_json TEXT,
                watchlist_json TEXT,
                raw_text TEXT,
                error TEXT,
                model TEXT,
                started_at TEXT,
                finished_at TEXT
            )
        """)
        # 마이그레이션: market 컬럼 추가 (국내/해외 구분, 기본 국내)
        try:
            conn.execute("ALTER TABLE profiles ADD COLUMN market TEXT DEFAULT 'DOMESTIC'")
        except sqlite3.OperationalError:
            pass  # 이미 존재
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for p in DEFAULT_PROFILES:
            conn.execute(
                "INSERT OR IGNORE INTO profiles (name, prompt, model, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (p["name"], p["prompt"], DEFAULT_MODEL, now, now))


def _valid_model(model):
    model = (model or "").strip()
    return model if model in {m["id"] for m in AVAILABLE_MODELS} else DEFAULT_MODEL


def list_profiles():
    with _conn() as conn:
        rows = conn.execute("""
            SELECT p.*, r.status AS last_status, r.finished_at AS last_finished_at
            FROM profiles p LEFT JOIN results r ON r.profile_id = p.id
            ORDER BY p.id
        """).fetchall()
    return [dict(r) for r in rows]


def _valid_market(market):
    return market if market in ("DOMESTIC", "OVERSEAS") else "DOMESTIC"


def add_profile(name, prompt, model=None, market=None):
    name = (name or "").strip()
    if not name or not (prompt or "").strip():
        raise ValueError("이름과 프롬프트를 입력하세요.")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO profiles (name, prompt, model, market, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (name, prompt.strip(), _valid_model(model), _valid_market(market), now, now))
        return cur.lastrowid


def update_profile(profile_id, name, prompt, model=None, market=None):
    name = (name or "").strip()
    if not name or not (prompt or "").strip():
        raise ValueError("이름과 프롬프트를 입력하세요.")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as conn:
        if market is None:
            cur = conn.execute(
                "UPDATE profiles SET name = ?, prompt = ?, model = ?, updated_at = ? WHERE id = ?",
                (name, prompt.strip(), _valid_model(model), now, profile_id))
        else:
            cur = conn.execute(
                "UPDATE profiles SET name = ?, prompt = ?, model = ?, market = ?, updated_at = ? WHERE id = ?",
                (name, prompt.strip(), _valid_model(model), _valid_market(market), now, profile_id))
        return cur.rowcount > 0


def delete_profile(profile_id):
    with _conn() as conn:
        conn.execute("DELETE FROM results WHERE profile_id = ?", (profile_id,))
        cur = conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        return cur.rowcount > 0


def get_result(profile_id):
    with _conn() as conn:
        row = conn.execute("SELECT * FROM results WHERE profile_id = ?", (profile_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    for key, col in (("events", "events_json"), ("watchlist", "watchlist_json")):
        try:
            d[key] = json.loads(d.pop(col) or "[]")
        except Exception:
            d[key] = []
    # 일정은 날짜순, 관심 종목은 일정 날짜순으로 정렬해 그대로 쓸 수 있게 한다
    d["events"] = sorted(d["events"], key=lambda e: str(e.get("date") or "9999"))
    d["watchlist"] = sorted(d["watchlist"], key=lambda w: str(w.get("event_date") or "9999"))
    # 일정에서 파생 — 앞으로의 일정에 긍정 영향을 받는 종목
    d["upside_stocks"] = build_upside_stocks(d["events"])
    return d


_IMPORTANCE_SCORE = {"높음": 3, "중간": 2, "낮음": 1}


def build_upside_stocks(events, today=None):
    """일정에서 '긍정' 영향을 받는 종목을 모아 상승 기대 종목 목록을 만든다.

    지난 일정은 제외하고, 여러 일정에서 반복 언급되거나 중요도가 높은 일정에
    걸린 종목일수록 위로 오도록 점수를 매긴다.
    """
    today = today or datetime.now().strftime("%Y-%m-%d")
    by_key = {}
    for e in events or []:
        date = str(e.get("date") or "")
        if date < today:
            continue
        importance = str(e.get("importance") or "중간")
        for s in e.get("stocks") or []:
            if str(s.get("impact")) != "긍정":
                continue
            key = str(s.get("ticker") or s.get("name") or "").strip()
            if not key:
                continue
            item = by_key.setdefault(key, {
                "ticker": str(s.get("ticker") or ""),
                "name": str(s.get("name") or ""),
                "score": 0,
                "nearest_date": date,
                "events": [],
            })
            item["score"] += _IMPORTANCE_SCORE.get(importance, 2)
            if date < item["nearest_date"]:
                item["nearest_date"] = date
            item["events"].append({
                "date": date,
                "title": str(e.get("title") or ""),
                "category": str(e.get("category") or ""),
                "importance": importance,
                "reason": str(s.get("reason") or ""),
            })
    out = list(by_key.values())
    for it in out:
        it["event_count"] = len(it["events"])
        it["events"].sort(key=lambda x: x["date"])
    # 점수 높은 순 → 가장 가까운 일정 순
    out.sort(key=lambda x: (-x["score"], x["nearest_date"]))
    return out


def _save_result(profile_id, **fields):
    cols = ", ".join(f"{k} = ?" for k in fields)
    with _conn() as conn:
        cur = conn.execute(f"UPDATE results SET {cols} WHERE profile_id = ?",
                           (*fields.values(), profile_id))
        if cur.rowcount == 0:
            keys = ["profile_id"] + list(fields.keys())
            conn.execute(
                f"INSERT INTO results ({', '.join(keys)}) VALUES ({', '.join('?' * len(keys))})",
                (profile_id, *fields.values()))


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _clean_events(raw_events):
    out = []
    for e in raw_events or []:
        if not isinstance(e, dict):
            continue
        date = str(e.get("date") or "").strip()
        if not _DATE_RE.match(date):
            continue          # 날짜가 없으면 캘린더에 놓을 수 없다
        stocks = []
        for s in e.get("stocks") or []:
            if not isinstance(s, dict):
                continue
            stocks.append({
                "ticker": str(s.get("ticker") or "").strip(),
                "name": str(s.get("name") or "").strip(),
                "impact": str(s.get("impact") or "중립").strip(),
                "reason": str(s.get("reason") or "").strip(),
            })
        out.append({
            "date": date,
            "title": str(e.get("title") or "").strip(),
            "category": str(e.get("category") or "기타").strip(),
            "importance": str(e.get("importance") or "중간").strip(),
            "description": str(e.get("description") or "").strip(),
            "stocks": stocks,
        })
    return out


def _clean_watchlist(raw_items):
    out = []
    for w in raw_items or []:
        if not isinstance(w, dict):
            continue
        out.append({
            "ticker": str(w.get("ticker") or "").strip(),
            "name": str(w.get("name") or "").strip(),
            "event_date": str(w.get("event_date") or "").strip(),
            "event": str(w.get("event") or "").strip(),
            "buy_timing": str(w.get("buy_timing") or "").strip(),
            "sell_timing": str(w.get("sell_timing") or "").strip(),
            "target_price": w.get("target_price"),
            "stop_loss": w.get("stop_loss"),
            "expected_return": str(w.get("expected_return") or "").strip(),
            "confidence": str(w.get("confidence") or "중간").strip(),
            "reason": str(w.get("reason") or "").strip(),
        })
    return out


def _extract_calendar(text):
    """응답에서 {"calendar": {"events": [...], "watchlist": [...]}} 추출"""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidates = [m.group(1)] if m else []
    if "{" in text and "}" in text:
        candidates.append(text[text.index("{"):text.rindex("}") + 1])
    for c in candidates:
        try:
            obj = json.loads(c)
        except Exception:
            continue
        cal = obj.get("calendar") if isinstance(obj, dict) else None
        if isinstance(cal, dict):
            return _clean_events(cal.get("events")), _clean_watchlist(cal.get("watchlist"))
    return None, None


def _run_worker(profile_id, prompt, model):
    now = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today = datetime.now().strftime("%Y-%m-%d")
    full_prompt = (f"## 오늘 날짜\n{today}\n\n## 요청\n"
                   + prompt.strip() + OUTPUT_FORMAT_GUIDE)
    claude_bin = shutil.which("claude")
    if not claude_bin:
        _save_result(profile_id, status="error",
                     error="Claude CLI를 찾을 수 없습니다. PATH에 claude가 있는지 확인하세요.",
                     finished_at=now())
        return
    try:
        proc = subprocess.run(
            [claude_bin, "-p", full_prompt, "--model", model,
             "--allowedTools", "WebSearch,WebFetch"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=RUN_TIMEOUT_SEC, creationflags=_NO_WINDOW,
        )
        raw = (proc.stdout or "").strip()
        if proc.returncode != 0 or not raw:
            err = (proc.stderr or "").strip()[:500] or "Claude CLI 실행 실패 (응답 없음)"
            _save_result(profile_id, status="error", error=err, raw_text=raw, finished_at=now())
            return
        events, watchlist = _extract_calendar(raw)
        if events is None:
            _save_result(profile_id, status="error",
                         error="응답에서 캘린더 JSON을 찾지 못했습니다. 원문을 확인하세요.",
                         raw_text=raw, finished_at=now())
            return
        _save_result(profile_id, status="done",
                     events_json=json.dumps(events, ensure_ascii=False),
                     watchlist_json=json.dumps(watchlist, ensure_ascii=False),
                     raw_text=raw, error=None, finished_at=now())
        logging.info(f"[AiCalendar] 프로파일 {profile_id} 실행 완료: "
                     f"일정 {len(events)}건, 관심 종목 {len(watchlist)}건")
    except subprocess.TimeoutExpired:
        _save_result(profile_id, status="error",
                     error=f"실행 시간 초과 ({RUN_TIMEOUT_SEC}초)", finished_at=now())
    except Exception as e:
        _save_result(profile_id, status="error", error=str(e), finished_at=now())


def run_profile(profile_id):
    """실행 시작 (백그라운드). 이미 실행 중이면 False."""
    with _conn() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if not row:
            raise ValueError("프로파일이 없습니다.")
        cur = conn.execute("SELECT status FROM results WHERE profile_id = ?",
                           (profile_id,)).fetchone()
        if cur and cur["status"] == "running":
            return False
    model = _valid_model(row["model"])
    _save_result(profile_id, status="running", error=None, events_json=None,
                 watchlist_json=None, raw_text=None, model=model,
                 started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), finished_at=None)
    threading.Thread(target=_run_worker, args=(profile_id, row["prompt"], model),
                     daemon=True).start()
    return True
