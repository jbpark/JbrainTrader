# -*- coding: utf-8 -*-
"""매매일지 AI 복기 — 최근 매매 내역을 AI에게 넘겨 습관/패턴을 진단하는 주간 리포트.

- 기간 내 매매 내역(종목별 합산)·일별 정산 손익·해당 종목의 AI 전략을 모아
  Claude CLI로 복기 리포트(JSON)를 생성한다.
- 완료되면 디스코드로 요약을 보내고, 구글시트 'AI복기' 탭에도 기록한다.
- 주 1회(기본: 토요일 09:00) 자동 실행 (설정: backend/settings/ai_review.json)
"""
import os
import json
import shutil
import sqlite3
import logging
import threading
import subprocess
import time
from datetime import datetime, timedelta

try:
    from backend.ai_picks import DEFAULT_MODEL, RUN_TIMEOUT_SEC
    from backend import ai_trades
    from backend import ai_notices
except ImportError:
    from ai_picks import DEFAULT_MODEL, RUN_TIMEOUT_SEC
    import ai_trades
    import ai_notices

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "settings", "ai_review.db")
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "settings", "ai_review.json")

DEFAULT_CONFIG = {
    "auto_run": True,
    "weekday": 5,          # 0=월 ... 5=토, 6=일
    "time": "09:00",
    "model": DEFAULT_MODEL,
    "send_discord": True,
    "export_gsheet": True,
}

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0

_engine = None
_thread = None
_run_lock = threading.Lock()
_config = dict(DEFAULT_CONFIG)

