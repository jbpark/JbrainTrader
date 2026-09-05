/* ============================================================
   JbrainTrader 데모 — 화면 로직
   실제 백엔드 호출은 없으며, 모든 동작은 data.js의 Mock 데이터로 재현합니다.
   ============================================================ */
(function () {
  'use strict';
  const $ = (sel, root = document) => root.querySelector(sel);
  const fmt = (n, d = 0) => Number(n).toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d });
  const sign = (n) => (n > 0 ? '+' : '') + fmt(n);
  const pct = (n) => (n > 0 ? '+' : '') + n.toFixed(2) + '%';
  const cls = (n) => (n > 0 ? 'up' : n < 0 ? 'down' : '');
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const now = () => new Date().toTimeString().slice(0, 8);

  /* ---------- 공통 UI: 토스트 / 모달 ---------- */
  function toast(msg, ok = false) {
    const wrap = $('#toasts');
    const el = document.createElement('div');
    el.className = 'toast' + (ok ? ' ok' : '');
    el.textContent = msg;
    wrap.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .3s'; setTimeout(() => el.remove(), 300); }, 2800);
  }
  const demoOnly = (what) => toast(`데모 모드: "${what}"은(는) 실제로 실행되지 않습니다. 실제 시스템에서는 엔진(backend/main.py)이 처리합니다.`);
  window.demoOnly = demoOnly;

  /* ---------- 메뉴 정의 ---------- */
  const VIEWS = [
    { key: 'MAIN', icon: '👤', label: '계정', featured: false },
    { key: 'LOG', icon: '📜', label: '로그' },
    { key: 'HOLDINGS', icon: '📁', label: '보유종목' },
    { key: 'MONITORING', icon: '🖥️', label: '관심종목' },
    { key: 'DATA', icon: '📂', label: '데이터' },
    { key: 'COLLECTOR', icon: '📥', label: '수집기' },
    { key: 'STRATEGY', icon: '⚡', label: '전략', featured: true },
    { key: 'AIPICKS', icon: '✨', label: 'AI 종목', featured: true },
    { key: 'AITRADES', icon: '🤖', label: 'AI 매매', featured: true },
    { key: 'AICALENDAR', icon: '📅', label: 'AI캘린더', featured: true },
    { key: 'AINOTICE', icon: '🔔', label: 'AI Notice', featured: true },
    { key: 'JOURNAL', icon: '📒', label: '매매일지' },
    { key: 'CLI', icon: '💻', label: 'CLI 작업' },
    { key: 'SETTINGS', icon: '⚙️', label: '환경 설정' },
  ];

  /* ---------- 메뉴별 설명(가이드) ---------- */
  const GUIDE = {
    MAIN: {
      summary: '연결된 증권사 계좌의 사용자명·계좌번호·예수금과 시스템 각 구성요소의 상태를 한눈에 보는 시작 화면입니다.',
      shows: ['사용자명, 계좌번호(복수 계좌 선택), 예수금', '국내/해외 시장 전환 토글', '게이트웨이·엔진·DB·Discord 연결 상태', '오늘 실현손익 요약'],
      steps: ['왼쪽 "연결 설정"에서 키움 모의투자 또는 실거래 로그인', '계좌가 2개 이상이면 계좌번호 드롭다운에서 선택', '해외 계좌가 연결되면 국내/해외 토글로 시장 전환'],
      real: '실제로는 키움 OpenAPI 게이트웨이(32bit)가 로그인 후 계좌 목록과 예수금을 ZeroMQ로 엔진에 전달합니다.',
      tips: ['계좌번호 드롭다운을 바꿔보세요', '연결 설정 버튼을 눌러 로그인 방식 선택 화면을 확인하세요'],
    },
    LOG: {
      summary: '엔진이 내보내는 실시간 로그입니다. 시세 수신, 전략 신호, 주문 체결, AI 작업 진행이 시간순으로 흘러갑니다.',
      shows: ['[TICK] 실시간 시세 수신', '[SIGNAL] 전략 조건 충족', '[ORDER] 주문·체결', '[AI] / [GSHEET] / [DUAL] 등 부가 작업'],
      steps: ['관심종목에서 전략을 "시작"하면 해당 종목의 TICK/SIGNAL 로그가 나타남', '주문이 나가면 ORDER 로그로 체결 확인', '문제가 생기면 WARN/ERROR 로그를 먼저 확인'],
      real: '엔진은 WebSocket(:8765)으로 로그를 브라우저에 푸시하고, 같은 내용을 Discord 로그 채널에도 전송합니다.',
      tips: ['이 데모에서는 2~3초마다 가짜 로그가 자동으로 추가됩니다'],
    },
    HOLDINGS: {
      summary: '증권사 계좌의 실제 보유 종목과 평가손익입니다. 종목별로 AI 분석을 바로 요청할 수 있습니다.',
      shows: ['총 매입금액·총 평가손익·총 수익률', '종목별 수량, 매입단가, 현재가, 평가손익', '"전체 분석" — 보유 종목을 AI 프로파일로 순차 분석', '구글 시트 "보유종목" 탭 업로드'],
      steps: ['"새로고침"으로 증권사에서 보유 종목을 다시 조회', '분석할 AI 프로파일을 고르고 "전체 분석" 클릭', '결과는 AI 매매 탭에서 종목별로 확인'],
      real: '키움 opw00018(계좌평가잔고내역) 조회 결과가 표시됩니다. 해외 계좌는 별도 TR로 조회합니다.',
      tips: ['각 행의 "🤖 분석" 버튼을 눌러보세요'],
    },
    MONITORING: {
      summary: '자동매매를 돌릴 관심종목 목록입니다. 종목마다 전략 파일을 지정하고 시작/중지를 제어합니다.',
      shows: ['종목명·코드·시장·현재가', '지정된 전략(strategy/*.txt)', '상태(실행/중지), 보유주식, 실현이익', '"실제 계좌" 표시 — 실제 계좌 보유 종목인지 여부'],
      steps: ['상단 검색창에 종목명 또는 코드 입력 → 전략 선택 → "추가"', '"▶️ 시작"을 누르면 실시간 틱을 받아 전략 조건 평가 시작', '"⏹️ 중지"는 신호 평가만 멈추고 포지션은 유지', '"🔍"로 지표 분석 탭을 열어 차트와 지표 확인'],
      real: '시작하면 게이트웨이가 해당 종목 실시간 시세를 등록(SetRealReg)하고, 엔진이 틱마다 전략 조건식을 평가합니다.',
      tips: ['시작/중지 버튼을 눌러 상태가 바뀌는 것을 확인하세요', '전략 드롭다운을 바꿔보세요 (데모에서는 저장되지 않음)'],
    },
    DATA: {
      summary: '시세·매매 데이터를 가져오고 조회하며, 백테스트와 시뮬레이션을 실행하는 데이터 작업 허브입니다.',
      shows: ['시세 데이터: 가져오기 / 가상 생성 / 조회', '매매 데이터: 가져오기 / 조회 / 통계', '백테스트: 기존·랜덤·듀얼 데이터 기반 실행과 결과 조회', '시뮬레이션: 저장된 틱을 실시간처럼 재생'],
      steps: ['왼쪽 트리에서 작업 선택', '오른쪽 폼에 종목·기간·전략 입력', '실행 결과(체결 목록, 수익 곡선)는 DB에 저장되어 "조회"에서 다시 볼 수 있음'],
      real: '백테스트는 backtrader 기반 엔진이 MySQL의 일봉/분봉을 읽어 실행합니다. 듀얼 백테스트는 core/strategy/dual 모듈을 사용합니다.',
      tips: ['"백테스트 → 실행 → 기존 데이터 기반"을 눌러 샘플 결과를 보세요'],
    },
    COLLECTOR: {
      summary: 'Yahoo Finance / KRX에서 일봉·분봉 시세를 내려받아 MySQL에 저장합니다. 백테스트의 재료를 만드는 곳입니다.',
      shows: ['데이터 소스(Yahoo Finance, KRX)', '주기(1분/5분/일봉)와 기간', '종목 검색·다중 선택', '수집 진행률과 로그'],
      steps: ['데이터 소스와 주기 선택', '기간 지정 (분봉은 소스 제한으로 최근 30일 내)', '종목 검색 후 칩으로 추가', '"수집 시작" → 진행률과 로그 확인'],
      real: 'core/provider/yahoo.py, krx.py가 데이터를 받아 core/service/collector.py가 중복 제거 후 저장합니다.',
      tips: ['"수집 시작"을 눌러 가짜 수집 진행을 확인하세요'],
    },
    STRATEGY: {
      summary: '전략은 코드가 아니라 텍스트 파일(INI 형식)입니다. 이 탭에서 전략 파일을 만들고 편집합니다.',
      shows: ['단일 종목 전략(strategy/*.txt) 목록', '듀얼 ETF 전략(strategy/dual/*.txt) 목록', '선택한 전략의 DSL 내용 편집기'],
      steps: ['왼쪽 목록에서 전략 선택 → 오른쪽에 내용 표시', '[BUY_STEP_n] / [SELL_STEP_n] / [STOP_LOSS]의 condition을 수정', '"전략 저장하기" → strategy/ 폴더에 파일로 저장', '관심종목 탭에서 종목에 전략을 지정'],
      real: 'condition 식은 price, ema5, ema20, rsi, bb_upper 같은 지표 변수와 first_buy_price, avg_price 같은 포지션 변수를 사용하며, 엔진이 사전 컴파일해 틱마다 평가합니다.',
      tips: ['GOLDEN_CROSS와 DUAL_200_1X_INVERSE를 골라 두 형식의 차이를 비교해 보세요'],
    },
    AIPICKS: {
      summary: '"어떤 종목을 볼까"를 AI에게 맡깁니다. 프로파일(프롬프트)마다 종목을 선별하고 근거를 기록합니다.',
      shows: ['종목 선별 프로파일 목록 (이름·모델·프롬프트)', '실행 결과: 종목, 점수, 선정 근거', '선별 종목 재무 비교 분석'],
      steps: ['"+ 새 프로파일 생성" → 이름·모델·프롬프트 입력 후 저장', '"▶ 실행" → Claude CLI가 프롬프트를 수행', '결과 표에서 종목을 골라 관심종목 추가 또는 AI 매매 전략 생성으로 연결'],
      real: '로컬 Claude CLI(claude -p)를 호출합니다. 별도 API 키 없이 CLI 로그인만 필요하며 결과는 SQLite(ai_picks.db)에 저장됩니다.',
      tips: ['"배당_안정형" 프로파일을 선택하고 "실행"을 눌러 결과가 생성되는 흐름을 보세요'],
    },
    AITRADES: {
      summary: '보유·관심 종목 하나를 정해 진입가·목표가·손절가·비중을 AI에게 제안받습니다. 이 값이 이후 "전략 이탈 감시"의 기준이 됩니다.',
      shows: ['매매 전략 프로파일과 대상 종목', '종목 현재 포지션(보유수량·매입단가·평가손익)', '결과: 목표가, 진입 가격대, 손절가, 기대수익, 비중, 보유기간', '매수/매도 조건, 리스크 요인, 근거'],
      steps: ['프로파일 선택 → 대상 종목 지정(AI 종목 결과 또는 직접 입력)', '"▶ 실행"으로 전략 생성', '"📈 가격대 그래프"로 진입/목표/손절 구간 시각화', '"시트 업로드"로 구글 시트에 기록'],
      real: '생성된 목표가/손절가는 strategy_monitor.py가 장중 현재가와 비교해 Discord로 경고하고, strategy_scorecard.py가 일봉으로 적중 여부를 채점합니다.',
      tips: ['두 프로파일을 번갈아 선택해 결과 카드와 가격대 그래프가 바뀌는 것을 보세요'],
    },
    AICALENDAR: {
      summary: '실적 발표, 경제지표, 배당 기준일 같은 일정을 AI가 정리해 달력에 표시합니다.',
      shows: ['캘린더 프로파일 (무엇을 정리할지 지시문)', '월간 달력과 일정 종류별 색상', '주요 일정 목록'],
      steps: ['프로파일 선택 또는 새로 생성', '"실행"으로 이번 달 일정 생성', '달력에서 날짜를 눌러 상세 확인'],
      real: '결과는 ai_calendar.db에 저장되고 Flutter 앱의 AI 탭에서도 같은 일정을 봅니다.',
      tips: ['달력의 일정 칸에 마우스를 올리면 전체 제목이 보입니다'],
    },
    AINOTICE: {
      summary: 'AI가 메신저(Discord)로 보낸 알림의 기록입니다. 아침 브리핑, 전략 이탈 경고, 주간 복기, 스코어카드가 여기에 쌓입니다.',
      shows: ['발송 시각·채널·알림 종류', '알림 본문'],
      steps: ['별도 조작 없이 자동으로 쌓임', '"새로고침"으로 최신 알림 반영', '중요 알림은 Discord에서 바로 확인'],
      real: '아침 브리핑(ai_briefing.py)은 장 시작 전 스케줄러가 실행하고, 전략 이탈 감시(strategy_monitor.py)는 장중 주기적으로 돕니다.',
      tips: ['각 알림 종류가 어떤 모듈에서 오는지 태그를 확인하세요'],
    },
    JOURNAL: {
      summary: '달력형 매매일지입니다. 날짜별 실현손익을 한눈에 보고, 날짜를 누르면 매매 상세를 확인합니다.',
      shows: ['월간 수익·총 매매횟수', '날짜별 손익 달력', '매매별(상세) / 종목별(합산) 보기', '구글 시트 자동 업로드 링크'],
      steps: ['달력에서 날짜 클릭 → 하단에 상세 표', '"매매별 / 종목별" 토글로 보기 전환', '월 이동으로 과거 기록 확인'],
      real: '키움 일별 실현손익(opt10074)과 체결내역을 합쳐 계산하며, 장 마감 후 구글 시트 월별 탭에 자동 업로드됩니다.',
      tips: ['9월 5일과 9월 3일을 눌러 상세 내역을 비교해 보세요'],
    },
    CLI: {
      summary: '개발 작업 기록입니다. Claude CLI로 코드를 수정하면 훅이 프롬프트와 결과 요약을 자동으로 여기에 저장합니다.',
      shows: ['작업 시각과 CLI 종류', '프롬프트(요청 내용)', '실행 요약과 응답'],
      steps: ['별도 조작 없음 — cli_hook_prompt.py / cli_hook_stop.py 훅이 자동 기록', '항목을 클릭해 상세 펼치기', '불필요한 기록은 × 로 삭제'],
      real: 'Claude Code의 UserPromptSubmit / Stop 훅이 엔진 REST(:5000)로 내용을 보내 cli_tasks.db에 저장합니다.',
      tips: ['항목을 눌러 펼쳐 보세요'],
    },
    SETTINGS: {
      summary: '증권사·거래소·메신저 연동 정보를 입력하는 곳입니다. 모든 키는 암호화되어 로컬에만 저장됩니다.',
      shows: ['증권 서버 연결: 키움 / 한국투자증권', '키움 자동로그인(ID·비밀번호·인증비밀번호)', '바이낸스 현물/선물 API, 메인넷/테스트넷', 'Discord 봇 토큰과 채널 ID'],
      steps: ['탭에서 연동할 서비스 선택', '값 입력 후 "저장"', '.env 파일에 직접 적어도 동일하게 동작'],
      real: '입력값은 secret.key(Fernet)로 암호화되어 backend/settings/account_config.json에 저장되며 git에 올라가지 않습니다.',
      tips: ['데모에서는 모든 입력이 마스킹된 읽기 전용입니다'],
    },
  };

  /* ---------- 렌더 헬퍼 ---------- */
  const h = (html) => { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstElementChild; };

  function sparkline(values, w = 320, ht = 80, color = 'var(--primary)') {
    const min = Math.min(...values), max = Math.max(...values);
    const rng = max - min || 1;
    const pts = values.map((v, i) => [i * (w / (values.length - 1)), ht - ((v - min) / rng) * (ht - 10) - 5]);
    const d = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
    const area = d + ` L${w},${ht} L0,${ht} Z`;
    return `<svg viewBox="0 0 ${w} ${ht}" width="100%" height="${ht}" preserveAspectRatio="none">
      <defs><linearGradient id="g${w}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".35"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
      <path d="${area}" fill="url(#g${w})"/><path d="${d}" fill="none" stroke="${color}" stroke-width="2"/></svg>`;
  }

  function priceLadder(r, cur) {
    const entry = r.entry.split('~').map((s) => Number(s.replace(/[^0-9]/g, '')));
    const lo = Math.min(r.stop, entry[0], cur) * 0.985, hi = Math.max(r.target, entry[1], cur) * 1.015;
    const y = (p) => 20 + (1 - (p - lo) / (hi - lo)) * 160;
    const line = (p, label, color) => `<line x1="90" x2="330" y1="${y(p)}" y2="${y(p)}" stroke="${color}" stroke-dasharray="4 3"/><text x="86" y="${y(p) + 4}" fill="${color}" font-size="11" text-anchor="end">${label}</text><text x="336" y="${y(p) + 4}" fill="${color}" font-size="11">${fmt(p)}</text>`;
    return `<svg viewBox="0 0 400 200" width="100%" height="200">
      <rect x="90" y="${y(entry[1])}" width="240" height="${y(entry[0]) - y(entry[1])}" fill="rgba(0,212,255,.12)"/>
      ${line(r.target, '목표가', '#00ff88')}
      ${line(entry[1], '진입 상단', '#00d4ff')}${line(entry[0], '진입 하단', '#00d4ff')}
      ${line(r.stop, '손절가', '#ff4d4d')}
      <line x1="90" x2="330" y1="${y(cur)}" y2="${y(cur)}" stroke="#ffcc00" stroke-width="2"/><text x="336" y="${y(cur) + 4}" fill="#ffcc00" font-size="11">현재 ${fmt(cur)}</text>
    </svg>`;
  }

  /* ---------- 화면별 렌더러 ---------- */
  const R = {};

  R.MAIN = (c) => {
    const a = DEMO.account;
    c.innerHTML = `
      <div class="stack">
        <div class="intro" id="intro">
          <h3>👋 JbrainTrader 데모에 오신 것을 환영합니다</h3>
          <p>이 사이트는 <b>실제 대시보드와 같은 메뉴 구조</b>를 <b>Mock 데이터</b>로 재현한 기능 소개용 페이지입니다. 증권사 연결, 주문, AI 호출은 일어나지 않습니다.</p>
          <p>왼쪽 메뉴를 하나씩 눌러 보세요. 각 화면 오른쪽의 <b>파란 안내 상자</b>가 그 메뉴가 무엇을 하고 어떻게 쓰는지 설명합니다.</p>
        </div>
        <div class="account-cards">
          <div class="glass account-card"><div class="label">👤 사용자명</div><div class="value">${a.name} <span class="tag yellow">${a.mode}</span></div><div class="small muted" style="margin-top:6px">브로커: 키움증권 (KIWOOM)</div></div>
          <div class="glass account-card"><div class="label">💳 계좌번호 <span class="muted">총 ${a.acc_list.length}개</span></div>
            <select id="accSel">${a.acc_list.map((x) => `<option>${x}</option>`).join('')}</select>
            <div class="market-toggle"><span class="active" data-m="DOMESTIC">국내</span><span data-m="OVERSEAS">해외</span></div></div>
          <div class="glass account-card"><div class="label">💰 예수금</div><div class="value green">₩ ${fmt(a.balance)}</div><div class="small muted" style="margin-top:6px">오늘 실현손익 <span class="${cls(a.today_pnl)}">${sign(a.today_pnl)}원</span></div></div>
        </div>
        <div class="grid c2">
          <div class="card"><h3>시스템 상태</h3>
            <div class="sys-grid">
              <div class="sys-item"><div class="name">키움 게이트웨이 (32bit)</div><div class="st pos">● CONNECTED</div></div>
              <div class="sys-item"><div class="name">전략 엔진 (64bit)</div><div class="st pos">● RUNNING</div></div>
              <div class="sys-item"><div class="name">MySQL</div><div class="st pos">● OK</div></div>
              <div class="sys-item"><div class="name">Discord 봇</div><div class="st pos">● ONLINE</div></div>
            </div>
            <div class="small muted" style="margin-top:10px">32bit 게이트웨이와 64bit 엔진은 ZeroMQ(5555/5556)로 통신합니다. 키움 OpenAPI가 32bit 전용이라 프로세스를 나눴습니다.</div>
          </div>
          <div class="card"><h3>이번 달 누적 실현손익</h3>${sparkline([0, 34.5, 16.3, 108.4, 170.2, 312.5, 269.9, 297.8, 386.2, 398.5, 486.2])}
            <div class="row between small" style="margin-top:6px"><span class="muted">2026-09-01 ~ 09-12</span><span class="pos" style="font-weight:700">+${fmt(DEMO.journal.monthly_pnl)}원</span></div></div>
        </div>
        <div class="card"><h3>실행 흐름 한눈에 보기</h3>
          <div class="grid c4">
            ${[['① 데이터', '수집기 / 데이터 탭에서 시세를 모은다'], ['② 전략', '전략 탭에서 텍스트 파일로 규칙을 쓴다'], ['③ 검증', '백테스트 → 시뮬레이션 → 모의매매로 확인'], ['④ 운용', '관심종목에 전략을 붙여 시작, AI가 감시·복기']].map(([t, d]) => `<div class="metric"><div class="label">${t}</div><div style="font-size:.85rem;margin-top:4px">${d}</div></div>`).join('')}
          </div></div>
      </div>`;
    $('#accSel', c).onchange = (e) => toast(`계좌 전환: ${e.target.value} (데모)`, true);
    c.querySelectorAll('.market-toggle span').forEach((s) => (s.onclick = () => { c.querySelectorAll('.market-toggle span').forEach((x) => x.classList.remove('active')); s.classList.add('active'); toast(`${s.textContent} 시장으로 전환 (데모)`, true); }));
  };

  let logTimer = null;
  R.LOG = (c) => {
    c.innerHTML = `<div class="row between" style="margin-bottom:10px"><div class="row"><span class="status-dot">● 실시간</span><span class="muted small">WebSocket :8765 (데모에서는 타이머로 재현)</span></div><button class="small" id="clearLog">지우기</button></div><div class="log-box" id="logBox"></div>`;
    const box = $('#logBox', c);
    const add = (line) => {
      const kind = /\[ORDER\]/.test(line) ? 'order' : /\[SIGNAL\]|\[DUAL\]/.test(line) ? 'signal' : /경고|WARN/.test(line) ? 'warn' : /\[AI\]|\[GSHEET\]/.test(line) ? 'ai' : '';
      box.appendChild(h(`<div class="log-line ${kind}"><span class="t">${now()}</span>${esc(line)}</div>`));
      box.scrollTop = box.scrollHeight;
    };
    DEMO.logs.slice(0, 12).forEach(add);
    let i = 12;
    const tickers = DEMO.watchlist.filter((w) => !w.paused);
    clearInterval(logTimer);
    logTimer = setInterval(() => {
      if (Math.random() < 0.55) {
        const t = tickers[Math.floor(Math.random() * tickers.length)];
        const chg = (Math.random() - 0.5) * 1.2;
        add(`[TICK] ${t.ticker} ${fmt(Math.round(t.price * (1 + chg / 100)))} (${pct(chg)}) vol ${fmt(Math.floor(Math.random() * 4000))}`);
      } else { add(DEMO.logs[i % DEMO.logs.length]); i++; }
    }, 2200);
    $('#clearLog', c).onclick = () => (box.innerHTML = '');
  };

  R.HOLDINGS = (c) => {
    const a = DEMO.account, H = DEMO.holdings;
    const tb = H.reduce((s, x) => s + x.avg * x.qty, 0), te = H.reduce((s, x) => s + x.cur * x.qty, 0);
    const pl = te - tb, rate = (pl / tb) * 100;
    c.innerHTML = `
      <div class="grid c4" style="margin-bottom:14px">
        <div class="metric"><div class="label">계좌번호</div><div class="value">${a.acc_no}</div></div>
        <div class="metric"><div class="label">총 매입금액</div><div class="value">${fmt(tb)}원</div></div>
        <div class="metric"><div class="label">총 평가손익</div><div class="value ${cls(pl)}">${sign(pl)}원</div></div>
        <div class="metric"><div class="label">총 수익률</div><div class="value ${cls(rate)}">${pct(rate)}</div></div>
      </div>
      <div class="row between" style="margin-bottom:10px">
        <div class="row"><select style="width:180px" id="prof">${DEMO.aiTrades.profiles.map((p) => `<option>${p.name}</option>`).join('')}</select><button class="primary" id="analyzeAll" title="보유 종목 ${H.length}개를 선택한 프로파일로 순차 분석합니다">🤖 전체 분석</button></div>
        <div class="row"><button class="small" id="refresh" title="증권사에서 보유 종목과 현재가를 다시 불러옵니다">🔄 새로고침</button><button class="small" id="sheet" title="구글 시트의 '보유종목' 탭에 현재 보유 종목을 업로드합니다">📤 시트 업로드</button><a class="small" href="#" id="openSheet">시트 열기 ↗</a></div>
      </div>
      <div class="card scroll-x"><table><thead><tr><th>종목명</th><th>코드</th><th class="num">수량</th><th class="num">매입단가</th><th class="num">현재가</th><th class="num">평가손익</th><th class="num">수익률</th><th></th></tr></thead><tbody>
        ${H.map((x) => { const p = (x.cur - x.avg) * x.qty, r = ((x.cur - x.avg) / x.avg) * 100; return `<tr><td><b>${x.name}</b></td><td class="mono muted">${x.ticker}</td><td class="num">${fmt(x.qty)}</td><td class="num">${fmt(x.avg)}</td><td class="num">${fmt(x.cur)}</td><td class="num ${cls(p)}">${sign(p)}</td><td class="num ${cls(r)}">${pct(r)}</td><td><button class="small" data-an="${x.name}">🤖 분석</button></td></tr>`; }).join('')}
      </tbody></table></div>`;
    $('#analyzeAll', c).onclick = () => { toast(`"${$('#prof', c).value}" 프로파일로 ${H.length}개 종목 순차 분석 시작 (데모)`, true); setTimeout(() => toast('삼성전자 분석 완료 → AI 매매 탭에서 확인 (데모)', true), 1500); };
    $('#refresh', c).onclick = () => toast('증권사 보유 종목 재조회 완료 (데모)', true);
    $('#sheet', c).onclick = () => demoOnly('구글 시트 업로드');
    $('#openSheet', c).onclick = (e) => { e.preventDefault(); demoOnly('구글 시트 열기'); };
    c.querySelectorAll('[data-an]').forEach((b) => (b.onclick = () => { toast(`${b.dataset.an} AI 분석 요청 (데모) → AI 매매 탭으로 이동`, true); setTimeout(() => (location.hash = '#/AITRADES'), 900); }));
  };

  const wl = JSON.parse(JSON.stringify(DEMO.watchlist));
  R.MONITORING = (c) => {
    const strategies = [...DEMO.strategies.single, ...DEMO.strategies.dual].map((s) => s.name);
    const render = () => {
      c.innerHTML = `
        <div class="card" style="margin-bottom:14px"><div class="row">
          <input id="q" placeholder="예: 삼성전자 또는 005930" style="flex:1;min-width:200px"/>
          <select id="st" style="width:220px">${strategies.map((s) => `<option>${s}</option>`).join('')}</select>
          <button class="primary" id="add">➕ 추가</button></div>
          <div class="small muted" style="margin-top:8px">종목을 추가하면 지정한 전략 파일이 붙습니다. "시작"을 눌러야 실시간 평가가 시작됩니다.</div></div>
        <div class="card scroll-x"><table><thead><tr><th>종목명</th><th>종목코드</th><th>시장/현재가</th><th>전략</th><th title="클릭하여 시작/중지">상태 ⓘ</th><th class="num">보유주식</th><th class="num">실현이익</th><th>시작/종료</th><th>분석</th><th>삭제</th></tr></thead><tbody>
          ${wl.map((t, i) => `<tr>
            <td><b>${t.name}</b> ${t.real ? '<span class="tag green">실제 계좌</span>' : ''}</td><td class="mono muted">${t.ticker}</td>
            <td><span class="tag">${t.market}</span> ${t.market === 'NASDAQ' ? '$' + fmt(t.price, 2) : fmt(t.price)}</td>
            <td><select class="small" data-st="${i}" style="width:200px">${strategies.map((s) => `<option ${s === t.strategy ? 'selected' : ''}>${s}</option>`).join('')}</select></td>
            <td>${t.paused ? '<span class="tag">⏸ 중지</span>' : '<span class="tag green">● 실행 중</span>'}</td>
            <td class="num">${fmt(t.qty)}</td><td class="num ${cls(t.realized)}">${sign(t.realized)}</td>
            <td><button class="small toggle-btn ${t.paused ? 'off' : 'on'}" data-tg="${i}">${t.paused ? '▶️ 시작' : '⏹️ 중지'}</button></td>
            <td><button class="small" data-an="${i}" title="지표 분석">🔍</button></td><td><button class="small danger" data-del="${i}" title="삭제">🗑️</button></td></tr>`).join('')}
        </tbody></table></div>`;
      $('#add', c).onclick = () => { const q = $('#q', c).value.trim(); if (!q) return toast('종목명 또는 코드를 입력하세요'); wl.push({ ticker: /^\d+$/.test(q) ? q : 'NEW', name: /^\d+$/.test(q) ? '(검색 종목)' : q, market: 'KOSPI', price: 10000, strategy: $('#st', c).value, paused: true, qty: 0, realized: 0, real: false }); toast(`"${q}" 추가 — 실제로는 증권사 종목 검색 후 확인 모달이 뜹니다 (데모)`, true); render(); };
      c.querySelectorAll('[data-tg]').forEach((b) => (b.onclick = () => { const t = wl[b.dataset.tg]; t.paused = !t.paused; toast(t.paused ? `${t.name} 전략 평가 중지 (포지션 유지)` : `${t.name} 실시간 시세 등록 → ${t.strategy} 평가 시작`, true); render(); }));
      c.querySelectorAll('[data-st]').forEach((s) => (s.onchange = () => { wl[s.dataset.st].strategy = s.value; toast(`전략을 ${s.value}로 변경 — 실제로는 DB(tickers.buy_rule)에 저장 (데모)`, true); }));
      c.querySelectorAll('[data-an]').forEach((b) => (b.onclick = () => toast(`${wl[b.dataset.an].name} 지표 분석 탭 열기 — 캔들·EMA·RSI·BB 차트가 새 탭으로 뜹니다 (데모)`, true)));
      c.querySelectorAll('[data-del]').forEach((b) => (b.onclick = () => { const t = wl.splice(b.dataset.del, 1)[0]; toast(`${t.name} 삭제 (데모)`, true); render(); }));
    };
    render();
  };

  R.DATA = (c) => {
    let active = null;
    const tree = (items) => `<ul>${items.map((it) => it.children ? `<li><div class="node group">📁 ${it.name}</div>${tree(it.children)}</li>` : `<li><div class="node leaf" data-name="${esc(it.name)}" data-desc="${esc(it.desc || '')}">${it.name}</div></li>`).join('')}</ul>`;
    c.innerHTML = `<div class="data-layout"><div class="card"><div class="card-title">데이터 작업 메뉴</div><div class="tree">${tree(DEMO.dataMenu)}</div></div><div class="card" id="dataRight"><div class="muted">왼쪽 트리에서 작업을 선택하세요.</div></div></div>`;
    const right = $('#dataRight', c);
    c.querySelectorAll('.node.leaf').forEach((n) => (n.onclick = () => {
      c.querySelectorAll('.node.leaf').forEach((x) => x.classList.remove('active')); n.classList.add('active');
      const name = n.dataset.name, desc = n.dataset.desc, parent = n.closest('ul').closest('li')?.querySelector('.node.group')?.textContent.replace('📁 ', '') || '';
      const isBT = parent === '실행';
      let body = `<h3>${parent ? parent + ' › ' : ''}${name}</h3><p class="small" style="margin:0 0 14px">${desc}</p>`;
      if (parent === '실행' || parent === '가져오기' || parent === '가상' || name.includes('기존 데이터') || name.includes('랜덤')) {
        body += `<div class="grid c3" style="margin-bottom:12px"><div class="field"><label>종목</label><input value="005930 삼성전자" readonly/></div><div class="field"><label>기간</label><input value="2026-01-02 ~ 2026-06-30" readonly/></div><div class="field"><label>전략</label><input value="${parent === '실행' && name.includes('듀얼') ? 'DUAL_200_1X_INVERSE' : 'GOLDEN_CROSS'}" readonly/></div></div><button class="primary" id="runIt">▶ 실행</button>`;
      }
      if (isBT && parent === '실행') {
        const b = DEMO.backtestSample;
        body += `<div style="margin-top:16px" id="btResult"><div class="card-title">최근 실행 결과 (샘플)</div><div class="grid c4" style="margin-bottom:10px">${[['거래 수', b.trades], ['승률', b.win_rate], ['누적 수익', b.pnl], ['최대 낙폭', b.mdd]].map(([l, v]) => `<div class="metric"><div class="label">${l}</div><div class="value">${v}</div></div>`).join('')}</div>${sparkline(b.curve, 400, 100)}<div class="small muted">${b.strategy} · ${b.ticker} · ${b.period} — 수익 곡선(%)</div></div>`;
      }
      if (parent === '통계' || parent === '조회') {
        body += `<div class="scroll-x" style="margin-top:8px"><table><thead><tr><th>날짜</th><th>종목</th><th>전략</th><th class="num">매수</th><th class="num">매도</th><th class="num">손익</th></tr></thead><tbody>${[['09-05', '삼성전자', 'GOLDEN_CROSS', 73850, 74600, 6240], ['09-05', 'SK하이닉스', 'VOL_BREAKOUT_PRO', 178200, 182300, 135045], ['09-04', 'KODEX 인버스', 'DUAL_200_1X_INVERSE', 4085, 4094, 1015], ['09-03', '카카오', 'MEAN_REVERSION_BB', 48900, 48150, -2340]].map((r) => `<tr><td>${r[0]}</td><td>${r[1]}</td><td class="mono small">${r[2]}</td><td class="num">${fmt(r[3])}</td><td class="num">${fmt(r[4])}</td><td class="num ${cls(r[5])}">${sign(r[5])}</td></tr>`).join('')}</tbody></table></div>`;
      }
      right.innerHTML = body;
      const run = $('#runIt', right); if (run) run.onclick = () => { toast(`${name} 실행 요청 (데모) — 실제로는 엔진이 MySQL 데이터를 읽어 처리합니다`, true); };
    }));
  };

  R.COLLECTOR = (c) => {
    const picked = ['005930.KS 삼성전자', '069500.KS KODEX 200', 'AAPL Apple'];
    c.innerHTML = `<div class="grid c2" style="grid-template-columns: 320px 1fr">
      <div class="card"><h3>API 데이터 수집</h3>
        <div class="field"><label>데이터 소스</label><select><option>Yahoo Finance</option><option>KRX (준비중)</option></select></div>
        <div class="field"><label>주기 선택</label><div class="row"><label><input type="radio" name="p" style="width:auto"/> 1분</label><label><input type="radio" name="p" style="width:auto"/> 5분</label><label><input type="radio" name="p" checked style="width:auto"/> 일봉</label></div></div>
        <div class="field"><label>기간 설정</label><div class="row"><input type="date" value="2025-09-05"/><span>~</span><input type="date" value="2026-09-05"/></div></div>
        <div class="field"><label>종목 선택 (티커 및 종목명 검색 가능)</label><div class="row"><input id="cq" placeholder="예: AAPL, 삼성전자, 005930.KS" style="flex:1"/><button id="cs">검색</button></div></div>
        <div class="chip-list" id="chips"></div>
        <button class="primary" id="start" style="width:100%;margin-top:14px">수집 시작</button></div>
      <div class="stack"><div class="card"><div class="card-title">수집 진행률</div><div class="progress"><div id="bar"></div></div><div class="small muted" id="ptxt" style="margin-top:6px">대상 종목: <span id="pcount"></span>개 — 대기 중</div></div>
        <div class="card"><div class="card-title">수집 로그</div><div class="log-box" id="clog" style="height:300px"></div></div></div></div>`;
    const chips = $('#chips', c), log = $('#clog', c);
    const drawChips = () => { chips.innerHTML = picked.map((p, i) => `<span class="chip">${p}<span class="x" data-i="${i}">×</span></span>`).join(''); $('#pcount', c).textContent = picked.length; chips.querySelectorAll('.x').forEach((x) => (x.onclick = () => { picked.splice(x.dataset.i, 1); drawChips(); })); };
    drawChips();
    $('#cs', c).onclick = () => { const q = $('#cq', c).value.trim(); if (!q) return; picked.push(q); $('#cq', c).value = ''; drawChips(); toast(`"${q}" 추가 — 실제로는 Yahoo 검색 API로 티커를 확인합니다 (데모)`, true); };
    $('#start', c).onclick = () => {
      if (!picked.length) return toast('종목을 먼저 선택하세요');
      log.innerHTML = ''; let i = 0; const bar = $('#bar', c);
      $('#start', c).disabled = true;
      const tick = () => { if (i >= DEMO.collectorLog.length) { $('#ptxt', c).textContent = `완료 — ${picked.length}종목 저장됨 (데모)`; $('#start', c).disabled = false; toast('수집 완료 (데모 데이터)', true); return; }
        log.appendChild(h(`<div class="log-line"><span class="t">${now()}</span>${esc(DEMO.collectorLog[i])}</div>`)); log.scrollTop = log.scrollHeight; i++; bar.style.width = Math.round((i / DEMO.collectorLog.length) * 100) + '%'; $('#ptxt', c).textContent = `대상 종목: ${picked.length}개 — 진행 ${Math.round((i / DEMO.collectorLog.length) * 100)}%`; setTimeout(tick, 550); };
      tick();
    };
  };

  R.STRATEGY = (c) => {
    let sel = 'GOLDEN_CROSS', editing = false;
    const S = DEMO.strategies;
    const content = (n) => S.content[n] || S.generic(n, S.dual.some((d) => d.name === n) ? 'dual' : 'single');
    const render = () => {
      c.innerHTML = `<div class="two-col">
        <div class="stack"><div class="row between"><div class="card-title" style="margin:0">📊 활성 전략 프로파일</div><button class="small" id="newS">+ 새 전략 생성</button></div>
          <div class="card-title">단일 종목 (strategy/*.txt)</div><div class="list">${S.single.map((s) => `<div class="list-item ${s.name === sel ? 'active' : ''}" data-s="${s.name}"><div class="name">${s.name}</div><div class="desc">${s.desc}</div></div>`).join('')}</div>
          <div class="card-title">듀얼 ETF (strategy/dual/*.txt)</div><div class="list">${S.dual.map((s) => `<div class="list-item ${s.name === sel ? 'active' : ''}" data-s="${s.name}"><div class="name">${s.name}</div><div class="desc">${s.desc}</div></div>`).join('')}</div></div>
        <div class="card"><div class="row between" style="margin-bottom:10px"><h3 style="margin:0">${sel} <span class="tag ${S.dual.some((d) => d.name === sel) ? 'purple' : 'blue'}">${S.dual.some((d) => d.name === sel) ? 'dual' : 'single'}</span></h3><div class="row">${editing ? '<button class="small" id="cancel">편집 취소</button><button class="small primary" id="save">전략 저장하기</button>' : '<button class="small" id="edit">✏️ 편집</button><button class="small danger" id="del">삭제</button>'}</div></div>
          <div class="field"><label>전략 명칭</label><input value="${sel}" ${editing ? '' : 'readonly'}/></div>
          <div class="field"><label>전략 구성 (DSL)</label><textarea style="min-height:360px" ${editing ? '' : 'readonly'}>${esc(content(sel))}</textarea></div>
          <div class="small muted">조건식 변수: <code>price ema5 ema20 rsi bb_upper bb_lower bb_mid</code> · 포지션: <code>first_buy_price avg_price</code> · 크기: <code>size = 0.5 / 1.0 / all</code></div></div></div>`;
      c.querySelectorAll('[data-s]').forEach((el) => (el.onclick = () => { sel = el.dataset.s; editing = false; render(); }));
      const on = (id, fn) => { const b = $(id, c); if (b) b.onclick = fn; };
      on('#edit', () => { editing = true; render(); });
      on('#cancel', () => { editing = false; render(); });
      on('#save', () => { editing = false; toast(`strategy/${sel}.txt 저장 (데모 — 파일은 변경되지 않음)`, true); render(); });
      on('#del', () => demoOnly('전략 삭제'));
      on('#newS', () => { sel = 'NEW_STRATEGY'; editing = true; S.content.NEW_STRATEGY = S.generic('NEW_STRATEGY', 'single'); render(); toast('새 전략 템플릿이 열렸습니다. 이름과 조건을 수정하고 저장하세요 (데모)', true); });
    };
    render();
  };

  R.AIPICKS = (c) => {
    let sel = DEMO.aiPicks.profiles[0].name, running = false;
    const render = () => {
      const p = DEMO.aiPicks.profiles.find((x) => x.name === sel), r = DEMO.aiPicks.results[sel];
      c.innerHTML = `<div class="two-col">
        <div class="stack"><div class="row between"><div class="card-title" style="margin:0">✨ 종목 선별 프로파일</div><button class="small" id="np">+ 새 프로파일 생성</button></div>
          <div class="list">${DEMO.aiPicks.profiles.map((x) => `<div class="list-item ${x.name === sel ? 'active' : ''}" data-p="${x.name}"><div class="name">${x.name}</div><div class="desc">모델: ${x.model} · ${DEMO.aiPicks.results[x.name] ? '결과 ' + DEMO.aiPicks.results[x.name].picks.length + '종목' : '미실행'}</div></div>`).join('')}</div></div>
        <div class="stack"><div class="card"><div class="row between"><h3 style="margin:0">${p.name}</h3><div class="row"><button class="small" id="rf" title="모바일 등 다른 기기에서 변경된 내용을 다시 불러옵니다">🔄 새로고침</button><button class="small danger">삭제</button></div></div>
          <div class="grid c2" style="margin-top:10px"><div class="field"><label>프로파일 명칭</label><input value="${p.name}" readonly/></div><div class="field"><label>실행 AI 모델</label><select><option ${p.model === 'opus' ? 'selected' : ''}>opus</option><option ${p.model === 'sonnet' ? 'selected' : ''}>sonnet</option><option ${p.model === 'haiku' ? 'selected' : ''}>haiku</option></select></div></div>
          <div class="field"><label>종목 선별 프롬프트</label><textarea readonly style="min-height:90px">${esc(p.prompt)}</textarea></div>
          <div class="row"><button class="primary" id="run" ${running ? 'disabled' : ''} title="프롬프트를 Claude CLI로 실행해 종목을 선별합니다">${running ? '⏳ Claude CLI 실행 중...' : '▶ 실행'}</button><button class="small" id="cmp" title="선별된 종목들의 재무제표·투자지표를 비교 분석합니다">📊 재무 비교 분석</button></div></div>
          <div class="card"><div class="row between"><h3 style="margin:0">📋 선별 결과</h3>${r ? `<span class="muted small">실행: ${r.ran_at}</span>` : ''}</div>
          ${r ? `<div class="scroll-x"><table><thead><tr><th>#</th><th>종목</th><th>코드</th><th>점수</th><th>선정 근거</th><th></th></tr></thead><tbody>${r.picks.map((k, i) => `<tr><td class="muted">${i + 1}</td><td><b>${k.name}</b></td><td class="mono muted">${k.ticker}</td><td><span class="score">${k.score}</span></td><td style="white-space:normal;min-width:260px">${k.reason}</td><td><button class="small" data-add="${k.name}">관심종목 추가</button></td></tr>`).join('')}</tbody></table></div>` : '<div class="muted" style="padding:20px 0">아직 실행하지 않은 프로파일입니다. "▶ 실행"을 눌러 보세요.</div>'}
          <div class="disclaimer">※ AI가 생성한 참고용 정보입니다. 투자 판단과 책임은 본인에게 있습니다.</div></div></div></div>`;
      c.querySelectorAll('[data-p]').forEach((el) => (el.onclick = () => { sel = el.dataset.p; render(); }));
      $('#run', c).onclick = () => { running = true; render(); toast('claude -p 로 프롬프트 실행 중... (데모: 2초 후 가짜 결과 생성)', true); setTimeout(() => { if (!DEMO.aiPicks.results[sel]) DEMO.aiPicks.results[sel] = { ran_at: new Date().toISOString().slice(0, 16).replace('T', ' '), picks: [{ ticker: '017670', name: 'SK텔레콤', score: 79, reason: '배당수익률 6.1%, 5년 연속 배당 증가' }, { ticker: '033780', name: 'KT&G', score: 77, reason: '배당수익률 5.4%, 자사주 소각 병행' }, { ticker: '086790', name: '하나금융지주', score: 74, reason: '배당수익률 5.8%, 분기 배당 전환' }] }; else DEMO.aiPicks.results[sel].ran_at = new Date().toISOString().slice(0, 16).replace('T', ' '); running = false; render(); toast('선별 완료 — 결과가 SQLite(ai_picks.db)에 저장됩니다 (데모)', true); }, 2000); };
      $('#cmp', c).onclick = () => demoOnly('재무 비교 분석');
      $('#rf', c).onclick = () => toast('새로고침 완료 (데모)', true);
      $('#np', c).onclick = () => demoOnly('새 프로파일 생성');
      c.querySelectorAll('[data-add]').forEach((b) => (b.onclick = () => toast(`${b.dataset.add} 관심종목 추가 → 전략 선택 모달이 뜹니다 (데모)`, true)));
    };
    render();
  };

  R.AITRADES = (c) => {
    let sel = DEMO.aiTrades.profiles[0].name, showChart = false;
    const render = () => {
      const p = DEMO.aiTrades.profiles.find((x) => x.name === sel), r = DEMO.aiTrades.results[sel];
      const hd = DEMO.holdings.find((x) => x.ticker === p.ticker);
      const pl = hd ? (hd.cur - hd.avg) * hd.qty : 0, rate = hd ? ((hd.cur - hd.avg) / hd.avg) * 100 : 0;
      c.innerHTML = `<div class="two-col">
        <div class="stack"><div class="row between"><div class="card-title" style="margin:0">🤖 매매 전략 프로파일</div><button class="small" id="np">+ 새 프로파일 생성</button></div>
          <div class="list">${DEMO.aiTrades.profiles.map((x) => `<div class="list-item ${x.name === sel ? 'active' : ''}" data-p="${x.name}"><div class="name">${x.name}</div><div class="desc">${DEMO.holdings.find((k) => k.ticker === x.ticker)?.name} (${x.ticker}) · ${x.model}</div></div>`).join('')}</div></div>
        <div class="stack"><div class="card"><div class="row between"><h3 style="margin:0">${p.name}</h3><button class="small" title="모바일 등 다른 기기에서 변경된 내용을 다시 불러옵니다">🔄 새로고침</button></div>
          <div class="grid c2" style="margin-top:10px"><div class="field"><label>대상 종목</label><select><option>— AI 종목 프로파일 선택 —</option><option selected>${hd.name} (${p.ticker})</option></select></div><div class="field"><label>실행 AI 모델</label><input value="${p.model}" readonly/></div></div>
          <div class="grid c3" style="margin-bottom:12px">${[['보유수량', fmt(hd.qty) + '주'], ['매입단가', fmt(hd.avg)], ['현재가', fmt(hd.cur)], ['매입금액', fmt(hd.avg * hd.qty)], ['평가손익', `<span class="${cls(pl)}">${sign(pl)}</span>`], ['수익률', `<span class="${cls(rate)}">${pct(rate)}</span>`]].map(([l, v]) => `<div class="metric"><div class="label">${l}</div><div class="value" style="font-size:.95rem">${v}</div></div>`).join('')}</div>
          <div class="field"><label>매매 전략 프롬프트</label><textarea readonly style="min-height:70px">${esc(p.prompt)}</textarea></div>
          <div class="row"><button class="primary" id="run" title="선택한 종목의 매매 전략을 AI에게 요청합니다">▶ 실행</button><button class="small" id="chart" title="가격대별 매매 전략을 그래프로 표시합니다">📈 가격대 그래프</button><button class="small" id="sheet" title="구글 시트의 '${p.name}' 탭에 업로드합니다">📤 시트 업로드</button></div></div>
          ${r ? `<div class="card"><div class="row between"><h3 style="margin:0">전략 결과</h3><span class="muted small">실행: ${r.ran_at}</span></div>
            <div class="grid c3" style="margin:10px 0">${[['목표가', fmt(r.target), 'pos'], ['진입 가격대', r.entry, ''], ['손절가', fmt(r.stop), 'neg'], ['기대 수익', r.expected, 'pos'], ['투자 비중', r.weight, ''], ['보유 기간', r.period, '']].map(([l, v, k]) => `<div class="metric"><div class="label">${l}</div><div class="value ${k}">${v}</div></div>`).join('')}</div>
            ${showChart ? `<div class="card" style="margin-bottom:12px">${priceLadder(r, hd.cur)}</div>` : ''}
            <div class="grid c3"><div><div class="card-title">✅ 매수 조건</div><ul class="cond-list">${r.buy_cond.map((x) => `<li>${x}</li>`).join('')}</ul></div><div><div class="card-title">🎯 매도 조건</div><ul class="cond-list">${r.sell_cond.map((x) => `<li>${x}</li>`).join('')}</ul></div><div><div class="card-title">⚠️ 리스크 요인</div><ul class="cond-list">${r.risks.map((x) => `<li>${x}</li>`).join('')}</ul></div></div>
            <div class="card-title" style="margin-top:12px">근거</div><div style="font-size:.88rem">${r.reason}</div>
            <div class="disclaimer">※ AI가 생성한 참고용 정보입니다. 투자 판단과 책임은 본인에게 있습니다.</div></div>` : ''}</div></div>`;
      c.querySelectorAll('[data-p]').forEach((el) => (el.onclick = () => { sel = el.dataset.p; showChart = false; render(); }));
      $('#run', c).onclick = () => { toast('Claude CLI로 매매 전략 생성 중... (데모)', true); setTimeout(() => { DEMO.aiTrades.results[sel].ran_at = new Date().toISOString().slice(0, 16).replace('T', ' '); render(); toast('전략 생성 완료 — 목표가/손절가가 전략 이탈 감시 기준으로 등록됩니다 (데모)', true); }, 1500); };
      $('#chart', c).onclick = () => { showChart = !showChart; render(); };
      $('#sheet', c).onclick = () => demoOnly('구글 시트 업로드');
      $('#np', c).onclick = () => demoOnly('새 프로파일 생성');
    };
    render();
  };

  const DOW = ['일', '월', '화', '수', '목', '금', '토'];
  function calendarGrid(year, month, cellFn) {
    const first = new Date(year, month - 1, 1).getDay(), days = new Date(year, month, 0).getDate();
    let html = DOW.map((d) => `<div class="dow">${d}</div>`).join('');
    for (let i = 0; i < first; i++) html += '<div class="day empty"></div>';
    for (let d = 1; d <= days; d++) html += cellFn(d);
    return `<div class="cal">${html}</div>`;
  }

  R.AICALENDAR = (c) => {
    let sel = DEMO.calendar.profiles[0].name;
    const C = DEMO.calendar;
    const render = () => {
      const p = C.profiles.find((x) => x.name === sel);
      c.innerHTML = `<div class="two-col">
        <div class="stack"><div class="row between"><div class="card-title" style="margin:0">📅 캘린더 프로파일</div><button class="small" id="np">+ 새 프로파일</button></div>
          <div class="list">${C.profiles.map((x) => `<div class="list-item ${x.name === sel ? 'active' : ''}" data-p="${x.name}"><div class="name">${x.name}</div></div>`).join('')}</div>
          <div class="card"><div class="field"><label>프로파일 이름</label><input value="${p.name}" readonly/></div><div class="field"><label>지시문</label><textarea readonly style="min-height:80px">${esc(p.prompt)}</textarea></div><div class="row"><button class="primary" id="run">▶ 실행</button><button class="small">💾 저장</button><button class="small danger">🗑 삭제</button></div></div>
          <div class="card"><h3>🗓 주요 일정</h3>${C.events.map((e) => `<div class="kv"><span><span class="tag ${e.type === 'stock' ? 'green' : e.type === 'dividend' ? 'yellow' : e.type === 'market' ? 'purple' : 'blue'}">${e.type}</span> ${e.title}</span><span class="muted">${C.month}/${e.day}</span></div>`).join('')}</div></div>
        <div class="card"><div class="row between" style="margin-bottom:10px"><button class="small" id="prev" title="이전 달">‹</button><h3 style="margin:0">${C.year}년 ${C.month}월</h3><div class="row"><button class="small">오늘</button><button class="small" id="next" title="다음 달">›</button></div></div>
          ${calendarGrid(C.year, C.month, (d) => { const evs = C.events.filter((e) => e.day === d); return `<div class="day ${d === 5 ? 'active' : ''}"><div class="d">${d}</div>${evs.map((e) => `<div class="ev ${e.type}" title="${e.title}">${e.title}</div>`).join('')}</div>`; })}
          <div class="small muted" style="margin-top:8px">색상: <span class="tag blue">macro 경제지표</span> <span class="tag green">stock 종목 이벤트</span> <span class="tag yellow">dividend 배당</span> <span class="tag purple">market 시장</span></div></div></div>`;
      c.querySelectorAll('[data-p]').forEach((el) => (el.onclick = () => { sel = el.dataset.p; render(); }));
      $('#run', c).onclick = () => { toast('Claude CLI로 이번 달 일정 정리 중... (데모)', true); setTimeout(() => toast('일정 9건 생성 완료 → ai_calendar.db 저장 (데모)', true), 1500); };
      $('#np', c).onclick = () => demoOnly('새 프로파일');
      $('#prev', c).onclick = $('#next', c).onclick = () => toast('데모에는 2026년 9월 데이터만 있습니다');
      c.querySelectorAll('.day:not(.empty)').forEach((d) => (d.onclick = () => { c.querySelectorAll('.day').forEach((x) => x.classList.remove('active')); d.classList.add('active'); }));
    };
    render();
  };

  R.AINOTICE = (c) => {
    const color = { '아침 브리핑': 'blue', '전략 이탈 감시': 'red', '체결 알림': 'green', '주간 매매 복기': 'purple', '스코어카드': 'yellow' };
    const src = { '아침 브리핑': 'ai_briefing.py', '전략 이탈 감시': 'strategy_monitor.py', '체결 알림': 'backend/main.py', '주간 매매 복기': 'ai_review.py', '스코어카드': 'strategy_scorecard.py' };
    c.innerHTML = `<div class="row between" style="margin-bottom:12px"><h3 style="margin:0">🔔 메신저 발송 알림</h3><button class="small" id="rf" title="알림을 다시 불러옵니다">🔄 새로고침</button></div>
      <div class="stack">${DEMO.notices.map((n) => `<div class="notice"><div class="head"><span class="tag ${color[n.kind] || ''}">${n.kind}</span><span>${n.time}</span><span>→ ${n.channel}</span><span class="mono" style="margin-left:auto">${src[n.kind] || ''}</span></div><div class="body">${esc(n.body)}</div></div>`).join('')}</div>`;
    $('#rf', c).onclick = () => toast('알림 새로고침 완료 (데모)', true);
  };

  R.JOURNAL = (c) => {
    const J = DEMO.journal; let day = 5, mode = 'detail';
    const render = () => {
      const rows = J.detail[day] || [];
      const dayTotal = rows.reduce((s, r) => s + r.pnl, 0);
      const byName = Object.values(rows.reduce((m, r) => { (m[r.name] = m[r.name] || { name: r.name, qty: 0, fee: 0, pnl: 0, n: 0 }); m[r.name].qty += r.qty; m[r.name].fee += r.fee; m[r.name].pnl += r.pnl; m[r.name].n++; return m; }, {}));
      c.innerHTML = `<div class="grid c3" style="margin-bottom:14px"><div class="metric"><div class="label">월간 수익</div><div class="value ${cls(J.monthly_pnl)}">${sign(J.monthly_pnl)}원</div></div><div class="metric"><div class="label">총 매매횟수</div><div class="value">${J.trade_count}회</div></div><div class="metric"><div class="label">구글 시트</div><div class="value" style="font-size:.9rem"><a href="#" id="sheet" title="구글 시트 열기">시트 열기 ↗</a> <span class="muted small">2026-09 탭</span></div></div></div>
        <div class="card" style="margin-bottom:14px"><div class="row between" style="margin-bottom:10px"><button class="small">‹</button><h3 style="margin:0">${J.year}년 ${J.month}월</h3><button class="small">›</button></div>
          ${calendarGrid(J.year, J.month, (d) => { const x = J.days[d]; return `<div class="day ${d === day ? 'active' : ''}" data-d="${d}"><div class="d">${d}</div>${x ? `<div class="pnl ${cls(x.pnl)}">${sign(x.pnl)}</div><div class="n">${x.n}건</div>` : ''}</div>`; })}</div>
        <div class="card"><div class="row between" style="margin-bottom:10px"><div><b>${J.month}월 ${day}일</b> <span class="muted small">일일 손익:</span> <b class="${cls(dayTotal)}">${sign(dayTotal)}원</b> ${rows.length ? `<span class="muted small" title="키움 정산 기준 (opt10074)">(수익률: ${pct(dayTotal / 10_000_000 * 100)})</span>` : ''}</div>
          <div class="row"><button class="small ${mode === 'detail' ? 'primary' : ''}" id="m1">매매별 (상세)</button><button class="small ${mode === 'sum' ? 'primary' : ''}" id="m2">종목별 (합산)</button></div></div>
          ${!rows.length ? '<div class="muted" style="padding:16px 0">이날의 매매 내역이 없습니다.' + (J.days[day] ? ' (데모에는 5일·3일 상세만 있음)' : '') + '</div>' : mode === 'detail'
            ? `<div class="scroll-x"><table><thead><tr><th>종목명</th><th class="num">매수단가</th><th class="num">매도단가</th><th class="num">수량</th><th class="num">수수료+제세금</th><th class="num">실현손익</th><th class="num">수익률</th></tr></thead><tbody>${rows.map((r) => `<tr><td><b>${r.name}</b></td><td class="num">${fmt(r.buy)}</td><td class="num">${fmt(r.sell)}</td><td class="num">${fmt(r.qty)}</td><td class="num muted">${fmt(r.fee)}</td><td class="num ${cls(r.pnl)}">${sign(r.pnl)}</td><td class="num ${cls(r.pnl)}">${pct((r.sell - r.buy) / r.buy * 100)}</td></tr>`).join('')}</tbody></table></div>`
            : `<div class="scroll-x"><table><thead><tr><th>종목명</th><th class="num">매매 건수</th><th class="num">수량 합계</th><th class="num">수수료+제세금</th><th class="num">실현손익</th></tr></thead><tbody>${byName.map((r) => `<tr><td><b>${r.name}</b></td><td class="num">${r.n}</td><td class="num">${fmt(r.qty)}</td><td class="num muted">${fmt(r.fee)}</td><td class="num ${cls(r.pnl)}">${sign(r.pnl)}</td></tr>`).join('')}</tbody></table></div>`}</div>`;
      c.querySelectorAll('[data-d]').forEach((el) => (el.onclick = () => { day = Number(el.dataset.d); render(); }));
      $('#m1', c).onclick = () => { mode = 'detail'; render(); }; $('#m2', c).onclick = () => { mode = 'sum'; render(); };
      $('#sheet', c).onclick = (e) => { e.preventDefault(); demoOnly('구글 시트 열기'); };
    };
    render();
  };

  R.CLI = (c) => {
    c.innerHTML = `<div class="row between" style="margin-bottom:12px"><h3 style="margin:0">💻 CLI 작업 기록</h3><span class="muted small">cli_hook_prompt.py / cli_hook_stop.py 훅이 자동 저장</span></div>
      <div class="stack">${DEMO.cliTasks.map((t, i) => `<div class="task ${i === 0 ? 'open' : ''}"><div class="head"><div><span class="tag ${t.cli === 'claude_cli' ? 'blue' : 'purple'}">${t.cli}</span> <b>${esc(t.prompt)}</b></div><div class="row"><span class="muted small">${t.time}</span><button class="small danger" data-x="${i}" title="삭제">×</button></div></div>
        <div class="body"><div class="lbl">프롬프트</div><div>${esc(t.prompt)}</div><div class="lbl">실행 요약</div><div>${esc(t.summary)}</div><div class="lbl">응답</div><div class="small">${esc(t.response)}</div></div></div>`).join('')}</div>`;
    c.querySelectorAll('.task .head').forEach((hd) => (hd.onclick = (e) => { if (e.target.closest('button')) return; hd.parentElement.classList.toggle('open'); }));
    c.querySelectorAll('[data-x]').forEach((b) => (b.onclick = () => demoOnly('작업 기록 삭제')));
  };

  R.SETTINGS = (c) => {
    let tab = 'broker';
    const F = (label, val = '••••••••••••', ph) => `<div class="field"><label>${label}</label><input value="${val}" placeholder="${ph || ''}" readonly/></div>`;
    const render = () => {
      c.innerHTML = `<div class="settings-tabs">${[['broker', '🔌 증권 서버 연결'], ['kiwoom', '📝 키움 자동로그인'], ['binance', '🪙 바이낸스 API'], ['discord', '💬 Discord 알림']].map(([k, l]) => `<button class="${tab === k ? 'active' : ''}" data-t="${k}">${l}</button>`).join('')}</div>
        <div class="card">${{
          broker: `<h3>증권 서버 연결 (Broker)</h3><div class="row" style="margin-bottom:14px"><label class="row"><input type="radio" checked style="width:auto"/> 키움증권</label><label class="row"><input type="radio" style="width:auto"/> 한국투자증권</label></div><div class="card-title">한국투자증권 API 상세 설정 (선택)</div><div class="grid c3">${F('계좌번호 (8~10자리 숫자)', '', '예: 12345678')}${F('App Key', '', 'App Key를 입력하세요')}${F('App Secret', '', 'App Secret을 입력하세요')}</div><div class="small muted">모의/실전 키를 따로 저장하며 KIS_MOCK_* / KIS_REAL_* 환경변수와 동일합니다.</div>`,
          kiwoom: `<h3>키움증권 자동로그인 설정</h3><div class="grid c3">${F('사용자 ID', 'demo_user')}${F('비밀번호')}${F('인증비밀번호')}</div><div class="row"><label class="row"><input type="checkbox" checked style="width:auto"/> 모의투자 서버 사용 (KIWOOM_IS_MOCK=1)</label></div><div class="small muted" style="margin-top:8px">저장 시 secret.key(Fernet)로 암호화됩니다. 로그인 창 자동 입력은 auto_login 모듈이 관리자 권한으로 수행합니다.</div>`,
          binance: `<h3>바이낸스 API 설정</h3><div class="grid c2"><div><div class="card-title">🚀 선물 (Futures)</div>${F('선물 API Key')}${F('선물 API Secret')}</div><div><div class="card-title">💰 현물 (Spot)</div>${F('현물 API Key')}${F('현물 API Secret')}</div></div><div class="grid c2"><div class="field"><label>활성 시장 유형</label><select><option>선물 (Futures)</option><option>현물 (Spot)</option></select></div><div class="field"><label>네트워크 모드</label><select><option>🧪 테스트넷</option><option>🌐 메인넷</option></select></div></div>`,
          discord: `<h3>Discord 알림 및 명령 설정</h3><div class="grid c2">${F('Bot Token')}${F('서버(Guild) ID', '0000000000000000000')}${F('Log 채널 ID', '0000000000000000000')}${F('Command 채널 ID', '0000000000000000000')}</div><div class="small muted">Log 채널에는 엔진 로그와 AI 알림이 전송되고, Command 채널에서는 /portfolio 명령을 사용할 수 있습니다.</div>`,
        }[tab]}<div class="row" style="margin-top:14px"><button class="primary" id="save">💾 저장</button><span class="muted small">데모에서는 모든 값이 마스킹된 읽기 전용입니다.</span></div></div>`;
      c.querySelectorAll('[data-t]').forEach((b) => (b.onclick = () => { tab = b.dataset.t; render(); }));
      $('#save', c).onclick = () => demoOnly('설정 저장');
    };
    render();
  };

  /* ---------- 라우팅 / 셸 ---------- */
  function renderGuide(key) {
    const g = GUIDE[key], v = VIEWS.find((x) => x.key === key);
    $('#guide').innerHTML = `<h3>${v.icon} ${v.label} 메뉴 안내</h3><div class="summary">${g.summary}</div>
      <h4>무엇을 보여주나</h4><ul>${g.shows.map((x) => `<li>${x}</li>`).join('')}</ul>
      <h4>사용 순서</h4><ol>${g.steps.map((x) => `<li>${x}</li>`).join('')}</ol>
      <div class="note"><b>실제 시스템에서는</b><br/>${g.real}</div>
      <div class="try"><b>데모에서 해볼 것</b><ul style="margin-top:4px">${g.tips.map((x) => `<li>${x}</li>`).join('')}</ul></div>`;
  }

  function route() {
    const key = (location.hash.replace('#/', '') || 'MAIN').toUpperCase();
    const v = VIEWS.find((x) => x.key === key) || VIEWS[0];
    clearInterval(logTimer);
    document.querySelectorAll('.nav-button').forEach((b) => b.classList.toggle('active', b.dataset.key === v.key));
    $('#tabs').innerHTML = `<div class="tab-item active">${v.icon} ${v.label}</div>`;
    const c = $('#content'); c.innerHTML = '';
    R[v.key](c);
    renderGuide(v.key);
    document.title = `JbrainTrader 데모 — ${v.label}`;
    window.scrollTo(0, 0);
  }

  function buildNav() {
    $('#nav').innerHTML = VIEWS.map((v) => `<a class="nav-button ${v.featured ? 'featured' : ''}" href="#/${v.key}" data-key="${v.key}"><span class="nav-icon">${v.icon}</span><span class="nav-label">${v.label}</span></a>`).join('');
  }

  function initHelper() {
    const panel = $('#helper'), msgs = $('#helperMsgs');
    const say = (t, who = 'bot') => { msgs.appendChild(h(`<div class="msg ${who}">${esc(t)}</div>`)); msgs.scrollTop = msgs.scrollHeight; };
    say('안녕하세요! JbrainTrader 도우미입니다. 실제 대시보드에서는 Claude CLI가 답하지만, 데모에서는 미리 준비한 답만 드려요. 아래 질문을 눌러 보세요.');
    $('#helperQuick').innerHTML = DEMO.helper.map((q, i) => `<button data-q="${i}">${q.q}</button>`).join('');
    $('#helperQuick').querySelectorAll('button').forEach((b) => (b.onclick = () => { const q = DEMO.helper[b.dataset.q]; say(q.q, 'user'); setTimeout(() => say(q.a), 500); }));
    $('#helperBtn').onclick = () => panel.classList.toggle('show');
    $('#helperClose').onclick = () => panel.classList.remove('show');
    $('#helperSend').onclick = () => { const v = $('#helperIn').value.trim(); if (!v) return; say(v, 'user'); $('#helperIn').value = ''; setTimeout(() => say('데모 모드에서는 미리 준비된 질문에만 답할 수 있어요. 실제 시스템에서는 이 질문이 Claude CLI(JBRAIN_CHAT_MODEL)로 전달됩니다.'), 500); };
    $('#helperIn').onkeydown = (e) => { if (e.key === 'Enter') $('#helperSend').click(); };
  }

  function initModal() {
    const m = $('#loginModal');
    $('#connectBtn').onclick = () => m.classList.add('show');
    m.onclick = (e) => { if (e.target === m || e.target.closest('[data-close]')) m.classList.remove('show'); };
    m.querySelectorAll('.opt').forEach((o) => (o.onclick = () => { m.classList.remove('show'); toast(`${o.dataset.mode} 로그인 요청 → 게이트웨이가 키움 로그인 창을 자동 입력합니다 (데모)`, true); }));
  }

  document.addEventListener('DOMContentLoaded', () => {
    buildNav(); initHelper(); initModal();
    window.addEventListener('hashchange', route);
    route();
  });
})();
