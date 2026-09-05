# JbrainTrader 데모 페이지

JbrainTrader 웹 대시보드의 **메뉴 구조와 기능을 소개하는 정적 데모 사이트**입니다.
모든 숫자는 `data.js`에 들어 있는 **Mock 데이터**이며, 실제 계좌·시세·매매 기록이 아닙니다.
백엔드 호출이 전혀 없어 브라우저만 있으면 어디서든 열립니다.

## 구성

| 파일 | 역할 |
|------|------|
| `index.html` | 셸(배너, 사이드바, 메인, 모달, 도우미) |
| `style.css` | 실제 대시보드와 같은 다크 테마 팔레트 |
| `data.js` | Mock 데이터 (계좌, 보유종목, 관심종목, 로그, 전략, AI 결과, 일정, 알림, 매매일지, CLI 기록) |
| `app.js` | 메뉴별 화면 렌더링, 메뉴 안내문, 데모 상호작용 |
| `_headers` | Cloudflare Pages 보안 헤더 |

메뉴는 해시 라우팅(`#/HOLDINGS`, `#/STRATEGY` …)으로 이동하므로 특정 화면을 링크로 공유할 수 있습니다.

## 메뉴별 데모 내용

| 메뉴 | 데모에서 볼 수 있는 것 |
|------|------|
| 계정 | 계좌 카드, 시스템 상태(게이트웨이·엔진·DB·Discord), 월 누적 손익 그래프, 실행 흐름 |
| 로그 | 2~3초마다 가짜 TICK/SIGNAL/ORDER 로그가 흘러가는 실시간 로그 |
| 보유종목 | 평가손익 표, 전체 분석·시트 업로드 버튼(토스트로 동작 설명) |
| 관심종목 | 종목 추가, 전략 변경, 시작/중지 토글, 삭제 |
| 데이터 | 시세·매매·백테스트·시뮬레이션 트리 메뉴, 백테스트 샘플 결과 |
| 수집기 | 종목 칩 추가, 가짜 수집 진행률과 로그 |
| 전략 | 단일/듀얼 전략 파일 목록, DSL 내용 보기·편집 |
| AI 종목 | 프로파일 선택, 실행 시 가짜 결과 생성 |
| AI 매매 | 목표가·손절가 카드, 가격대 그래프 |
| AI캘린더 | 월간 달력과 일정 종류별 색상 |
| AI Notice | 아침 브리핑·전략 이탈·복기·스코어카드 알림 기록 |
| 매매일지 | 날짜별 손익 달력, 매매별/종목별 상세 |
| CLI 작업 | Claude CLI 작업 기록 펼치기 |
| 환경 설정 | 브로커·키움·바이낸스·Discord 설정 (마스킹된 읽기 전용) |

각 화면 오른쪽 안내 상자에 "무엇을 보여주나 / 사용 순서 / 실제 시스템에서는 / 데모에서 해볼 것"이 표시됩니다.

## 로컬에서 보기

```bash
python -m http.server 8090 --directory demo
```

브라우저에서 http://localhost:8090 을 엽니다. 빌드 단계는 없습니다.

## Cloudflare Pages 배포

### 방법 A. 직접 업로드 (저장소 연동 없음, 가장 간단)

1. Cloudflare 대시보드 → **Workers & Pages** → **Create** → **Pages** → **Upload assets**
2. 프로젝트 이름 입력 (예: `jbraintrader-demo`)
3. `demo/` 폴더 안의 파일들을 드래그 앤 드롭 (폴더 자체가 아니라 안의 파일들을 올려야 `index.html`이 루트에 옵니다)
4. **Deploy site** → `https://jbraintrader-demo.pages.dev` 발급

갱신할 때는 같은 프로젝트에서 **Create new deployment**로 다시 업로드합니다.

### 방법 B. Wrangler CLI

```bash
npm install -g wrangler
wrangler login
wrangler pages deploy demo --project-name jbraintrader-demo
```

### 방법 C. Git 연동 (자동 배포)

1. **Workers & Pages** → **Create** → **Pages** → **Connect to Git**에서 이 저장소 선택
2. 빌드 설정
   - Framework preset: `None`
   - Build command: (비움)
   - Build output directory: `demo`
3. `main`에 push할 때마다 자동 배포됩니다.

## 데이터 수정

`data.js`의 `DEMO.*` 객체만 바꾸면 화면이 따라 바뀝니다. 새 화면을 추가할 때는 `app.js`의 `VIEWS`(메뉴), `GUIDE`(안내문), `R.<KEY>`(렌더러) 세 곳에 항목을 추가합니다.

## 주의

- 실제 백엔드 주소, API 키, 실계좌 데이터가 이 폴더에 들어가지 않도록 유지하세요.
- 데모 배너와 "AI가 생성한 참고용 정보" 문구는 투자 오해를 막기 위한 것이므로 지우지 마세요.
