# -*- coding: utf-8 -*-
"""보유종목 아침 브리핑 — 장 시작 전 보유 종목 뉴스·공시 + 일정 영향을 AI가 요약.

- 보유 종목, 각 종목의 최신 AI 전략, AI 캘린더의 다가오는 일정을 모아
  Claude CLI(웹 검색 허용)로 아침 브리핑(JSON)을 생성한다.
- 완료되면 디스코드로 요약 전달.
- 평일 아침(기본 08:00) 자동 실행 (설정: backend/settings/ai_briefing.json)
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
    from backend import ai_calendar
    from backend import ai_notices
except ImportError:
    from ai_picks import DEFAULT_MODEL, RUN_TIMEOUT_SEC
    import ai_trades
    import ai_calendar
    import ai_notices

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "settings", "ai_briefing.db")
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "settings", "ai_briefing.json")

DEFAULT_CONFIG = {
    "auto_run": True,
    "time": "08:00",       # 평일 이 시각 이후 하루 1회
    "model": DEFAULT_MODEL,
    "send_discord": True,
}

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0

_engine = None
_thread = None
_run_lock = threading.Lock()
_config = dict(DEFAULT_CONFIG)

OUTPUT_FORMAT_GUIDE = """

## 출력 형식 (반드시 준수)
- 대상은 한국 주식이다. 최신 뉴스·공시는 웹 검색으로 확인하라 (최근 2~3일 위주).
- 모든 보유 종목을 하나하나 검색할 필요는 없다. 주요 뉴스가 있는 종목 위주로 다루되,
  전략과 배치되는 이벤트가 있는 종목은 반드시 포함하라.
- 결과는 아래 JSON 형식만 출력하라. JSON 앞뒤에 다른 설명 문장을 붙이지 마라.

