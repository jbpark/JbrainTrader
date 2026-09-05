#!/usr/bin/env python3
"""UserPromptSubmit 훅 — Claude CLI / Antigravity CLI 입력을 jbrain_trader 백엔드에 기록.

- 이 프로젝트(스크립트 위치 기준) 안에서 실행된 프롬프트만 기록한다.
- 백엔드(기본 http://localhost:5000)가 꺼져 있으면 조용히 종료하므로
  CLI 동작에는 영향이 없다.
- 첫 번째 인자(또는 JBRAIN_TRIGGER_TYPE 환경변수)로 CLI 종류를 구분한다:
  claude_cli(기본) / antigravity_cli
"""
import json
import sys
import os
import urllib.request
from pathlib import Path

BASE_URL = os.environ.get("JBRAIN_BASE_URL", "http://localhost:5000")
TEMP_DIR = Path(os.environ.get("TEMP", os.environ.get("TMP", "/tmp")))
PROJECT_ROOT = Path(__file__).resolve().parent

TRIGGER_TYPE = (sys.argv[1] if len(sys.argv) > 1 else
                os.environ.get("JBRAIN_TRIGGER_TYPE", "claude_cli")).strip() or "claude_cli"

# 하네스가 주입한 자동 메시지(백그라운드 완료 알림 등)는 새 작업으로 등록하지 않는다.
INJECTED_PREFIXES = ("<task-notification>", "<system-reminder>",
                     "<local-command-stdout>", "<command-name>",
                     "<local-command-caveat>")


def main():
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        return

    prompt = (payload.get("prompt") or "").strip()
    session_id = payload.get("session_id") or "default"
    cwd = payload.get("cwd") or os.getcwd()

    if not prompt or prompt.startswith(INJECTED_PREFIXES):
        return

    # 이 프로젝트 밖에서 입력된 프롬프트는 무시 (전역 훅으로 등록해도 안전)
    try:
        cwd_path = Path(cwd).resolve()
        if cwd_path != PROJECT_ROOT and PROJECT_ROOT not in cwd_path.parents:
            return
    except Exception:
        return

    title = prompt.split("\n")[0].strip()[:100] or "CLI 작업"
    try:
        body = json.dumps(
            {"title": title, "prompt": prompt, "trigger_type": TRIGGER_TYPE,
             "session_id": session_id, "cwd": str(cwd_path)},
            ensure_ascii=False,
        ).encode()
        req = urllib.request.Request(
            f"{BASE_URL}/cli/tasks",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            result = json.loads(r.read().decode())
    except Exception:
        return  # 백엔드가 없으면 조용히 종료

    task_id = result.get("id")
    if not task_id:
        return

    # Stop 훅이 결과를 기록할 수 있도록 세션-작업 매핑 저장
    state_file = TEMP_DIR / f"jbrain_cli_{session_id}.json"
    try:
        state_file.write_text(json.dumps({"task_id": task_id}), encoding="utf-8")
    except Exception:
        pass


if __name__ == "__main__":
    main()
