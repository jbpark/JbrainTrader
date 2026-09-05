# -*- coding: utf-8 -*-
"""AI 매매 — 특정 종목의 매매 전략을 AI에게 묻는 프로파일 관리 및 Claude CLI 실행.

AI 종목(ai_picks)과 구조는 같으나, 실행 시 대상 종목을 지정하고
결과로 해당 종목의 매매 전략(진입/청산/손절/비중 등)을 받는다.
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

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings", "ai_trades.db")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0

DEFAULT_PROFILES = [
    {
        "name": "단기_스윙전략",
        "prompt": (
            "이 종목을 지금 매매한다면 어떻게 접근해야 할지 매매 전략을 제시해줘.\n"
            "최근 주가 흐름과 수급, 재무 상태를 고려해서 진입 가격대, 목표가, 손절가, "
            "매수/매도 조건과 투자 비중을 구체적으로 알려줘.\n"
            "보유 기간은 수일~수주의 단기 스윙 관점으로 판단해줘."
        ),
    },
]

OUTPUT_FORMAT_GUIDE = """

## 출력 형식 (반드시 준수)
- 대상은 한국 주식(코스피/코스닥)이다.
- 최신 주가, 차트 흐름, 재무·수급 정보는 웹 검색으로 확인하라.
- 결과는 아래 JSON 형식만 출력하라. JSON 앞뒤에 다른 설명 문장을 붙이지 마라.

```json
{"strategy": {
  "ticker": "005930",
  "name": "삼성전자",
  "market": "코스피",
  "current_price": 276000,
  "summary": "전략 한 줄 요약",
  "entry_price": "270,000 ~ 274,000",
  "target_price": 300000,
  "stop_loss": 262000,
  "expected_return": "+9%",
  "risk_level": "중간",
  "position_size": "총 자산의 5% 이내",
  "holding_period": "2~3주",
  "buy_conditions": ["매수 조건 1", "매수 조건 2"],
  "sell_conditions": ["매도 조건 1", "매도 조건 2"],
  "risks": ["리스크 요인 1", "리스크 요인 2"],
  "reason": "이 전략을 제시한 근거 요약"
}}
```

