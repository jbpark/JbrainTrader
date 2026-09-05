# -*- coding: utf-8 -*-
"""전략 이탈 감시 — 보유 종목의 현재가를 AI 매매 전략(손절가/목표가)과 주기적으로 비교.

- 장중(평일 09:00~15:30)에 주기적으로 계좌를 새로고침(REFRESH_ACCOUNT)한 뒤,
  보유 종목별 최신 AI 전략의 손절가/목표가와 현재가를 비교한다.
- 손절가 근접/도달, 목표가 도달 시 디스코드(봇 토큰 REST)와 엔진 로그로 알림.
- 같은 상태가 유지되는 동안에는 다시 알리지 않고, 상태가 바뀌거나
  새 전략 분석(finished_at 변경)이 나오면 다시 평가한다.
- auto_reanalyze가 켜져 있으면 손절/목표 도달 시 해당 프로파일로 AI 재분석을 자동 실행한다.

설정은 backend/settings/strategy_monitor.json에 저장되며 API로 변경할 수 있다.
"""
import os
import json
import logging
import threading
import time
from collections import deque
from datetime import datetime

try:
    from backend import ai_trades
    from backend import ai_notices
except ImportError:
    import ai_trades
    import ai_notices

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "settings", "strategy_monitor.json")

DEFAULT_CONFIG = {
    "enabled": True,          # 감시 on/off
    "interval_sec": 60,       # 감시 주기 (초)
    "near_stop_pct": 3.0,     # 손절가 '근접' 판정 여유 (%)
    "auto_reanalyze": False,  # 손절/목표 도달 시 AI 재분석 자동 실행
    "market_open": "09:00",
    "market_close": "15:30",
}

# 상태 코드: OK < NEAR_STOP < HIT_STOP / HIT_TARGET
STATE_LABELS = {
    "HIT_STOP": "손절가 도달",
    "NEAR_STOP": "손절가 근접",
    "HIT_TARGET": "목표가 도달",
    "OK": "정상",
}
STATE_ICONS = {"HIT_STOP": "🔴", "NEAR_STOP": "🟠", "HIT_TARGET": "🟢"}

_engine = None
_thread = None
_lock = threading.Lock()
_config = dict(DEFAULT_CONFIG)
# ticker -> {"state": str, "finished_at": str}  (전략이 갱신되면 다시 평가)
_last_states = {}
_alerts = deque(maxlen=100)   # 최근 알림 이력
_last_check = None            # 마지막 점검 시각 문자열


def _load_config():
    global _config
    try:
        if os.path.isfile(CONFIG_PATH):
            with open(CONFIG_PATH, encoding="utf-8") as f:
                saved = json.load(f)
            _config = {**DEFAULT_CONFIG, **{k: v for k, v in saved.items()
                                            if k in DEFAULT_CONFIG}}
    except Exception as e:
        logging.warning(f"[StrategyMonitor] 설정 로드 실패(기본값 사용): {e}")


def _save_config():
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(_config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.warning(f"[StrategyMonitor] 설정 저장 실패: {e}")


def _to_num(v):
    """'1,550,000' / 1550000 / None → float 또는 None"""
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _fmt(v):
    try:
        return f"{int(round(float(v))):,}"
    except (TypeError, ValueError):
        return str(v)


def _is_market_hours(cfg=None):
    cfg = cfg or _config
    now = datetime.now()
    if now.weekday() >= 5:  # 토/일
        return False
    hhmm = now.strftime("%H:%M")
    return cfg["market_open"] <= hhmm <= cfg["market_close"]


def _latest_entry(entries):
    """같은 종목의 전략 목록에서 finished_at이 가장 최근인 항목"""
    if not entries:
        return None
    return max(entries, key=lambda e: str(e.get("finished_at") or ""))


def _send_discord(text):
    """디스코드 봇 토큰으로 로그 채널에 메시지 전송 (REST). 실패해도 감시는 계속."""
    token = channel_id = ""
    if _engine is not None:
        dc = (_engine.accounts or {}).get("discord_config") or {}
        token = str(dc.get("bot_token") or "").strip()
        channel_id = str(dc.get("log_channel_id") or "").strip()
    if not token or not channel_id:
        # 통합 봇과 같은 설정(discord_bot/.env)을 폴백으로 사용
        token = token or os.getenv("DISCORD_BOT_TOKEN", "").strip()
        channel_id = channel_id or os.getenv("DISCORD_LOG_CHANNEL_ID", "").strip()
    if not token or not channel_id:
        return False
    try:
        import requests
        r = requests.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {token}"},
            json={"content": text}, timeout=10)
        if r.status_code >= 300:
            logging.warning(f"[StrategyMonitor] 디스코드 전송 실패 ({r.status_code}): {r.text[:200]}")
            return False
        return True
    except Exception as e:
        logging.warning(f"[StrategyMonitor] 디스코드 전송 오류: {e}")
        return False


