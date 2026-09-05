# -*- coding: utf-8 -*-
"""AI 전략 스코어카드 — 매매 전략의 목표가/손절가 도달 여부를 실제 주가로 자동 채점.

- ai_trades의 완료된 전략은 프로파일+종목당 최신 1건만 보관되므로,
  여기서 (프로파일, 종목, 분석일시) 단위로 스냅샷을 보존해 이력이 사라지지 않게 한다.
- 채점: 분석일 이후 일봉(야후 파이낸스)에서 목표가/손절가 중 무엇에 먼저 닿았는지 판정.
  * TARGET_HIT  : 고가가 목표가 도달 (같은 날 둘 다 닿으면 보수적으로 STOP_HIT)
  * STOP_HIT    : 저가가 손절가 도달
  * EXPIRED     : 보유기간(예: "1~3주") 경과에도 미도달 → 마지막 종가로 정산
  * OPEN        : 아직 진행 중 (미실현 수익률 기록)
- 수익률 기준가: 분석 시점의 current_price (없으면 첫 거래일 시가).
- 평일 장 마감 후(기본 16:00) 자동으로 스냅샷+채점 1회 실행.
"""
import os
import re
import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta

try:
    from backend import ai_trades
except ImportError:
    import ai_trades

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "settings", "strategy_scorecard.db")

AUTO_GRADE_TIME = "16:00"   # 평일 이 시각 이후 하루 1회 자동 채점
DEFAULT_DEADLINE_DAYS = 60  # 보유기간을 해석할 수 없을 때의 만료 기한

OUTCOME_LABELS = {
    "TARGET_HIT": "목표 달성",
    "STOP_HIT": "손절 도달",
    "EXPIRED": "기간 만료",
    "OPEN": "진행 중",
    "INVALID": "채점 불가",
}

_grade_lock = threading.Lock()
_thread = None
_last_auto_grade_date = None


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scorecard (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                profile_name TEXT,
                model TEXT,
                ticker TEXT NOT NULL,
                name TEXT,
                market TEXT,
                analyzed_at TEXT NOT NULL,     -- 전략 분석 완료 일시
                base_price REAL,               -- 수익률 기준가 (분석 시점 현재가)
                target_price REAL,
                stop_loss REAL,
                expected_return TEXT,
                holding_period TEXT,
                deadline_date TEXT,            -- 보유기간 기반 만료일 (YYYY-MM-DD)
                outcome TEXT NOT NULL DEFAULT 'OPEN',
                outcome_date TEXT,             -- 도달/만료 판정일
                outcome_price REAL,            -- 판정 가격 (목표가/손절가/만료일 종가)
                realized_return REAL,          -- 판정 수익률 (%)
                last_price REAL,               -- OPEN 상태의 최근 종가
                unrealized_return REAL,        -- OPEN 상태의 미실현 수익률 (%)
                note TEXT,
                graded_at TEXT,
                UNIQUE(profile_id, ticker, analyzed_at)
            )
        """)


def _to_num(v):
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _parse_deadline_days(holding_period):
    """'1~3주' / '2주' / '수주' / '1~2개월' → 최대 일수. 해석 불가면 기본값."""
    s = str(holding_period or "").strip()
    if not s:
        return DEFAULT_DEADLINE_DAYS
    unit_days = {"일": 1, "주": 7, "개월": 30, "달": 30}
    m = re.findall(r"(\d+)\s*(일|주|개월|달)", s)
    if m:
        return max(int(n) * unit_days[u] for n, u in m)
    if "수일" in s:
        return 7
    if "수주" in s:
        return 28
    return DEFAULT_DEADLINE_DAYS


def snapshot():
    """ai_trades의 완료된 전략을 스코어카드에 보존 (이미 있으면 무시). 반환: 신규 건수"""
    added = 0
    try:
        strategies = ai_trades.list_strategies()
    except Exception as e:
        logging.warning(f"[Scorecard] 전략 조회 실패: {e}")
        return 0
    with _conn() as conn:
        for ticker, entries in strategies.items():
            for e in entries:
                s = e.get("strategy") or {}
                analyzed_at = str(e.get("finished_at") or "").strip()
                if not analyzed_at:
                    continue
                target = _to_num(s.get("target_price"))
                stop = _to_num(s.get("stop_loss"))
                if target is None and stop is None:
                    continue
                deadline_days = _parse_deadline_days(s.get("holding_period"))
                try:
                    deadline = (datetime.strptime(analyzed_at[:10], "%Y-%m-%d")
                                + timedelta(days=deadline_days)).strftime("%Y-%m-%d")
                except ValueError:
                    deadline = None
                cur = conn.execute("""
                    INSERT OR IGNORE INTO scorecard
                        (profile_id, profile_name, model, ticker, name, market,
                         analyzed_at, base_price, target_price, stop_loss,
                         expected_return, holding_period, deadline_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (e.get("profile_id"), e.get("profile_name"), e.get("model"),
                      ticker, e.get("ticker_name") or s.get("name"),
                      str(s.get("market") or ""), analyzed_at,
                      _to_num(s.get("current_price")), target, stop,
                      str(s.get("expected_return") or ""),
                      str(s.get("holding_period") or ""), deadline))
                added += cur.rowcount
    if added:
        logging.info(f"[Scorecard] 전략 스냅샷 {added}건 추가")
    return added


