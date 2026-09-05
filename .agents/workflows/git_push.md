---
description: 현재 변경 내용을 요약하여 git add, commit, push를 자동 실행합니다.
---

# git_push 워크플로우

## 절차

1. `git status --short` 명령으로 변경된 파일 목록을 확인합니다.
2. `git diff --stat` 명령으로 변경 통계를 확인합니다.
3. 변경된 파일 목록과 diff 내용을 기반으로, **한글**로 간결한 커밋 메시지를 자동 생성합니다.
   - 형식: `[요약] 세부내용1, 세부내용2`
   - 예시: `[바이낸스 연동] 코인 로그인/매매 API 추가, 환경설정 탭 추가`
4. 다음 명령을 순서대로 실행합니다:

// turbo
```
git add -A
```

// turbo
```
git commit -m "생성한 커밋 메시지"
```

// turbo
```
git push
```

5. push 결과를 사용자에게 보고합니다.