# 다른 모듈(ai_review, ai_briefing 등)에서도 같은 채널로 알림을 보낼 수 있게 공개
def send_discord(text):
    return _send_discord(text)


def _evaluate_holding(holding, entry, near_stop_pct):
    """보유 종목 1건 평가 → (state, detail dict) 또는 (None, None) (전략/가격 없음)"""
    strategy = entry.get("strategy") or {}
    cur = _to_num(holding.get("current_price"))
    stop = _to_num(strategy.get("stop_loss"))
    target = _to_num(strategy.get("target_price"))
    if cur is None or cur <= 0 or (stop is None and target is None):
        return None, None

    state = "OK"
    if stop is not None and cur <= stop:
        state = "HIT_STOP"
    elif target is not None and cur >= target:
        state = "HIT_TARGET"
    elif stop is not None and cur <= stop * (1 + near_stop_pct / 100.0):
        state = "NEAR_STOP"

    detail = {
        "ticker": str(holding.get("ticker") or ""),
        "name": str(holding.get("name") or entry.get("ticker_name") or ""),
        "current_price": cur, "stop_loss": stop, "target_price": target,
        "ratio": _to_num(holding.get("ratio")),
        "profile_id": entry.get("profile_id"),
        "profile_name": str(entry.get("profile_name") or ""),
        "finished_at": str(entry.get("finished_at") or ""),
    }
    return state, detail


def _build_message(state, d):
    icon = STATE_ICONS.get(state, "ℹ️")
    label = STATE_LABELS.get(state, state)
    ratio = f"{d['ratio']:+.2f}%" if d.get("ratio") is not None else "-"
    lines = [f"{icon} **[{label}] {d['name']}({d['ticker']})**",
             f"현재가 {_fmt(d['current_price'])}원 · 수익률 {ratio}"]
    if state in ("HIT_STOP", "NEAR_STOP") and d.get("stop_loss") is not None:
        gap = (d["current_price"] - d["stop_loss"]) / d["current_price"] * 100
        lines.append(f"손절가 {_fmt(d['stop_loss'])}원 (여유 {gap:+.2f}%)")
    if d.get("target_price") is not None:
        lines.append(f"목표가 {_fmt(d['target_price'])}원")
    lines.append(f"전략: {d['profile_name']} ({d['finished_at']} 분석)")
    return "\n".join(lines)


def _maybe_reanalyze(state, d, results):
    """손절/목표 도달 시 해당 프로파일로 AI 재분석 실행 (설정 시)"""
    if state not in ("HIT_STOP", "HIT_TARGET") or not _config.get("auto_reanalyze"):
        return
    try:
        started = ai_trades.run_profile(d["profile_id"], d["ticker"], d["name"])
        note = "AI 재분석 시작" if started else "AI 재분석 대기 (프로파일 실행 중)"
        results.append(note)
        if _engine is not None:
            _engine.add_log(f"[전략감시] {d['name']}({d['ticker']}) {note}")
    except Exception as e:
        logging.warning(f"[StrategyMonitor] 재분석 실행 실패({d['ticker']}): {e}")


def _refresh_holdings():
    """브로커에서 보유 종목 현재가를 새로 받아온다. (키움: REFRESH_ACCOUNT → LOGIN_RESULT 갱신)"""
    if _engine is None or _engine.status != "CONNECTED":
        return False
    account = _engine.data_store.get("account") or {}
    broker = account.get("broker", "KIWOOM")
    try:
        if broker == "KOREA_INVESTMENT" and getattr(_engine, "kis_broker", None):
            kis_data = _engine.kis_broker.get_balance()
            if kis_data:
                account["balance"] = kis_data["balance"]
                account["holdings"] = kis_data["holdings"]
            return True
        _engine.zmq_send({
            "action": "REFRESH_ACCOUNT",
            "acc_no": account.get("acc_no"),
            "market": account.get("market", "DOMESTIC"),
        })
        time.sleep(5)  # 게이트웨이 TR 조회 → LOGIN_RESULT 수신 대기
        return True
    except Exception as e:
        logging.warning(f"[StrategyMonitor] 계좌 새로고침 실패: {e}")
        return False