def _yahoo_symbols(ticker, market):
    m = str(market or "")
    if "코스닥" in m or "KOSDAQ" in m.upper():
        return [f"{ticker}.KQ", f"{ticker}.KS"]
    return [f"{ticker}.KS", f"{ticker}.KQ"]


def _fetch_daily(ticker, market, start_date):
    """분석일~오늘의 일봉 DataFrame (없으면 None)"""
    try:
        from core.provider.yahoo import YahooProvider
    except ImportError as e:
        logging.error(f"[Scorecard] YahooProvider 로드 실패: {e}")
        return None
    end = datetime.now().strftime("%Y-%m-%d")
    provider = YahooProvider()
    for sym in _yahoo_symbols(ticker, market):
        try:
            df = provider.fetch_data(sym, "1d", start_date, end)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logging.debug(f"[Scorecard] {sym} 일봉 조회 실패: {e}")
    return None


def _effective_start(analyzed_at):
    """채점 시작일 — 장 마감(15:30) 후 분석이면 다음 날부터, 장중이면 당일부터."""
    try:
        dt = datetime.strptime(analyzed_at[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return analyzed_at[:10]
    if dt.strftime("%H:%M") >= "15:30":
        return (dt + timedelta(days=1)).strftime("%Y-%m-%d")
    return dt.strftime("%Y-%m-%d")


def _grade_row(row, df):
    """일봉 DataFrame으로 한 건 채점 → 갱신 dict (변경 없으면 None)"""
    start = _effective_start(row["analyzed_at"])
    target, stop = row["target_price"], row["stop_loss"]
    base = row["base_price"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sub = df[df.index.strftime("%Y-%m-%d") >= start] if df is not None else None
    if sub is None or sub.empty:
        # 아직 채점할 거래일이 없음 (주말/휴일 등)
        return {"graded_at": now}

    if base is None:
        base = float(sub.iloc[0]["open"])

    def ret(price):
        return round((price - base) / base * 100, 2) if base else None

    for idx, day in sub.iterrows():
        d = idx.strftime("%Y-%m-%d")
        hit_stop = stop is not None and float(day["low"]) <= stop
        hit_target = target is not None and float(day["high"]) >= target
        if hit_stop and hit_target:
            return {"outcome": "STOP_HIT", "outcome_date": d, "outcome_price": stop,
                    "realized_return": ret(stop), "base_price": base,
                    "note": "같은 날 목표/손절 모두 도달 → 보수적으로 손절 판정",
                    "graded_at": now}
        if hit_stop:
            return {"outcome": "STOP_HIT", "outcome_date": d, "outcome_price": stop,
                    "realized_return": ret(stop), "base_price": base, "graded_at": now}
        if hit_target:
            return {"outcome": "TARGET_HIT", "outcome_date": d, "outcome_price": target,
                    "realized_return": ret(target), "base_price": base, "graded_at": now}

    last_close = float(sub.iloc[-1]["close"])
    last_date = sub.index[-1].strftime("%Y-%m-%d")
    deadline = row["deadline_date"]
    if deadline and last_date >= deadline:
        return {"outcome": "EXPIRED", "outcome_date": last_date, "outcome_price": last_close,
                "realized_return": ret(last_close), "base_price": base, "graded_at": now}
    return {"outcome": "OPEN", "last_price": last_close, "unrealized_return": ret(last_close),
            "base_price": base, "graded_at": now}


def grade():
    """미확정(OPEN) 전략 전체 채점. 반환: 요약 dict"""
    if not _grade_lock.acquire(blocking=False):
        return {"error": "이미 채점이 진행 중입니다."}
    try:
        snapshot()
        with _conn() as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM scorecard WHERE outcome = 'OPEN' ORDER BY ticker, analyzed_at")]
        if not rows:
            return {"graded": 0, "open": 0, "message": "채점할 전략이 없습니다."}

        # 종목별로 일봉을 한 번만 조회 (가장 이른 분석일 기준)
        by_ticker = {}
        for r in rows:
            by_ticker.setdefault(r["ticker"], []).append(r)

        graded = still_open = failed = 0
        for ticker, t_rows in by_ticker.items():
            start = min(_effective_start(r["analyzed_at"]) for r in t_rows)
            df = _fetch_daily(ticker, t_rows[0]["market"], start)
            if df is None:
                failed += len(t_rows)
                logging.warning(f"[Scorecard] {ticker} 일봉 조회 실패 — 채점 보류")
                continue
            for r in t_rows:
                upd = _grade_row(r, df)
                if not upd:
                    continue
                cols = ", ".join(f"{k} = ?" for k in upd)
                with _conn() as conn:
                    conn.execute(f"UPDATE scorecard SET {cols} WHERE id = ?",
                                 (*upd.values(), r["id"]))
                if upd.get("outcome") and upd["outcome"] != "OPEN":
                    graded += 1
                else:
                    still_open += 1
            time.sleep(0.5)  # 야후 API 부하 방지

        logging.info(f"[Scorecard] 채점 완료: 확정 {graded}건, 진행 중 {still_open}건, 조회실패 {failed}건")
        return {"graded": graded, "open": still_open, "fetch_failed": failed,
                "total": len(rows)}
    finally:
        _grade_lock.release()


def list_rows(limit=500):
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM scorecard ORDER BY analyzed_at DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["outcome_label"] = OUTCOME_LABELS.get(d["outcome"], d["outcome"])
        out.append(d)
    return out


def _aggregate(rows, key):
    """key('profile_name'|'model')별 성과 집계"""
    groups = {}
    for r in rows:
        g = groups.setdefault(str(r.get(key) or "(없음)"), {
            "total": 0, "target_hit": 0, "stop_hit": 0, "expired": 0, "open": 0,
            "returns": [], "open_returns": [],
        })
        g["total"] += 1
        oc = r["outcome"]
        if oc == "TARGET_HIT":
            g["target_hit"] += 1
        elif oc == "STOP_HIT":
            g["stop_hit"] += 1
        elif oc == "EXPIRED":
            g["expired"] += 1
        else:
            g["open"] += 1
        if r.get("realized_return") is not None:
            g["returns"].append(r["realized_return"])
        if oc == "OPEN" and r.get("unrealized_return") is not None:
            g["open_returns"].append(r["unrealized_return"])

    out = {}
    for name, g in groups.items():
        decided = g["target_hit"] + g["stop_hit"]
        out[name] = {
            "total": g["total"],
            "target_hit": g["target_hit"], "stop_hit": g["stop_hit"],
            "expired": g["expired"], "open": g["open"],
            # 적중률: 목표/손절이 확정된 것 중 목표 달성 비율
            "hit_rate": round(g["target_hit"] / decided * 100, 1) if decided else None,
            # 확정(만료 포함) 건 평균 수익률
            "avg_return": round(sum(g["returns"]) / len(g["returns"]), 2) if g["returns"] else None,
            "avg_open_return": round(sum(g["open_returns"]) / len(g["open_returns"]), 2)
                               if g["open_returns"] else None,
        }
    return out


def get_stats():
    rows = list_rows(limit=10000)
    return {
        "rows": len(rows),
        "by_profile": _aggregate(rows, "profile_name"),
        "by_model": _aggregate(rows, "model"),
    }


def _auto_loop():
    """평일 장 마감 후 하루 1회 자동 스냅샷+채점"""
    global _last_auto_grade_date
    logging.info("[Scorecard] 자동 채점 스레드 시작")
    while True:
        time.sleep(300)
        try:
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            if now.weekday() >= 5 or now.strftime("%H:%M") < AUTO_GRADE_TIME:
                continue
            if _last_auto_grade_date == today:
                continue
            _last_auto_grade_date = today
            grade()
        except Exception as e:
            logging.error(f"[Scorecard] 자동 채점 오류: {e}", exc_info=True)


def start():
    """엔진 시작 시 1회 호출"""
    global _thread
    init_db()
    if _thread is None or not _thread.is_alive():
        _thread = threading.Thread(target=_auto_loop, daemon=True,
                                   name="ScorecardThread")
        _thread.start()
