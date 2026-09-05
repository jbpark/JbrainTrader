---
name: SessionAnalyzer
description: 특정 세션의 로그를 분석하여 코드 변경점 및 작업 내용을 요약해 주는 지능형 스킬입니다.
---

# SessionAnalyzer 스킬 가이드

사용자로부터 특정 **세션 ID (해시)** 또는 **작업 시점**을 입력받았을 때, 해당 세션의 로컬 로그 파일(`C:\Users\<USER>\.gemini\antigravity\brain\{ID}\.system_generated\logs\overview.txt`)을 심층 분석하여 다음 항목을 도출합니다.

## 핵심 기능
1.  **전후 코드 차이 분석 (Code Diff)**: 해당 세션에서 실제로 수정된 코드 블록을 추출합니다.
2.  **작업 성공 여부 평가**: 오류 발생 여부 및 해결된 문제점을 정리합니다.
3.  **지식 자산화 (Knowledge Extraction)**: 향후 참고할 만한 전략이나 설정 값을 요약합니다.

## 사용 방법
*   `"ID [세션ID] 세션에서 작업한 내용을 자세히 알려줘"`
*   `"저번 QQQ 매수 로직 수정한 세션 분석해줘"`

---
작동 방식:
1.  로컬 로그 디렉토리에서 검색
2.  `overview.txt`를 읽어 전체 컨텍스트 파악
3.  최종 결과물(Markdown)을 사용자에게 응답