def check_once(refresh=True, dry_run=False, force=False):
    """보유 종목 전체를 1회 점검. 반환: 평가 결과 목록.

    refresh: 브로커에서 현재가를 새로 받아올지 (연결 안 됐으면 저장된 값으로 평가)
    dry_run: True면 알림/재분석 없이 평가 결과만 반환 (상태 기록도 하지 않음)
    force:   장 시간 외에도 점검 실행
    """
    global _last_check
    if _engine is None:
        return {"error": "엔진이 초기화되지 않았습니다."}
    if not force and not _is_market_hours():
        return {"skipped": "장 시간이 아닙니다.", "checked": 0, "alerts": []}

    if refresh:
        _refresh_holdings()

    holdings = (_engine.data_store.get("account") or {}).get("holdings") or []
    try:
        strategies = ai_trades.list_strategies()
    except Exception as e:
        logging.warning(f"[StrategyMonitor] 전략 조회 실패: {e}")
        strategies = {}

    near_pct = float(_config.get("near_stop_pct", 3.0))
    evaluated, new_alerts = [], []
    seen_tickers = set()

    for h in holdings:
        if not isinstance(h, dict):
            continue
        ticker = str(h.get("ticker") or "").strip()
        entry = _latest_entry(strategies.get(ticker))
        if not entry:
            continue
        state, d = _evaluate_holding(h, entry, near_pct)
        if state is None:
            continue
        seen_tickers.add(ticker)
        evaluated.append({"state": state, "label": STATE_LABELS[state], **d})
        if dry_run:
            continue

        prev = _last_states.get(ticker)
        # 새 전략 분석이 나오면 이전 상태를 무효화하고 다시 평가
        if prev and prev.get("finished_at") != d["finished_at"]:
            prev = None
        changed = (prev is None) or (prev.get("state") != state)
        _last_states[ticker] = {"state": state, "finished_at": d["finished_at"]}

        if changed and state != "OK":
            msg = _build_message(state, d)
            notes = []
            _maybe_reanalyze(state, d, notes)
            full_msg = msg + (f"\n→ {notes[0]}" if notes else "")
            # AI Notice 탭에도 기록 (디스코드 전송 성공 여부와 무관)
            level = {"HIT_STOP": "critical", "NEAR_STOP": "warning",
                     "HIT_TARGET": "good"}.get(state, "info")
            ai_notices.add("전략감시",
                           f"[{STATE_LABELS[state]}] {d['name']}({ticker})",
                           full_msg, level=level, meta=d,
                           market="DOMESTIC" if str(ticker).isdigit() else "OVERSEAS")
            sent = _send_discord(full_msg)
            _engine.add_log(f"[전략감시] {STATE_LABELS[state]}: {d['name']}({ticker}) "
                            f"현재가 {_fmt(d['current_price'])}원"
                            + (f" (디스코드 전송 실패)" if not sent else ""))
            alert = {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                     "state": state, "label": STATE_LABELS[state],
                     "ticker": ticker, "name": d["name"],
                     "current_price": d["current_price"],
                     "discord_sent": sent, "notes": notes}
            _alerts.append(alert)
            new_alerts.append(alert)

    if not dry_run:
        # 매도 등으로 사라진 종목은 상태 초기화 (재매수 시 새로 평가)
        for t in list(_last_states.keys()):
            if t not in seen_tickers:
                del _last_states[t]

    _last_check = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {"checked": len(evaluated), "results": evaluated, "alerts": new_alerts}


def _loop():
    logging.info("[StrategyMonitor] 감시 스레드 시작")
    while True:
        try:
            interval = max(15, int(_config.get("interval_sec", 60)))
        except (TypeError, ValueError):
            interval = 60
        time.sleep(interval)
        try:
            if not _config.get("enabled"):
                continue
            if _engine is None or _engine.status != "CONNECTED":
                continue
            if not _is_market_hours():
                continue
            check_once(refresh=True)
        except Exception as e:
            logging.error(f"[StrategyMonitor] 감시 오류: {e}", exc_info=True)


def start(engine):
    """엔진 시작 시 1회 호출 — 설정 로드 후 감시 스레드 기동"""
    global _engine, _thread
    _engine = engine
    _load_config()
    if _thread is None or not _thread.is_alive():
        _thread = threading.Thread(target=_loop, daemon=True,
                                   name="StrategyMonitorThread")
        _thread.start()


def get_status():
    return {
        "config": dict(_config),
        "running": _thread is not None and _thread.is_alive(),
        "market_hours": _is_market_hours(),
        "engine_connected": _engine is not None and _engine.status == "CONNECTED",
        "last_check": _last_check,
        "states": {t: s.get("state") for t, s in _last_states.items()},
        "recent_alerts": list(_alerts)[-20:],
    }


def update_config(data):
    """설정 일부 갱신 (허용된 키만). 반환: 갱신된 전체 설정"""
    global _config
    with _lock:
        for k in DEFAULT_CONFIG:
            if k not in (data or {}):
                continue
            v = data[k]
            if k in ("enabled", "auto_reanalyze"):
                _config[k] = bool(v)
            elif k == "interval_sec":
                _config[k] = max(15, int(v))
            elif k == "near_stop_pct":
                _config[k] = max(0.0, float(v))
            else:  # market_open / market_close — "HH:MM" 형식 검증
                s = str(v).strip()
                datetime.strptime(s, "%H:%M")
                _config[k] = s
        _save_config()
    return dict(_config)
