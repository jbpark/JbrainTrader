#!/usr/bin/env python3
"""Stop 훅 — Claude CLI / Antigravity CLI 응답 완료 시 jbrain_trader 백엔드에 결과 기록.

cli_hook_prompt.py 가 남긴 세션-작업 매핑을 읽어, 트랜스크립트(JSONL)에서
모델·실행 단계·최종 응답을 추출한 뒤 /cli/tasks/{id}/log-result 로 전송한다.
백엔드가 꺼져 있으면 조용히 종료한다.
"""
import json
import sys
import os
import urllib.request
from pathlib import Path

BASE_URL = os.environ.get("JBRAIN_BASE_URL", "http://localhost:5000")
TEMP_DIR = Path(os.environ.get("TEMP", os.environ.get("TMP", "/tmp")))

TRIGGER_TYPE = (sys.argv[1] if len(sys.argv) > 1 else
                os.environ.get("JBRAIN_TRIGGER_TYPE", "claude_cli")).strip() or "claude_cli"


def _parse_transcript(transcript_path: str) -> dict:
    """JSONL 트랜스크립트에서 세션 정보, 실행 단계, 최종 응답을 추출한다."""
    result = {
        "session_id": "", "model": "", "log_lines": [],
        "first_prompt": "", "output": "", "duration_ms": 0,
    }
    if not transcript_path:
        return result
    try:
        p = Path(transcript_path)
        if not p.exists():
            return result
        last_text = ""
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            t = obj.get("type", "")
            if not result["session_id"] and obj.get("sessionId"):
                result["session_id"] = obj["sessionId"]
            ts_hm = obj.get("timestamp", "")[11:16]  # ISO에서 HH:MM
            if t == "user" and not result["first_prompt"]:
                content = obj.get("message", {}).get("content", "")
                if isinstance(content, str):
                    result["first_prompt"] = content.strip()[:200]
                elif isinstance(content, list):
                    texts = [c.get("text", "") for c in content if c.get("type") == "text"]
                    result["first_prompt"] = " ".join(texts).strip()[:200]
            if t == "assistant":
                msg = obj.get("message", {})
                if not result["model"] and msg.get("model"):
                    result["model"] = msg["model"]
                for c in msg.get("content", []):
                    ct = c.get("type", "")
                    if ct == "tool_use":
                        name = c.get("name", "")
                        inp = c.get("input", {})
                        if name in ("Read", "Edit", "Write"):
                            desc = inp.get("file_path", "")
                        elif name in ("Bash", "PowerShell"):
                            desc = inp.get("command", "")[:80]
                        elif name == "Glob":
                            desc = inp.get("pattern", "")
                        elif name == "Grep":
                            desc = f"{inp.get('pattern', '')} in {inp.get('path', '.')}"
                        else:
                            desc = json.dumps(inp, ensure_ascii=False)[:80]
                        result["log_lines"].append(
                            {"level": "INFO", "msg": f"[{name}] {desc}", "ts": ts_hm}
                        )
                    elif ct == "text":
                        text = c.get("text", "").strip()
                        if text:
                            last_text = text
            elif t == "system" and obj.get("subtype") == "turn_duration":
                result["duration_ms"] = obj.get("durationMs", 0)
        result["output"] = last_text[:8000]
    except Exception:
        pass
    return result


def _build_full_output(tr: dict) -> str:
    """실행 요약 텍스트 구성 — 최종 응답이 잘리지 않게 응답 예산을 먼저 확보한다."""
    MAX_TOTAL = 8000

    head = []
    if tr["session_id"]:
        head.append(f"세션 ID : {tr['session_id']}")
    if tr["model"]:
        head.append(f"모델    : {tr['model']}")
    if tr["duration_ms"]:
        head.append(f"소요시간: {tr['duration_ms'] / 1000:.1f}초")
    if tr["first_prompt"]:
        head.append("")
        head.append("── 첫 메시지 ──")
        head.append(f"  {tr['first_prompt']}")

    tail = []
    if tr["output"]:
        tail.append("")
        tail.append("── 최종 응답 ──")
        tail.append(tr["output"][:6000])

    steps = []
    budget = MAX_TOTAL - len("\n".join(head)) - len("\n".join(tail)) - 40
    if tr["log_lines"] and budget > 0:
        steps.append("")
        steps.append("── 실행 과정 ──")
        used = sum(len(s) + 1 for s in steps)
        omitted = 0
        for i, l in enumerate(tr["log_lines"], 1):
            line = f"  {i}. {l.get('msg', '')}"
            if used + len(line) + 1 > budget:
                omitted = len(tr["log_lines"]) - i + 1
                break
            steps.append(line)
            used += len(line) + 1
        if omitted:
            steps.append(f"  … 이후 {omitted}개 단계 생략")

    return "\n".join(head + steps + tail) or "(출력 없음)"


def main():
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        return

    session_id = payload.get("session_id") or "default"
    transcript_path = payload.get("transcript_path") or ""

    state_file = TEMP_DIR / f"jbrain_cli_{session_id}.json"
    if not state_file.exists():
        return

    # 상태 파일은 삭제하지 않는다 — 턴이 여러 번 이어지는 경우 이후 Stop 훅이
    # 같은 작업의 답변을 최신 내용으로 갱신하고, 새 프롬프트가 오면
    # prompt 훅이 새 작업으로 덮어쓴다.
    try:
        task_id = json.loads(state_file.read_text(encoding="utf-8")).get("task_id")
    except Exception:
        return
    if not task_id:
        return

    tr = _parse_transcript(transcript_path)

    try:
        body = json.dumps(
            {"answer": tr["output"], "output": _build_full_output(tr),
             "status": "done", "model": tr["model"],
             "cli_session_id": tr["session_id"],
             "duration_ms": tr["duration_ms"],
             "log_lines": tr["log_lines"],
             "trigger_type": TRIGGER_TYPE},
            ensure_ascii=False,
        ).encode()
        req = urllib.request.Request(
            f"{BASE_URL}/cli/tasks/{task_id}/log-result",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception:
        pass


if __name__ == "__main__":
    main()
