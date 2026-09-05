---
description: 특정 세션의 프롬프트 대화 원문(Transcript) 출력
---

사용자가 `/transcript [세션ID]`를 입력하면 다음 작업을 수행합니다.

1.  **ID 식별 및 경로 구성**: 세션 ID가 입력된 경우 해당 ID를 사용하고, **ID가 없는 경우 오늘(현재) 세션 ID**(`5829e938`)를 기본값으로 설정합니다.
    *   경로: `C:\Users\<USER>\.gemini\antigravity\brain\{SessionID}\.system_generated\logs\overview.txt`
2.  **로그 파일 읽기**: `view_file` 또는 `run_command`를 사용하여 해당 대화 원문 파일을 로드합니다.
3.  **내용 표시**: 대화 내용이 길 경우 핵심 질문(USER)과 답변(ASSISTANT) 위주로 정리하여 아티팩트로 제공합니다.
---
// turbo
// 이 워크플로우는 과거 대화의 맥락을 빠르게 복기할 수 있도록 원문 그대로를 노출하는 목적으로 작동합니다.