- current_price / target_price / stop_loss: 숫자(원 단위)
- entry_price: 가격대 문자열 (단일 가격이면 그 값만)
- risk_level: "낮음" | "중간" | "높음"
- buy_conditions / sell_conditions / risks: 문자열 배열 (각 2~4개)
"""


def _format_guide(market):
    """해외 프로파일은 대상/통화 안내를 해외 주식 기준으로 바꾼다"""
    if market == "OVERSEAS":
        return (OUTPUT_FORMAT_GUIDE
                .replace("대상은 한국 주식(코스피/코스닥)이다.",
                         "대상은 미국 등 해외 주식이다. market에는 거래소(나스닥/NYSE 등)를 적어라.")
                .replace("숫자(원 단위)", "숫자(현지 통화 단위, 예: 달러)"))
    return OUTPUT_FORMAT_GUIDE


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


_RESULT_COLS = ["profile_id", "ticker", "ticker_name", "status", "strategy_json",
                "raw_text", "error", "model", "started_at", "finished_at"]


def _migrate_results_pk(conn):
    """예전 스키마(profile_id 단독 PK)를 (profile_id, ticker) PK로 옮긴다."""
    info = conn.execute("PRAGMA table_info(results)").fetchall()
    if not info:
        return
    pk_cols = [c["name"] for c in info if c["pk"]]
    if pk_cols != ["profile_id"]:
        return   # 이미 새 스키마

    cols = ", ".join(_RESULT_COLS)
    conn.execute("ALTER TABLE results RENAME TO results_old")
    conn.execute(f"""
        CREATE TABLE results (
            profile_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            ticker_name TEXT,
            status TEXT NOT NULL,
            strategy_json TEXT,
            raw_text TEXT,
            error TEXT,
            model TEXT,
            started_at TEXT,
            finished_at TEXT,
            PRIMARY KEY (profile_id, ticker)
        )
    """)
    # 종목이 비어 있는 예전 행은 새 키를 만들 수 없으므로 버린다
    conn.execute(f"INSERT INTO results ({cols}) SELECT {cols} FROM results_old "
                 "WHERE ticker IS NOT NULL AND TRIM(ticker) != ''")
    conn.execute("DROP TABLE results_old")
    logging.info("[AiTrades] results 테이블을 (프로파일, 종목) 키로 이전했습니다.")


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
        # 결과는 (프로파일, 종목) 단위로 보관한다. 예전에는 프로파일당 1건만
        # 저장해서 같은 프로파일로 여러 종목을 분석하면 서로 덮어썼다.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                profile_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                ticker_name TEXT,
                status TEXT NOT NULL,          -- running / done / error
                strategy_json TEXT,
                raw_text TEXT,
                error TEXT,
                model TEXT,
                started_at TEXT,
                finished_at TEXT,
                PRIMARY KEY (profile_id, ticker)
            )
        """)
        _migrate_results_pk(conn)
        # 마이그레이션: market 컬럼 추가 (국내/해외 구분, 기본 국내)
        try:
            conn.execute("ALTER TABLE profiles ADD COLUMN market TEXT DEFAULT 'DOMESTIC'")
        except sqlite3.OperationalError:
            pass  # 이미 존재
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for p in DEFAULT_PROFILES:
            conn.execute(
                "INSERT OR IGNORE INTO profiles (name, prompt, model, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (p["name"], p["prompt"], DEFAULT_MODEL, now, now))


def _valid_model(model):
    model = (model or "").strip()
    return model if model in {m["id"] for m in AVAILABLE_MODELS} else DEFAULT_MODEL


def list_profiles():
    with _conn() as conn:
        # 결과가 종목별로 여러 건이므로 프로파일당 최근 1건만 붙인다
        rows = conn.execute("""
            SELECT p.*, r.status AS last_status, r.finished_at AS last_finished_at,
                   r.ticker AS last_ticker, r.ticker_name AS last_ticker_name
            FROM profiles p
            LEFT JOIN results r ON r.profile_id = p.id AND r.rowid = (
                SELECT rowid FROM results WHERE profile_id = p.id
                ORDER BY (status = 'running') DESC, started_at DESC LIMIT 1
            )
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


def get_result(profile_id, ticker=None):
    """프로파일의 분석 결과. ticker를 주면 그 종목, 없으면 가장 최근 실행 건."""
    with _conn() as conn:
        if ticker:
            row = conn.execute(
                "SELECT * FROM results WHERE profile_id = ? AND ticker = ?",
                (profile_id, ticker)).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM results WHERE profile_id = ? "
                "ORDER BY (status = 'running') DESC, started_at DESC LIMIT 1",
                (profile_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["strategy"] = json.loads(d.pop("strategy_json") or "null")
    except Exception:
        d["strategy"] = None
    return d


def list_strategies():
    """완료된 매매 전략을 종목코드 기준으로 모아서 반환 (보유 종목 화면 연결용).

    results는 프로파일당 1건(최근 실행)만 보관하므로, 같은 종목을 여러
    프로파일에서 분석했다면 종목코드 하나에 전략이 여러 개 붙을 수 있다.
    """
    with _conn() as conn:
        rows = conn.execute("""
            SELECT p.id AS profile_id, p.name AS profile_name,
                   r.ticker, r.ticker_name, r.strategy_json, r.model, r.finished_at
            FROM profiles p JOIN results r ON r.profile_id = p.id
            WHERE r.status = 'done' AND r.strategy_json IS NOT NULL
            ORDER BY p.id
        """).fetchall()

    by_ticker = {}
    for row in rows:
        ticker = str(row["ticker"] or "").strip()
        if not ticker:
            continue
        try:
            strategy = json.loads(row["strategy_json"] or "null")
        except Exception:
            continue
        if not isinstance(strategy, dict):
            continue
        by_ticker.setdefault(ticker, []).append({
            "profile_id": row["profile_id"],
            "profile_name": row["profile_name"],
            "ticker": ticker,
            "ticker_name": row["ticker_name"] or strategy.get("name") or "",
            "model": row["model"],
            "finished_at": row["finished_at"],
            "strategy": strategy,
        })
    return by_ticker


def _save_result(profile_id, ticker, **fields):
    cols = ", ".join(f"{k} = ?" for k in fields)
    with _conn() as conn:
        cur = conn.execute(
            f"UPDATE results SET {cols} WHERE profile_id = ? AND ticker = ?",
            (*fields.values(), profile_id, ticker))
        if cur.rowcount == 0:
            keys = ["profile_id", "ticker"] + list(fields.keys())
            conn.execute(
                f"INSERT INTO results ({', '.join(keys)}) VALUES ({', '.join('?' * len(keys))})",
                (profile_id, ticker, *fields.values()))


def _extract_strategy(text):
    """응답 텍스트에서 {"strategy": {...}} JSON을 추출"""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidates = [m.group(1)] if m else []
    if "{" in text and "}" in text:
        candidates.append(text[text.index("{"):text.rindex("}") + 1])
    for c in candidates:
        try:
            obj = json.loads(c)
            strategy = obj.get("strategy")
            if isinstance(strategy, dict):
                return strategy
        except Exception:
            continue
    return None


def _run_worker(profile_id, prompt, model, ticker, ticker_name, market="DOMESTIC"):
    target = f"{ticker_name}({ticker})" if ticker_name else ticker
    full_prompt = (f"## 대상 종목\n{target}\n\n## 요청\n"
                   + prompt.strip() + _format_guide(market))
    claude_bin = shutil.which("claude")
    now = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not claude_bin:
        _save_result(profile_id, ticker, status="error",
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
            _save_result(profile_id, ticker, status="error", error=err, raw_text=raw, finished_at=now())
            return
        strategy = _extract_strategy(raw)
        if strategy is None:
            _save_result(profile_id, ticker, status="error",
                         error="응답에서 전략 JSON을 찾지 못했습니다. 원문을 확인하세요.",
                         raw_text=raw, finished_at=now())
            return
        _save_result(profile_id, ticker, status="done",
                     strategy_json=json.dumps(strategy, ensure_ascii=False),
                     raw_text=raw, error=None, finished_at=now())
        logging.info(f"[AiTrades] 프로파일 {profile_id} 실행 완료: {target}")
    except subprocess.TimeoutExpired:
        _save_result(profile_id, ticker, status="error",
                     error=f"실행 시간 초과 ({RUN_TIMEOUT_SEC}초)", finished_at=now())
    except Exception as e:
        _save_result(profile_id, ticker, status="error", error=str(e), finished_at=now())


def _profile_busy(profile_id):
    """해당 프로파일이 단건 실행 중이거나 일괄 분석 중인지"""
    with _batch_lock:
        st = _batches.get(profile_id)
        if st and st["running"]:
            return True
    with _conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM results WHERE profile_id = ? AND status = 'running' LIMIT 1",
            (profile_id,)).fetchone()
    return row is not None


# ── 일괄 분석 (보유 종목 전체를 한 프로파일로) ──
_batch_lock = threading.Lock()
_batches = {}    # profile_id -> 진행 상태


def get_batch_status(profile_id):
    with _batch_lock:
        st = _batches.get(profile_id)
        return dict(st) if st else {"running": False, "total": 0, "done": 0,
                                    "current": "", "errors": 0}


def run_batch(profile_id, items):
    """여러 종목을 한 프로파일로 순차 분석 (백그라운드). 이미 실행 중이면 False.

    Claude CLI를 동시에 여러 개 띄우지 않도록 한 종목씩 순서대로 처리한다.
    """
    cleaned = []
    seen = set()
    for it in items or []:
        ticker = str((it or {}).get("ticker") or "").strip()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        cleaned.append({"ticker": ticker,
                        "name": str((it or {}).get("name") or "").strip()})
    if not cleaned:
        raise ValueError("분석할 종목이 없습니다.")

    with _conn() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if not row:
            raise ValueError("프로파일이 없습니다.")
    if _profile_busy(profile_id):
        return False

    now = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    model = _valid_model(row["model"])
    prompt = row["prompt"]
    market = (dict(row).get("market") or "DOMESTIC")
    with _batch_lock:
        _batches[profile_id] = {"running": True, "total": len(cleaned), "done": 0,
                                "current": "", "errors": 0,
                                "started_at": now(), "finished_at": None}

    def worker():
        for it in cleaned:
            with _batch_lock:
                _batches[profile_id]["current"] = it["name"] or it["ticker"]
            _save_result(profile_id, it["ticker"], status="running", error=None,
                         strategy_json=None, raw_text=None,
                         ticker_name=it["name"], model=model,
                         started_at=now(), finished_at=None)
            # 스레드를 새로 만들지 않고 이 스레드에서 순차 실행
            _run_worker(profile_id, prompt, model, it["ticker"], it["name"],
                        market=market)
            res = get_result(profile_id, it["ticker"])
            with _batch_lock:
                _batches[profile_id]["done"] += 1
                if not res or res.get("status") != "done":
                    _batches[profile_id]["errors"] += 1
        with _batch_lock:
            _batches[profile_id].update(running=False, current="", finished_at=now())
        logging.info(f"[AiTrades] 프로파일 {profile_id} 일괄 분석 완료 "
                     f"({len(cleaned)}종목)")

    threading.Thread(target=worker, daemon=True).start()
    return True


def run_profile(profile_id, ticker, ticker_name=""):
    """실행 시작 (백그라운드). 이미 실행 중이면 False."""
    ticker = (ticker or "").strip()
    if not ticker:
        raise ValueError("대상 종목을 선택하세요.")
    with _conn() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if not row:
            raise ValueError("프로파일이 없습니다.")
    if _profile_busy(profile_id):
        return False
    model = _valid_model(row["model"])
    market = (dict(row).get("market") or "DOMESTIC")
    _save_result(profile_id, ticker, status="running", error=None, strategy_json=None, raw_text=None,
                 ticker_name=(ticker_name or "").strip(), model=model,
                 started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), finished_at=None)
    threading.Thread(target=_run_worker,
                     args=(profile_id, row["prompt"], model, ticker, ticker_name),
                     kwargs={"market": market},
                     daemon=True).start()
    return True
