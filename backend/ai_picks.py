# -*- coding: utf-8 -*-
"""AI 추천 종목 — 프롬프트 프로파일 관리 및 Claude CLI 실행.

프로파일(이름+프롬프트)을 SQLite에 보관하고, 실행 시 Claude CLI(claude -p)로
프롬프트를 실행해 JSON 형식의 종목 목록을 파싱한다. 실행은 백그라운드
스레드에서 진행되며 프론트엔드는 결과를 폴링한다.
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

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings", "ai_picks.db")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0

RUN_TIMEOUT_SEC = 900  # 웹 검색 + 고성능 모델(턴이 수 분 소요될 수 있음) 고려

# 선택 가능한 AI 모델 (성능이 좋은 순서)
AVAILABLE_MODELS = [
    {"id": "claude-fable-5", "label": "Fable 5 (최고 성능)"},
    {"id": "claude-opus-5", "label": "Opus 5"},
    {"id": "claude-sonnet-5", "label": "Sonnet 5"},
    {"id": "claude-haiku-4-5", "label": "Haiku 4.5 (빠름/저비용)"},
]
DEFAULT_MODEL = "claude-opus-5"

DEFAULT_PROFILES = [
    {
        "name": "주가_재무기반",
        "prompt": (
            "현재 주가를 기준으로 재무상태가 건전하고 상승여력이 좋은 종목을 10개 선별해줘.\n"
            "출력은 코스피/코스닥 구분 및 현재 주가와 상승 여력을 표시해줘."
        ),
    },
]

OUTPUT_FORMAT_GUIDE = """

## 출력 형식 (반드시 준수)
- 대상은 한국 주식(코스피/코스닥)이다.
- 최신 주가와 재무 정보는 웹 검색으로 확인하라.
- 결과는 아래 JSON 형식만 출력하라. JSON 앞뒤에 다른 설명 문장을 붙이지 마라.

```json
{"stocks": [
  {"market": "코스피", "name": "삼성전자", "ticker": "005930",
   "price": 276000, "upside": "+15%", "reason": "선정 근거 1문장"}
]}
```

- market: "코스피" 또는 "코스닥"
- ticker: 6자리 종목코드 (문자열)
- price: 현재 주가 (숫자, 원 단위)
- upside: 상승 여력 (예: "+15%")
- reason: 선정 근거 요약 1문장
"""

COMPARE_FORMAT_GUIDE = """

## 요청
위 종목들의 재무제표와 투자 지표를 비교 분석하라. 최신 정보는 웹 검색으로 확인하라.

## 출력 형식 (반드시 준수)
- 결과는 아래 JSON 형식만 출력하라. JSON 앞뒤에 다른 설명 문장을 붙이지 마라.
- 모든 금액은 **억원 단위 숫자**, 비율은 **% 숫자**로만 표기하라 (단위 문자·쉼표 금지).
- 값을 확인할 수 없으면 null을 넣어라. 추정치를 지어내지 마라.

```json
{"comparison": [
  {"ticker": "005930", "name": "삼성전자", "market": "코스피",
   "price": 276000, "market_cap": 4500000, "per": 12.5, "pbr": 1.2, "roe": 10.5,
   "revenue": 3000000, "operating_profit": 300000, "net_income": 250000,
   "operating_margin": 15.2, "debt_ratio": 45.3, "revenue_growth": 8.5,
   "dividend_yield": 2.1, "foreign_ownership": 52.3,
   "week52_high": 280000, "week52_low": 190000,
   "comment": "재무 상태와 투자 매력도 한 줄 총평"}
]}
```