```json
{"briefing": {
  "summary": "오늘 아침 브리핑 총평 (2~3문장, 시장 분위기 포함)",
  "market_overview": "간밤 미국 증시/환율/주요 이슈가 국내 증시에 미칠 영향",
  "items": [
    {"ticker": "005930", "name": "삼성전자",
     "news": "핵심 뉴스/공시 요약 (출처 언론사 포함)",
     "impact": "긍정|부정|중립",
     "strategy_conflict": "보유 전략(목표/손절)과 배치되는 점이 있으면 서술, 없으면 빈 문자열",
     "action_hint": "오늘 주시할 포인트 한 줄"}
  ],
  "calendar_alerts": ["오늘/이번 주 일정 중 보유 종목에 영향을 주는 항목과 그 이유"]
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
            CREATE TABLE IF NOT EXISTS briefings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,   -- 브리핑 날짜 (YYYY-MM-DD)
                status TEXT NOT NULL,        -- running / done / error
                report_json TEXT,
                raw_text TEXT,
                error TEXT,
                model TEXT,
                started_at TEXT,
                finished_at TEXT
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
        logging.warning(f"[AiBriefing] 설정 로드 실패(기본값 사용): {e}")


def _save_config():
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(_config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.warning(f"[AiBriefing] 설정 저장 실패: {e}")


def get_config():
    return dict(_config)


def update_config(data):
    global _config
    for k in DEFAULT_CONFIG:
        if k not in (data or {}):
            continue
        v = data[k]
        if k in ("auto_run", "send_discord"):
            _config[k] = bool(v)
        elif k == "time":
            datetime.strptime(str(v).strip(), "%H:%M")
            _config[k] = str(v).strip()
        else:
            _config[k] = str(v).strip() or DEFAULT_CONFIG[k]
    _save_config()
    return dict(_config)


def _upcoming_events(days=7):
    """AI 캘린더의 완료된 결과에서 오늘~N일 내 일정을 수집 (중복 제거)"""
    today = datetime.now().strftime("%Y-%m-%d")
    until = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    events, seen = [], set()
    try:
        for p in ai_calendar.list_profiles():
            r = ai_calendar.get_result(p["id"])
            if not r or r.get("status") != "done":
                continue
            for e in r.get("events") or []:
                date = str(e.get("date") or "")
                title = str(e.get("title") or e.get("name") or "")
                if not (today <= date <= until) or not title:
                    continue
                key = (date, title)
                if key in seen:
                    continue
                seen.add(key)
                events.append(e)
    except Exception as e:
        logging.warning(f"[AiBriefing] 캘린더 일정 조회 실패: {e}")
    return sorted(events, key=lambda e: str(e.get("date") or ""))


def _build_context():
    """보유 종목 + 전략 + 다가오는 일정 → 프롬프트 텍스트"""
    holdings = []
    if _engine is not None:
        holdings = (_engine.data_store.get("account") or {}).get("holdings") or []
    if not holdings:
        return None

    try:
        strategies = ai_trades.list_strategies()
    except Exception:
        strategies = {}

    lines = [f"## 오늘 날짜: {datetime.now().strftime('%Y-%m-%d (%a)')}",
             "\n## 보유 종목 (수익률은 현재 계좌 기준)"]
    for h in holdings:
        if not isinstance(h, dict):
            continue
        ticker = str(h.get("ticker") or "").strip()
        line = (f"- {h.get('name')}({ticker}): {h.get('qty')}주, "
                f"수익률 {h.get('ratio')}%")
        entries = strategies.get(ticker)
        if entries:
            e = max(entries, key=lambda x: str(x.get("finished_at") or ""))
            s = e.get("strategy") or {}
            line += (f" | 전략[{e.get('profile_name')}]: 목표 {s.get('target_price')}, "
                     f"손절 {s.get('stop_loss')}, 기간 {s.get('holding_period')}")
        lines.append(line)

    events = _upcoming_events()
    if events:
        lines.append("\n## 다가오는 주요 일정 (AI 캘린더)")
        for e in events[:20]:
            lines.append(f"- {e.get('date')} {e.get('title') or e.get('name')} "
                         f"(중요도: {e.get('importance', '-')}, 영향: {e.get('impact', '-')})")
    return "\n".join(lines)


def _save(date, **fields):
    cols = ", ".join(f"{k} = ?" for k in fields)
    with _conn() as conn:
        cur = conn.execute(f"UPDATE briefings SET {cols} WHERE date = ?",
                           (*fields.values(), date))
        if cur.rowcount == 0:
            keys = ["date"] + list(fields.keys())
            conn.execute(
                f"INSERT INTO briefings ({', '.join(keys)}) VALUES ({', '.join('?' * len(keys))})",
                (date, *fields.values()))


def _extract_report(text):
    import re
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidates = [m.group(1)] if m else []
    if "{" in text and "}" in text:
        candidates.append(text[text.index("{"):text.rindex("}") + 1])
    for c in candidates:
        try:
            obj = json.loads(c)
            b = obj.get("briefing")
            if isinstance(b, dict):
                return b
        except Exception:
            continue
    return None


def _deliver(date, report):
    impact_icon = {"긍정": "🟢", "부정": "🔴", "중립": "⚪"}
    lines = [f"☀️ **[아침 브리핑] {date}**",
             str(report.get("summary") or "")]
    if report.get("market_overview"):
        lines.append(f"\n**시장 개요**: {report['market_overview']}")
    items = report.get("items") or []
    if items:
        lines.append("\n**보유 종목 뉴스**")
        for it in items[:8]:
            icon = impact_icon.get(str(it.get("impact") or ""), "⚪")
            lines.append(f"{icon} {it.get('name')}({it.get('ticker')}): {it.get('news')}")
            if it.get("strategy_conflict"):
                lines.append(f"   ⚠️ 전략 배치: {it['strategy_conflict']}")
    alerts = report.get("calendar_alerts") or []
    if alerts:
        lines.append("\n**일정 알림**")
        lines.extend(f"- {a}" for a in alerts[:5])
    text = "\n".join(lines)

    # AI Notice 탭 기록 (전문 + 구조화 리포트)
    ai_notices.add("브리핑", f"아침 브리핑 {date}", text,
                   level="info", meta=report)

    if not _config.get("send_discord"):
        return
    try:
        from backend import strategy_monitor
        strategy_monitor.send_discord(text[:1900])
    except Exception as e:
        logging.warning(f"[AiBriefing] 디스코드 전달 실패: {e}")


def _run_worker(date, model):
    now = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        context = _build_context()
        if not context:
            _save(date, status="error", error="보유 종목이 없습니다.", finished_at=now())
            return
        claude_bin = shutil.which("claude")
        if not claude_bin:
            _save(date, status="error", error="Claude CLI를 찾을 수 없습니다.",
                  finished_at=now())
            return
        prompt = (
            "너는 한국 주식 투자자의 아침 브리핑 비서다. 아래 보유 종목과 일정을 바탕으로 "
            "장 시작 전 브리핑을 작성하라.\n"
            "1) 간밤 미국 증시·주요 매크로 이슈를 확인하고\n"
            "2) 보유 종목의 최신 뉴스·공시를 웹 검색으로 확인해 영향(긍정/부정/중립)을 평가하고\n"
            "3) 오늘/이번 주 일정이 보유 종목에 미칠 영향과, 보유 전략(목표가/손절가)과 "
            "배치되는 이벤트를 하이라이트하라.\n\n"
            + context + OUTPUT_FORMAT_GUIDE)
        proc = subprocess.run(
            [claude_bin, "-p", prompt, "--model", model,
             "--allowedTools", "WebSearch,WebFetch"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=RUN_TIMEOUT_SEC, creationflags=_NO_WINDOW)
        raw = (proc.stdout or "").strip()
        if proc.returncode != 0 or not raw:
            err = (proc.stderr or "").strip()[:500] or "Claude CLI 실행 실패 (응답 없음)"
            _save(date, status="error", error=err, raw_text=raw, finished_at=now())
            return
        report = _extract_report(raw)
        if report is None:
            _save(date, status="error", error="응답에서 브리핑 JSON을 찾지 못했습니다.",
                  raw_text=raw, finished_at=now())
            return
        _save(date, status="done",
              report_json=json.dumps(report, ensure_ascii=False),
              raw_text=raw, error=None, finished_at=now())
        logging.info(f"[AiBriefing] 브리핑 완료: {date}")
        _deliver(date, report)
        if _engine is not None:
            _engine.add_log(f"아침 브리핑 생성 완료 ({date})")
    except subprocess.TimeoutExpired:
        _save(date, status="error", error=f"실행 시간 초과 ({RUN_TIMEOUT_SEC}초)",
              finished_at=now())
    except Exception as e:
        logging.error(f"[AiBriefing] 브리핑 실패: {e}", exc_info=True)
        _save(date, status="error", error=str(e), finished_at=now())


def run(date=None, model=None):
    """브리핑 실행 (백그라운드). 이미 실행 중이면 False."""
    date = date or datetime.now().strftime("%Y-%m-%d")
    model = (model or _config.get("model") or DEFAULT_MODEL).strip()
    with _run_lock:
        with _conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM briefings WHERE status = 'running' LIMIT 1").fetchone()
        if row:
            return False
        _save(date, status="running", error=None, report_json=None, raw_text=None,
              model=model, started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              finished_at=None)
    threading.Thread(target=_run_worker, args=(date, model), daemon=True).start()
    return True


def get_briefing(date=None):
    with _conn() as conn:
        if date:
            row = conn.execute("SELECT * FROM briefings WHERE date = ?", (date,)).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM briefings ORDER BY date DESC LIMIT 1").fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["report"] = json.loads(d.pop("report_json") or "null")
    except Exception:
        d["report"] = None
    return d


def list_briefings(limit=14):
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, date, status, model, started_at, finished_at, error "
            "FROM briefings ORDER BY date DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def _auto_loop():
    """평일 설정 시각 이후 하루 1회 자동 브리핑"""
    logging.info("[AiBriefing] 자동 브리핑 스레드 시작")
    while True:
        time.sleep(300)
        try:
            if not _config.get("auto_run") or _engine is None:
                continue
            now = datetime.now()
            if now.weekday() >= 5:
                continue
            if now.strftime("%H:%M") < str(_config.get("time", "08:00")):
                continue
            today = now.strftime("%Y-%m-%d")
            with _conn() as conn:
                row = conn.execute("SELECT status FROM briefings WHERE date = ?",
                                   (today,)).fetchone()
            if row:  # 오늘 이미 실행됨(성공/실패 무관 — 재시도는 수동으로)
                continue
            if run(date=today):
                logging.info(f"[AiBriefing] 자동 브리핑 시작: {today}")
        except Exception as e:
            logging.error(f"[AiBriefing] 자동 브리핑 오류: {e}", exc_info=True)


def start(engine):
    """엔진 시작 시 1회 호출"""
    global _engine, _thread
    _engine = engine
    init_db()
    _load_config()
    if _thread is None or not _thread.is_alive():
        _thread = threading.Thread(target=_auto_loop, daemon=True,
                                   name="AiBriefingThread")
        _thread.start()