OUTPUT_FORMAT_GUIDE = """

## 출력 형식 (반드시 준수)
- 결과는 아래 JSON 형식만 출력하라. JSON 앞뒤에 다른 설명 문장을 붙이지 마라.
- 한국어로 작성하라. 데이터에 없는 내용을 지어내지 마라.

```json
{"review": {
  "summary": "이번 주 매매 총평 (2~3문장)",
  "score": 7,
  "patterns": [
    {"title": "패턴 제목 (예: 손절 지연)", "detail": "구체적 근거와 수치", "severity": "높음|중간|낮음"}
  ],
  "strategy_adherence": "AI 전략(진입가/손절가) 대비 실제 매매가 어떻게 달랐고 그 결과 손익 차이가 어땠는지",
  "checkpoints": ["다음 주에 지킬 체크포인트 1", "체크포인트 2", "체크포인트 3"]
}}
```
"""


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                period_start TEXT NOT NULL,
                period_end TEXT NOT NULL,
                status TEXT NOT NULL,        -- running / done / error
                report_json TEXT,
                raw_text TEXT,
                error TEXT,
                model TEXT,
                started_at TEXT,
                finished_at TEXT,
                UNIQUE(period_start, period_end)
            )
        """)


def _load_config():
    global _config
    try:
        if os.path.isfile(CONFIG_PATH):
            with open(CONFIG_PATH, encoding="utf-8") as f:
                saved = json.load(f)
            _config = {**DEFAULT_CONFIG, **{k: v for k, v in saved.items()
                                            if k in DEFAULT_CONFIG}}
    except Exception as e:
        logging.warning(f"[AiReview] 설정 로드 실패(기본값 사용): {e}")


def _save_config():
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(_config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.warning(f"[AiReview] 설정 저장 실패: {e}")


def get_config():
    return dict(_config)


def update_config(data):
    global _config
    for k in DEFAULT_CONFIG:
        if k not in (data or {}):
            continue
        v = data[k]
        if k in ("auto_run", "send_discord", "export_gsheet"):
            _config[k] = bool(v)
        elif k == "weekday":
            _config[k] = min(6, max(0, int(v)))
        elif k == "time":
            datetime.strptime(str(v).strip(), "%H:%M")
            _config[k] = str(v).strip()
        else:
            _config[k] = str(v).strip() or DEFAULT_CONFIG[k]
    _save_config()
    return dict(_config)


def _daterange(start, end):
    d = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end, "%Y-%m-%d")
    while d <= e:
        yield d.strftime("%Y-%m-%d")
        d += timedelta(days=1)


def _build_context(db, start, end):
    """기간 매매 내역 + 일별 정산 + 관련 AI 전략을 프롬프트용 텍스트로 구성"""
    from core.service.gsheet_exporter import GSheetExporter

    lines = [f"## 복기 대상 기간: {start} ~ {end}"]
    all_trades = []
    daily_lines = []
    for d in _daterange(start, end):
        trades = db.get_trades_by_date(d) or []
        all_trades.extend(trades)
        total = db.get_daily_profit_total(d)
        if total:
            daily_lines.append(
                f"- {d}: 실현손익 {int(total.get('profit') or 0):,}원 "
                f"(매수 {int(total.get('buy_amount') or 0):,} / "
                f"매도 {int(total.get('sell_amount') or 0):,} / "
                f"수수료+세금 {int((total.get('fee') or 0) + (total.get('tax') or 0)):,})")

    if daily_lines:
        lines.append("\n## 일별 정산 실현손익")
        lines.extend(daily_lines)

    grouped = GSheetExporter._aggregate_by_ticker(all_trades)
    traded_tickers = set()
    if grouped:
        lines.append("\n## 종목별 매매 결과 (합산)")
        for g in grouped:
            traded_tickers.add(g["ticker"])
            lines.append(
                f"- {g['ticker_name']}({g['ticker']}): 수량 {g['qty']}, "
                f"매수단가 {g['buy_price']:,}, 매도단가 {g['sell_price']:,}, "
                f"실현손익 {g['profit']:,}원 ({g['profit_rate']}%)")

    # 개별 체결 시각 정보 (시간대 패턴 분석용, 최대 80건)
    detail = [t for t in all_trades if str(t.get("side")) in ("BUY", "SELL")]
    if detail:
        lines.append("\n## 개별 체결 내역 (시간 패턴 분석용)")
        for t in detail[:80]:
            lines.append(
                f"- {t.get('execution_time')} {t.get('side')} "
                f"{t.get('ticker_name')}({t.get('ticker')}) "
                f"{t.get('qty')}주 @ {int(t.get('price') or 0):,}")

    # 매매한 종목의 AI 전략 (이행 여부 비교용)
    try:
        strategies = ai_trades.list_strategies()
    except Exception:
        strategies = {}
    strat_lines = []
    for ticker in sorted(traded_tickers):
        entries = strategies.get(ticker)
        if not entries:
            continue
        e = max(entries, key=lambda x: str(x.get("finished_at") or ""))
        s = e.get("strategy") or {}
        strat_lines.append(
            f"- {e.get('ticker_name')}({ticker}) [{e.get('profile_name')}, {e.get('finished_at')} 분석]: "
            f"진입 {s.get('entry_price')}, 목표 {s.get('target_price')}, "
            f"손절 {s.get('stop_loss')}, 비중 {s.get('position_size')}, 기간 {s.get('holding_period')}")
    if strat_lines:
        lines.append("\n## 해당 종목의 AI 매매 전략 (실제 매매와 비교하라)")
        lines.extend(strat_lines)

    has_data = bool(grouped or daily_lines)
    return "\n".join(lines), has_data


def _save(period_start, period_end, **fields):
    cols = ", ".join(f"{k} = ?" for k in fields)
    with _conn() as conn:
        cur = conn.execute(
            f"UPDATE reviews SET {cols} WHERE period_start = ? AND period_end = ?",
            (*fields.values(), period_start, period_end))
        if cur.rowcount == 0:
            keys = ["period_start", "period_end"] + list(fields.keys())
            conn.execute(
                f"INSERT INTO reviews ({', '.join(keys)}) VALUES ({', '.join('?' * len(keys))})",
                (period_start, period_end, *fields.values()))


def _extract_report(text):
    import re
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidates = [m.group(1)] if m else []
    if "{" in text and "}" in text:
        candidates.append(text[text.index("{"):text.rindex("}") + 1])
    for c in candidates:
        try:
            obj = json.loads(c)
            r = obj.get("review")
            if isinstance(r, dict):
                return r
        except Exception:
            continue
    return None


def _deliver(period, report, model, finished_at):
    """완료된 리포트를 AI Notice/디스코드/구글시트로 전달 (실패해도 리포트 자체는 저장됨)"""
    lines = [f"📋 **[매매일지 AI 복기] {period}**",
             str(report.get("summary") or "")]
    if report.get("score") is not None:
        lines.append(f"매매 점수: **{report['score']}/10**")
    pats = report.get("patterns") or []
    if pats:
        lines.append("\n**반복 패턴**")
        for p in pats[:5]:
            if isinstance(p, dict):
                lines.append(f"- [{p.get('severity', '-')}] {p.get('title')}: {p.get('detail')}")
            else:
                lines.append(f"- {p}")
    cps = report.get("checkpoints") or []
    if cps:
        lines.append("\n**다음 주 체크포인트**")
        lines.extend(f"{i+1}. {c}" for i, c in enumerate(cps[:5]))
    text = "\n".join(lines)

    # AI Notice 탭 기록 (전문 + 구조화 리포트)
    ai_notices.add("복기", f"매매일지 AI 복기 {period}", text,
                   level="info", meta=report)

    if _config.get("send_discord"):
        try:
            from backend import strategy_monitor
            strategy_monitor.send_discord(text[:1900])
        except Exception as e:
            logging.warning(f"[AiReview] 디스코드 전달 실패: {e}")

    if _config.get("export_gsheet"):
        try:
            from core.service.gsheet_exporter import GSheetExporter
            GSheetExporter().export_review(period, report, model=model,
                                           finished_at=finished_at)
        except Exception as e:
            logging.warning(f"[AiReview] 구글시트 업로드 실패: {e}")


def _run_worker(db, start, end, model):
    period = f"{start} ~ {end}"
    now = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        context, has_data = _build_context(db, start, end)
        if not has_data:
            _save(start, end, status="error", error="기간 내 매매 내역이 없습니다.",
                  finished_at=now())
            return
        claude_bin = shutil.which("claude")
        if not claude_bin:
            _save(start, end, status="error",
                  error="Claude CLI를 찾을 수 없습니다.", finished_at=now())
            return
        prompt = (
            "너는 트레이딩 코치다. 아래 매매 기록을 복기해서 나쁜 습관과 좋은 습관을 "
            "구체적 수치 근거와 함께 진단하라.\n"
            "특히 다음 관점을 반드시 확인하라:\n"
            "1) 손절 지연/물타기 등 반복되는 나쁜 패턴\n"
            "2) 특정 시간대·종목군에 손실이 몰리는지\n"
            "3) AI 매매 전략(진입/손절가)을 따랐다면 결과가 어떻게 달라졌을지\n\n"
            + context + OUTPUT_FORMAT_GUIDE)
        proc = subprocess.run(
            [claude_bin, "-p", prompt, "--model", model],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=RUN_TIMEOUT_SEC, creationflags=_NO_WINDOW)
        raw = (proc.stdout or "").strip()
        if proc.returncode != 0 or not raw:
            err = (proc.stderr or "").strip()[:500] or "Claude CLI 실행 실패 (응답 없음)"
            _save(start, end, status="error", error=err, raw_text=raw, finished_at=now())
            return
        report = _extract_report(raw)
        if report is None:
            _save(start, end, status="error",
                  error="응답에서 리포트 JSON을 찾지 못했습니다.",
                  raw_text=raw, finished_at=now())
            return
        finished = now()
        _save(start, end, status="done",
              report_json=json.dumps(report, ensure_ascii=False),
              raw_text=raw, error=None, finished_at=finished)
        logging.info(f"[AiReview] 복기 완료: {period}")
        _deliver(period, report, model, finished)
    except subprocess.TimeoutExpired:
        _save(start, end, status="error",
              error=f"실행 시간 초과 ({RUN_TIMEOUT_SEC}초)", finished_at=now())
    except Exception as e:
        logging.error(f"[AiReview] 복기 실패: {e}", exc_info=True)
        _save(start, end, status="error", error=str(e), finished_at=now())


def run(db, start=None, end=None, model=None):
    """복기 실행 (백그라운드). 기본 기간: 어제까지 최근 7일. 이미 실행 중이면 False."""
    end = end or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    start = start or (datetime.strptime(end, "%Y-%m-%d")
                      - timedelta(days=6)).strftime("%Y-%m-%d")
    model = (model or _config.get("model") or DEFAULT_MODEL).strip()
    with _run_lock:
        with _conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM reviews WHERE status = 'running' LIMIT 1").fetchone()
        if row:
            return False
        _save(start, end, status="running", error=None, report_json=None,
              raw_text=None, model=model, started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              finished_at=None)
    threading.Thread(target=_run_worker, args=(db, start, end, model),
                     daemon=True).start()
    return True


def list_reviews(limit=20):
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM reviews ORDER BY period_end DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["report"] = json.loads(d.pop("report_json") or "null")
        except Exception:
            d["report"] = None
        d.pop("raw_text", None)
        out.append(d)
    return out


def get_review(review_id=None):
    with _conn() as conn:
        if review_id:
            row = conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM reviews ORDER BY period_end DESC LIMIT 1").fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["report"] = json.loads(d.pop("report_json") or "null")
    except Exception:
        d["report"] = None
    return d


def _auto_loop():
    """주 1회 자동 복기 (설정 요일·시각 이후 첫 체크 때 실행)"""
    logging.info("[AiReview] 자동 복기 스레드 시작")
    last_run_date = None
    while True:
        time.sleep(300)
        try:
            if not _config.get("auto_run") or _engine is None:
                continue
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            if now.weekday() != int(_config.get("weekday", 5)):
                continue
            if now.strftime("%H:%M") < str(_config.get("time", "09:00")):
                continue
            if last_run_date == today:
                continue
            # 이번 주 기간을 이미 복기했으면 건너뜀
            end = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
            with _conn() as conn:
                row = conn.execute(
                    "SELECT status FROM reviews WHERE period_start = ? AND period_end = ?",
                    (start, end)).fetchone()
            if row and row["status"] == "done":
                last_run_date = today
                continue
            last_run_date = today
            if run(_engine.db, start=start, end=end):
                logging.info(f"[AiReview] 주간 자동 복기 시작: {start} ~ {end}")
        except Exception as e:
            logging.error(f"[AiReview] 자동 복기 오류: {e}", exc_info=True)


def start(engine):
    """엔진 시작 시 1회 호출"""
    global _engine, _thread
    _engine = engine
    init_db()
    _load_config()
    if _thread is None or not _thread.is_alive():
        _thread = threading.Thread(target=_auto_loop, daemon=True,
                                   name="AiReviewThread")
        _thread.start()