- market_cap / revenue / operating_profit / net_income: 억원 단위 숫자
- per / pbr / roe / operating_margin / debt_ratio / revenue_growth / dividend_yield / foreign_ownership: % 또는 배수 숫자
- price / week52_high / week52_low: 원 단위 숫자
- 입력된 모든 종목을 빠짐없이 포함하라.
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
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                profile_id INTEGER PRIMARY KEY,
                status TEXT NOT NULL,          -- running / done / error
                stocks_json TEXT,
                raw_text TEXT,
                error TEXT,
                model TEXT,
                started_at TEXT,
                finished_at TEXT
            )
        """)
        # 상세 비교 결과 (프로파일별 1건)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS comparisons (
                profile_id INTEGER PRIMARY KEY,
                status TEXT NOT NULL,          -- running / done / error
                comparison_json TEXT,
                raw_text TEXT,
                error TEXT,
                model TEXT,
                started_at TEXT,
                finished_at TEXT
            )
        """)

        # 마이그레이션: model 컬럼 추가 (기존 테이블에 없으면)
        try:
            conn.execute(f"ALTER TABLE profiles ADD COLUMN model TEXT DEFAULT '{DEFAULT_MODEL}'")
        except sqlite3.OperationalError:
            pass  # 이미 존재

        # 마이그레이션: market 컬럼 추가 (국내/해외 구분, 기본 국내)
        try:
            conn.execute("ALTER TABLE profiles ADD COLUMN market TEXT DEFAULT 'DOMESTIC'")
        except sqlite3.OperationalError:
            pass  # 이미 존재

        # 기본 프로파일 시드 (이름이 없을 때만)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for p in DEFAULT_PROFILES:
            conn.execute(
                "INSERT OR IGNORE INTO profiles (name, prompt, model, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (p["name"], p["prompt"], DEFAULT_MODEL, now, now))


def list_profiles():
    with _conn() as conn:
        rows = conn.execute("""
            SELECT p.*, r.status AS last_status, r.finished_at AS last_finished_at
            FROM profiles p LEFT JOIN results r ON r.profile_id = p.id
            ORDER BY p.id
        """).fetchall()
    return [dict(r) for r in rows]


def _valid_model(model):
    model = (model or "").strip()
    return model if model in {m["id"] for m in AVAILABLE_MODELS} else DEFAULT_MODEL


def _parse_upside(value):
    """상승여력 문자열("+15%", "15.5%", "약 20%")에서 숫자만 추출. 실패 시 None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = re.search(r"[-+]?\d+(?:\.\d+)?", str(value))
    return float(m.group()) if m else None


def list_result_stocks():
    """모든 프로파일의 최근 선별 결과 종목 목록 (AI 매매의 대상 종목 선택용).

    프로파일별로 묶어서 반환하며, 같은 프로파일 내 중복 종목만 제거한다.
    각 프로파일 안에서는 상승여력(수익률) 내림차순으로 정렬한다.
    """
    with _conn() as conn:
        rows = conn.execute("""
            SELECT p.id AS profile_id, p.name AS profile_name,
                   r.stocks_json, r.finished_at
            FROM profiles p JOIN results r ON r.profile_id = p.id
            WHERE r.status = 'done' AND r.stocks_json IS NOT NULL
            ORDER BY p.id
        """).fetchall()

    out = []
    for row in rows:
        try:
            stocks = json.loads(row["stocks_json"] or "[]")
        except Exception:
            continue
        seen = set()
        group = []
        for s in stocks:
            if not isinstance(s, dict):
                continue
            ticker = str(s.get("ticker") or "").strip()
            name = str(s.get("name") or "").strip()
            if (not ticker and not name) or ticker in seen:
                continue
            if ticker:
                seen.add(ticker)
            group.append({
                "ticker": ticker or name,
                "name": name or ticker,
                "market": s.get("market") or "",
                "price": s.get("price"),
                "upside": s.get("upside"),
                "upside_pct": _parse_upside(s.get("upside")),
                "profile_id": row["profile_id"],
                "profile_name": row["profile_name"],
                "finished_at": row["finished_at"],
            })
        # 상승여력 높은 순 (값이 없는 종목은 뒤로)
        group.sort(key=lambda x: (x["upside_pct"] is None, -(x["upside_pct"] or 0)))
        out.extend(group)
    return out


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
        conn.execute("DELETE FROM comparisons WHERE profile_id = ?", (profile_id,))
        cur = conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        return cur.rowcount > 0


def get_result(profile_id):
    with _conn() as conn:
        row = conn.execute("SELECT * FROM results WHERE profile_id = ?", (profile_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        stocks = json.loads(d.pop("stocks_json") or "[]")
    except Exception:
        stocks = []
    # 상승여력 높은 순 정렬 (값 없는 종목은 뒤로) — 기존에 저장된 결과에도 적용됨
    if isinstance(stocks, list):
        stocks = [s for s in stocks if isinstance(s, dict)]
        stocks.sort(key=lambda s: (_parse_upside(s.get("upside")) is None,
                                   -(_parse_upside(s.get("upside")) or 0)))
    d["stocks"] = stocks
    return d


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


def _extract_stocks(text):
    """응답 텍스트에서 {"stocks": [...]} JSON을 추출"""
    # 1) 코드 펜스 안 JSON 우선
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidates = [m.group(1)] if m else []
    # 2) 텍스트 내 첫 '{'부터 마지막 '}'까지
    if "{" in text and "}" in text:
        candidates.append(text[text.index("{"):text.rindex("}") + 1])
    for c in candidates:
        try:
            obj = json.loads(c)
            stocks = obj.get("stocks")
            if isinstance(stocks, list):
                return stocks
        except Exception:
            continue
    return None


def _run_worker(profile_id, prompt, model):
    full_prompt = prompt.strip() + OUTPUT_FORMAT_GUIDE
    claude_bin = shutil.which("claude")
    if not claude_bin:
        _save_result(profile_id, status="error",
                     error="Claude CLI를 찾을 수 없습니다. PATH에 claude가 있는지 확인하세요.",
                     finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
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
            _save_result(profile_id, status="error", error=err, raw_text=raw,
                         finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            return
        stocks = _extract_stocks(raw)
        if stocks is None:
            _save_result(profile_id, status="error",
                         error="응답에서 종목 JSON을 찾지 못했습니다. 원문을 확인하세요.",
                         raw_text=raw,
                         finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            return
        _save_result(profile_id, status="done",
                     stocks_json=json.dumps(stocks, ensure_ascii=False),
                     raw_text=raw, error=None,
                     finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        logging.info(f"[AiPicks] 프로파일 {profile_id} 실행 완료: {len(stocks)}종목")
    except subprocess.TimeoutExpired:
        _save_result(profile_id, status="error",
                     error=f"실행 시간 초과 ({RUN_TIMEOUT_SEC}초)",
                     finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as e:
        _save_result(profile_id, status="error", error=str(e),
                     finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


# ── 상세 비교 (재무제표/투자지표) ──

def get_comparison(profile_id):
    with _conn() as conn:
        row = conn.execute("SELECT * FROM comparisons WHERE profile_id = ?", (profile_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["comparison"] = json.loads(d.pop("comparison_json") or "[]")
    except Exception:
        d["comparison"] = []
    return d


def _save_comparison(profile_id, **fields):
    cols = ", ".join(f"{k} = ?" for k in fields)
    with _conn() as conn:
        cur = conn.execute(f"UPDATE comparisons SET {cols} WHERE profile_id = ?",
                           (*fields.values(), profile_id))
        if cur.rowcount == 0:
            keys = ["profile_id"] + list(fields.keys())
            conn.execute(
                f"INSERT INTO comparisons ({', '.join(keys)}) VALUES ({', '.join('?' * len(keys))})",
                (profile_id, *fields.values()))


def _extract_comparison(text):
    """응답 텍스트에서 {"comparison": [...]} JSON을 추출"""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidates = [m.group(1)] if m else []
    if "{" in text and "}" in text:
        candidates.append(text[text.index("{"):text.rindex("}") + 1])
    for c in candidates:
        try:
            obj = json.loads(c)
            rows = obj.get("comparison")
            if isinstance(rows, list):
                return rows
        except Exception:
            continue
    return None


def _compare_worker(profile_id, stocks, model):
    lines = [f"- {s.get('name')}({s.get('ticker')})" for s in stocks]
    full_prompt = "## 비교 대상 종목\n" + "\n".join(lines) + COMPARE_FORMAT_GUIDE
    claude_bin = shutil.which("claude")
    now = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not claude_bin:
        _save_comparison(profile_id, status="error",
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
            _save_comparison(profile_id, status="error", error=err, raw_text=raw, finished_at=now())
            return
        rows = _extract_comparison(raw)
        if rows is None:
            _save_comparison(profile_id, status="error",
                             error="응답에서 비교 JSON을 찾지 못했습니다. 원문을 확인하세요.",
                             raw_text=raw, finished_at=now())
            return
        _save_comparison(profile_id, status="done",
                         comparison_json=json.dumps(rows, ensure_ascii=False),
                         raw_text=raw, error=None, finished_at=now())
        logging.info(f"[AiPicks] 프로파일 {profile_id} 상세 비교 완료: {len(rows)}종목")
    except subprocess.TimeoutExpired:
        _save_comparison(profile_id, status="error",
                         error=f"실행 시간 초과 ({RUN_TIMEOUT_SEC}초)", finished_at=now())
    except Exception as e:
        _save_comparison(profile_id, status="error", error=str(e), finished_at=now())


def run_comparison(profile_id):
    """선별 결과 종목들의 재무/투자지표 상세 비교 실행 (백그라운드)."""
    result = get_result(profile_id)
    stocks = (result or {}).get("stocks") or []
    if not stocks:
        raise ValueError("비교할 선별 결과가 없습니다. 먼저 종목 선별을 실행하세요.")

    cur = get_comparison(profile_id)
    if cur and cur.get("status") == "running":
        return False

    with _conn() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if not row:
            raise ValueError("프로파일이 없습니다.")
    model = _valid_model(row["model"])
    _save_comparison(profile_id, status="running", error=None, comparison_json=None,
                     raw_text=None, model=model,
                     started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), finished_at=None)
    threading.Thread(target=_compare_worker, args=(profile_id, stocks, model), daemon=True).start()
    return True


def run_profile(profile_id):
    """실행 시작 (백그라운드). 이미 실행 중이면 False."""
    with _conn() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if not row:
            raise ValueError("프로파일이 없습니다.")
        cur = conn.execute("SELECT status FROM results WHERE profile_id = ?", (profile_id,)).fetchone()
        if cur and cur["status"] == "running":
            return False
    # 프로파일에 지정된 모델 사용 (없으면 기본 모델)
    model = _valid_model(row["model"] if "model" in row.keys() else None)
    _save_result(profile_id, status="running", error=None, stocks_json=None, raw_text=None,
                 model=model, started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 finished_at=None)
    threading.Thread(target=_run_worker, args=(profile_id, row["prompt"], model), daemon=True).start()
    return True
