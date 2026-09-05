/* ============================================================
   JbrainTrader 데모 — Mock 데이터
   모든 값은 데모용으로 만든 가짜 데이터입니다. 실제 계좌·시세·매매와 무관합니다.
   ============================================================ */
window.DEMO = window.DEMO || {};

DEMO.account = {
  name: '데모 사용자',
  broker: 'KIWOOM',
  mode: '모의투자',
  acc_no: '0000-****',
  acc_list: ['0000-**** [위탁]', '0000-**** [연금]'],
  market: 'DOMESTIC',
  balance: 12_480_350,
  total_buy: 18_250_000,
  total_eval: 18_912_400,
  today_pnl: 142_300,
};

DEMO.holdings = [
  { ticker: '005930', name: '삼성전자',        qty: 40,  avg: 71_200, cur: 73_900 },
  { ticker: '069500', name: 'KODEX 200',       qty: 120, avg: 36_450, cur: 36_980 },
  { ticker: '035420', name: 'NAVER',           qty: 12,  avg: 198_500, cur: 191_000 },
  { ticker: '005380', name: '현대차',          qty: 15,  avg: 236_000, cur: 244_500 },
  { ticker: '114800', name: 'KODEX 인버스',    qty: 300, avg: 4_120,  cur: 4_085 },
];

DEMO.watchlist = [
  { ticker: '005930', name: '삼성전자',   market: 'KOSPI',  price: 73_900,  strategy: 'GOLDEN_CROSS',        paused: false, qty: 40,  realized: 86_400,  real: true },
  { ticker: '000660', name: 'SK하이닉스', market: 'KOSPI',  price: 182_300, strategy: 'VOL_BREAKOUT_PRO',    paused: false, qty: 0,   realized: 21_900,  real: false },
  { ticker: '035720', name: '카카오',     market: 'KOSPI',  price: 48_150,  strategy: 'MEAN_REVERSION_BB',   paused: true,  qty: 0,   realized: -12_300, real: false },
  { ticker: '247540', name: '에코프로비엠', market: 'KOSDAQ', price: 152_800, strategy: 'SCALP_03',          paused: false, qty: 0,   realized: 34_100,  real: false },
  { ticker: '069500', name: 'KODEX 200',  market: 'ETF',    price: 36_980,  strategy: 'DUAL_200_1X_INVERSE', paused: false, qty: 120, realized: 12_600,  real: true },
  { ticker: 'AAPL',   name: 'Apple',      market: 'NASDAQ', price: 231.4,   strategy: 'TREND_FOLLOW_PRO',    paused: true,  qty: 0,   realized: 0,       real: false },
];

DEMO.logs = [
  '[ENGINE] 전략 엔진 시작 (64bit) — REST :5000 / WS :8765',
  '[ZMQ] 키움 게이트웨이 연결 확인 (5555/5556)',
  '[KIWOOM] 모의투자 서버 로그인 완료 — 계좌 2개 조회',
  '[DB] MySQL 연결 성공 (jbstock) — 테이블 점검 완료',
  '[STRATEGY] 005930 삼성전자 → GOLDEN_CROSS 로드',
  '[STRATEGY] 069500 KODEX 200 → DUAL_200_1X_INVERSE 로드 (페어 114800)',
  '[TICK] 005930 73,850 (+0.34%) vol 1,204',
  '[SIGNAL] 005930 BUY_STEP_1 조건 충족 (ema5 > ema20 상향돌파)',
  '[ORDER] 005930 매수 10주 @73,850 → 체결 완료',
  '[TICK] 069500 36,975 (-0.05%) z=0.42',
  '[AI] 아침 브리핑 생성 완료 → Discord #log 채널 전송',
  '[TICK] 000660 182,300 (+1.2%) vol 3,410',
  '[MONITOR] 035420 NAVER 현재가 191,000 — AI 손절가(188,000) 근접 경고',
  '[TICK] 247540 152,800 (+0.8%)',
  '[DUAL] 069500/114800 z-score 1.08 ≥ 임계값 1.0 → 인버스 1차 진입(40%)',
  '[ORDER] 114800 매수 195주 @4,085 → 체결 완료',
  '[TICK] 005930 73,900 (+0.41%)',
  '[JOURNAL] 오늘 실현손익 +142,300원 (3건) 집계',
  '[GSHEET] 매매일지 2026-09 탭 업로드 완료',
  '[DUAL] 069500/114800 z-score 0.12 → 익절Z 도달, 전량 청산 (+0.21%)',
];

DEMO.strategies = {
  single: [
    { name: 'DEFAULT', desc: '기본 전략 (RSI 과매도 매수 / 3% 익절)' },
    { name: 'GOLDEN_CROSS', desc: '단기 이평선(5)이 장기 이평선(20)을 상향 돌파할 때 매수' },
    { name: 'MEAN_REVERSION_BB', desc: '볼린저 하단 이탈 후 복귀 시 매수' },
    { name: 'VOL_BREAKOUT_PRO', desc: '거래량 급증 + 전고점 돌파' },
    { name: 'TREND_FOLLOW_PRO', desc: '추세 추종 (EMA 20/60 정배열)' },
    { name: 'SCALP_03', desc: 'BB Mean Reversion Scalper' },
    { name: 'SCALPING_3TICK', desc: '3틱 스캘핑' },
    { name: 'SPLIT_SCALPING', desc: '분할 스캘핑' },
    { name: 'COMPLEX_MARTINGALE_PYRAMID', desc: '불타기 감속 + 물타기 하방 제한 혼합' },
  ],
  dual: [
    { name: 'DUAL_200_1X_INVERSE', desc: 'KODEX 200 ↔ KODEX 인버스 스프레드' },
    { name: 'DUAL_KODEX_LEVERAGE_2X_INVERSE', desc: 'KODEX 레버리지 ↔ 인버스2X' },
    { name: 'DUAL_US_QQQ_SQQQ', desc: 'QQQ ↔ SQQQ (해외)' },
    { name: 'DUAL_US_SPY_SH', desc: 'SPY ↔ SH (해외)' },
  ],
  content: {
    GOLDEN_CROSS: `[INFO]
type = single
name = GOLDEN_CROSS
description = 단기 이평선(5)이 장기 이평선(20)을 상향 돌파할 때 매수

[BUY]
max_steps = 1

[BUY_STEP_1]
condition = (ema5 > ema20 and prev_ema5 <= prev_ema20)
size = 1.0

[STOP_LOSS]
condition = (price <= first_buy_price * 0.98) or (price < ema20)

[SELL]
max_steps = 2

[SELL_STEP_1]
condition = price >= first_buy_price * 1.03
size = 0.5

[SELL_STEP_2]
condition = ema5 < ema20
size = all`,
    DUAL_200_1X_INVERSE: `[설정]
type = dual
임계값 = 1.0
분할매수 = 40%, 30%, 30%
목표수익 = +0.2%
손절기준 = -1.5%
강제청산 = 15:20
매수금액 = 2,000,000
최대거래 = 일 5회
윈도우 = 30
익절Z = 0.0
시작시간 = 09:20`,
    SCALP_03: `[INFO]
type = single
name = SCALP_03
description = BB Mean Reversion Scalper

[BUY]
max_steps = 2

[BUY_STEP_1]
condition = price <= bb_lower and rsi < 30
size = 0.5

[BUY_STEP_2]
condition = price <= avg_price * 0.995
size = 0.5

[STOP_LOSS]
condition = price <= avg_price * 0.99

[SELL]
max_steps = 1

[SELL_STEP_1]
condition = price >= bb_mid
size = all`,
  },
  generic(name, type) {
    if (type === 'dual') {
      return `[설정]\ntype = dual\n임계값 = 1.2\n분할매수 = 50%, 50%\n목표수익 = +0.3%\n손절기준 = -1.2%\n강제청산 = 15:20\n매수금액 = 1,000,000\n최대거래 = 일 3회\n윈도우 = 20\n익절Z = 0.1\n시작시간 = 09:30`;
    }
    return `[INFO]\ntype = single\nname = ${name}\ndescription = (데모) ${name} 전략\n\n[BUY]\nmax_steps = 1\n\n[BUY_STEP_1]\ncondition = rsi < 35 and price > ema20\nsize = 1.0\n\n[STOP_LOSS]\ncondition = price <= first_buy_price * 0.97\n\n[SELL]\nmax_steps = 1\n\n[SELL_STEP_1]\ncondition = price >= first_buy_price * 1.03\nsize = all`;
  },
};

DEMO.aiPicks = {
  profiles: [
    { name: '주가_재무기반', model: 'opus', prompt: 'KOSPI 200 종목 중 최근 3년 매출 성장률 10% 이상, PER 15 이하, 부채비율 100% 이하인 종목 5개를 선별하고 각 종목의 선정 근거를 3줄로 정리해 주세요.' },
    { name: '수급_모멘텀', model: 'sonnet', prompt: '최근 20일 외국인·기관 순매수가 이어지고 60일 이평선을 상향 돌파한 종목을 찾아 주세요.' },
    { name: '배당_안정형', model: 'haiku', prompt: '배당수익률 4% 이상, 5년 연속 배당 증가 종목을 선별해 주세요.' },
  ],
  results: {
    '주가_재무기반': {
      ran_at: '2026-09-05 08:32',
      picks: [
        { ticker: '005930', name: '삼성전자',   score: 88, reason: '반도체 업황 회복으로 영업이익 개선, PER 11배로 밸류에이션 부담 낮음' },
        { ticker: '005380', name: '현대차',     score: 84, reason: '하이브리드 판매 호조, 배당 확대 정책, 부채비율 안정적' },
        { ticker: '000270', name: '기아',       score: 81, reason: '북미 판매 성장, 영업이익률 11%대 유지' },
        { ticker: '012330', name: '현대모비스', score: 76, reason: '전동화 부품 수주 증가, PER 7배 저평가' },
        { ticker: '055550', name: '신한지주',   score: 72, reason: '자사주 소각 지속, 배당수익률 5%대' },
      ],
    },
    '수급_모멘텀': {
      ran_at: '2026-09-04 16:10',
      picks: [
        { ticker: '000660', name: 'SK하이닉스', score: 90, reason: 'HBM 수요 지속, 외국인 12일 연속 순매수' },
        { ticker: '247540', name: '에코프로비엠', score: 74, reason: '60일선 돌파 후 거래량 3배 증가' },
        { ticker: '042700', name: '한미반도체', score: 71, reason: '기관 순매수 전환, 신고가 근접' },
      ],
    },
    '배당_안정형': null,
  },
};

DEMO.aiTrades = {
  profiles: [
    { name: '단기_스윙전략', model: 'opus', ticker: '005930', prompt: '보유 중인 종목에 대해 2~3주 스윙 관점에서 진입 가격대, 목표가, 손절가, 투자 비중을 제안해 주세요.' },
    { name: '중장기_적립', model: 'sonnet', ticker: '069500', prompt: '월 적립식으로 보유 중인 ETF의 추가 매수 가격대와 비중 조절 기준을 제안해 주세요.' },
  ],
  results: {
    '단기_스윙전략': {
      ran_at: '2026-09-05 08:40',
      target: 79_500, entry: '72,000 ~ 74,000', stop: 69_800, expected: '+7.6%', weight: '15%', period: '2~3주',
      buy_cond: ['5일 이평선이 20일 이평선 위에서 유지', '외국인 순매수 3일 연속 지속', '73,000원 지지 확인 후 분할 진입'],
      sell_cond: ['1차 목표 77,000원 도달 시 50% 익절', '2차 목표 79,500원 도달 시 잔량 정리', 'RSI 75 이상 과열 시 비중 축소'],
      risks: ['미국 반도체 관세 이슈 재부각', '환율 급등 시 외국인 매도 전환', '실적 발표(10월 말) 전 변동성 확대'],
      reason: '반도체 업황 개선 사이클 초입으로 판단되며, 현재가는 52주 고점 대비 8% 낮은 수준입니다. 20일 이평선 지지가 유효한 구간에서 분할 진입을 권장합니다.',
    },
    '중장기_적립': {
      ran_at: '2026-09-03 09:05',
      target: 39_000, entry: '35,500 ~ 36,800', stop: 33_900, expected: '+5.5%', weight: '25%', period: '3개월+',
      buy_cond: ['KOSPI 2,600 이하 조정 시 추가 매수', '월 1회 정기 매수 유지'],
      sell_cond: ['목표 수익률 +5% 도달 시 리밸런싱', '비중 30% 초과 시 일부 매도'],
      risks: ['글로벌 경기 둔화', '지수 박스권 장기화'],
      reason: '지수 ETF는 개별 종목 리스크가 낮아 적립식 운용에 적합합니다. 현 구간은 PBR 0.95배로 역사적 평균 하단입니다.',
    },
  },
};

DEMO.calendar = {
  profiles: [
    { name: '실적·경제지표', prompt: '보유 종목의 실적 발표일과 주요 한국·미국 경제지표 발표 일정을 정리해 주세요.' },
    { name: '배당·권리락', prompt: '보유 종목의 배당기준일과 권리락일을 정리해 주세요.' },
  ],
  year: 2026, month: 9,
  events: [
    { day: 3,  title: '미국 ISM 제조업 PMI', type: 'macro' },
    { day: 5,  title: '미국 고용보고서', type: 'macro' },
    { day: 10, title: '한국 8월 실업률', type: 'macro' },
    { day: 11, title: '미국 CPI 발표', type: 'macro' },
    { day: 17, title: 'FOMC 금리 결정', type: 'macro' },
    { day: 18, title: '삼성전자 파운드리 포럼', type: 'stock' },
    { day: 24, title: '현대차 IR 데이', type: 'stock' },
    { day: 26, title: '선물·옵션 만기일', type: 'market' },
    { day: 30, title: 'KODEX 200 분배금 기준일', type: 'dividend' },
  ],
};

DEMO.notices = [
  { time: '2026-09-05 08:30', channel: 'Discord #log', kind: '아침 브리핑', body: '전일 미 증시 혼조. 반도체 강세, 금리 민감주 약세. 오늘 관전 포인트: 미국 고용보고서(21:30). 보유 종목 중 NAVER가 AI 손절가(188,000)에 3% 근접했습니다.' },
  { time: '2026-09-04 14:52', channel: 'Discord #log', kind: '전략 이탈 감시', body: '⚠️ 035420 NAVER 현재가 189,500 — AI 매매 전략 손절가 188,000 대비 -0.8%. 확인이 필요합니다.' },
  { time: '2026-09-04 09:21', channel: 'Discord #log', kind: '체결 알림', body: '✅ 114800 KODEX 인버스 매수 195주 @4,085 체결 (DUAL_200_1X_INVERSE 1차 진입)' },
  { time: '2026-09-01 07:00', channel: 'Discord #log · 구글 시트', kind: '주간 매매 복기', body: '지난주 12건 매매, 승률 58%, 평균 보유 1.8일. 손절 지연 패턴 2건 발견: 손절 조건 도달 후 평균 40분 지연 청산. 다음 주 개선 과제로 자동 손절 활성화를 권장합니다.' },
  { time: '2026-08-29 15:35', channel: 'Discord #log', kind: '스코어카드', body: '📊 8월 AI 매매 전략 채점: 목표가 도달 4건 / 손절 도달 2건 / 진행 중 3건. 프로파일 "단기_스윙전략" 적중률 67%.' },
];

DEMO.journal = {
  year: 2026, month: 9,
  monthly_pnl: 486_200, trade_count: 23,
  days: {
    1: { pnl: 34_500, n: 2 }, 2: { pnl: -18_200, n: 3 }, 3: { pnl: 92_100, n: 4 },
    4: { pnl: 61_800, n: 3 }, 5: { pnl: 142_300, n: 3 },
    8: { pnl: -42_600, n: 2 }, 9: { pnl: 27_900, n: 1 }, 10: { pnl: 88_400, n: 3 },
    11: { pnl: 12_300, n: 1 }, 12: { pnl: 87_700, n: 1 },
  },
  detail: {
    5: [
      { name: '삼성전자',   buy: 73_850, sell: 74_600, qty: 10,  fee: 1_260,  pnl: 6_240 },
      { name: 'KODEX 인버스', buy: 4_085,  sell: 4_094,  qty: 195, fee: 740,   pnl: 1_015 },
      { name: 'SK하이닉스', buy: 178_200, sell: 182_300, qty: 33, fee: 2_010, pnl: 135_045 },
    ],
    3: [
      { name: '에코프로비엠', buy: 149_500, sell: 152_800, qty: 20, fee: 1_820, pnl: 64_180 },
      { name: '현대차',     buy: 240_000, sell: 244_500, qty: 6,  fee: 890,   pnl: 26_110 },
      { name: '카카오',     buy: 48_900,  sell: 48_150,  qty: 3,  fee: 90,    pnl: -2_340 },
      { name: 'KODEX 200',  buy: 36_900,  sell: 36_980,  qty: 50, fee: 220,   pnl: 3_780 },
    ],
  },
};

DEMO.cliTasks = [
  { time: '2026-09-05 16:20', cli: 'claude_cli', prompt: 'strategy 폴더의 전략 파일 이름을 대소문자 통일해줘', summary: '전략 파일 5개를 UPPER_SNAKE_CASE로 변경하고 코드·문서 참조 4곳을 수정', response: '파일명 변경: complex_martingale_pyramid → COMPLEX_MARTINGALE_PYRAMID 외 4개. export/martingale_mo.py의 STRATEGY_NAME 상수와 문서 3곳을 함께 수정했습니다.' },
  { time: '2026-09-05 15:40', cli: 'claude_cli', prompt: 'git으로 올라가는 것 중에 개인 정보가 있는지 확인해줘', summary: '328개 파일 검사, 민감 정보 없음. 로컬 경로가 든 설정 파일 1개 ignore 추가', response: '이메일·전화·API 키·계좌번호 패턴 검색 결과 노출 없음. .claude/launch.json을 .gitignore에 추가했습니다.' },
  { time: '2026-09-04 21:12', cli: 'antigravity_cli', prompt: '매매일지 구글 시트 업로드에 일별 요약 행을 추가해줘', summary: 'gsheet_exporter에 일별 합계 행 추가, 월별 탭 하단 요약 갱신', response: 'core/service/gsheet_exporter.py에 upload_daily_summary()를 추가하고 매매일지 업로드 후 자동 호출되도록 연결했습니다.' },
];

DEMO.dataMenu = [
  { name: '시세 데이터', children: [
    { name: '가져오기', children: [
      { name: '파일에서 가져오기 (CSV)', desc: 'CSV 파일을 업로드해 일봉/분봉 시세를 MySQL에 저장합니다. 열 이름을 자동 매핑합니다.' },
      { name: 'API에서 가져오기', desc: 'Yahoo Finance / KRX에서 기간을 지정해 시세를 내려받습니다. 수집기 탭과 같은 기능입니다.' },
    ]},
    { name: '가상', children: [
      { name: '기존 데이터 기반', desc: '실제 일봉의 변동성을 참고해 가짜 틱 데이터를 생성합니다. 시뮬레이션과 백테스트 입력으로 사용합니다.' },
    ]},
    { name: '조회', children: [
      { name: '종목별 조회', desc: '종목 하나를 골라 저장된 시세를 표와 캔들 차트로 확인합니다.' },
      { name: '날짜별 조회', desc: '특정 날짜에 저장된 모든 종목의 시세 유무를 달력으로 확인합니다. 빠진 날짜를 찾을 때 씁니다.' },
    ]},
  ]},
  { name: '매매 데이터', children: [
    { name: '가져오기', children: [
      { name: '파일에서 가져오기', desc: '증권사 체결내역 CSV를 올려 매매 기록을 저장합니다.' },
      { name: '전략 결과에서 생성', desc: '백테스트 결과의 체결 목록을 매매 데이터로 변환합니다.' },
      { name: '가상 매매', children: [
        { name: '가상 시세 기반 생성', desc: '가상 틱 데이터 위에서 전략을 돌려 매매 기록을 만듭니다.' },
        { name: '랜덤 매매 생성', desc: '통계 화면 테스트용으로 무작위 매매를 생성합니다.' },
      ]},
    ]},
    { name: '조회', children: [
      { name: '매수 / 매도 내역', desc: '기간별 체결 내역을 시간순으로 봅니다.' },
      { name: '전략별 조회', desc: '전략 이름으로 묶어 어떤 전략이 얼마나 벌었는지 봅니다.' },
      { name: '날짜별 조회', desc: '하루 단위 매매를 봅니다.' },
      { name: '가상 매매', desc: '시뮬레이션에서 생긴 매매만 따로 봅니다.' },
      { name: '매매 요약', desc: '종목·전략별 요약 테이블입니다.' },
    ]},
    { name: '통계', children: [
      { name: '손익 분석', desc: '누적 손익 곡선과 월별 손익을 그립니다.' },
      { name: '승률', desc: '전략별 승률과 손익비를 계산합니다.' },
      { name: '최대 낙폭', desc: 'MDD(최대 낙폭)와 회복 기간을 계산합니다.' },
      { name: '매매 횟수', desc: '요일·시간대별 매매 빈도를 봅니다.' },
    ]},
  ]},
  { name: '백테스트', children: [
    { name: '실행', children: [
      { name: '기존 데이터 기반', desc: '저장된 시세로 단일 종목 전략을 백테스트합니다. 결과는 체결 목록·수익 곡선으로 저장됩니다.' },
      { name: '랜덤 데이터', desc: '무작위 시세로 전략 로직만 빠르게 점검합니다.' },
      { name: '듀얼 데이터 기반', desc: '정방향/인버스 ETF 페어로 스프레드 Z-Score 전략을 백테스트합니다. 임계값을 바꿔 비교할 수 있습니다.' },
    ]},
    { name: '조회', desc: '과거 백테스트 결과 목록을 보고 다시 열거나 삭제합니다.' },
  ]},
  { name: '시뮬레이션', children: [
    { name: '기존 데이터 기반', desc: '저장된 틱을 실시간처럼 흘려보내며 전략이 실제로 어떻게 반응하는지 화면에서 봅니다.' },
    { name: '랜덤 데이터', desc: '무작위 틱으로 전략 반응을 봅니다.' },
  ]},
];

DEMO.backtestSample = {
  strategy: 'GOLDEN_CROSS', ticker: '005930 삼성전자', period: '2026-01-02 ~ 2026-06-30',
  trades: 14, win_rate: '64.3%', pnl: '+9.8%', mdd: '-4.1%',
  curve: [0, 0.8, 1.9, 1.2, 2.7, 3.9, 3.1, 4.6, 5.8, 5.2, 6.9, 8.1, 7.4, 9.8],
};

DEMO.collectorLog = [
  '[Yahoo] 005930.KS 일봉 2025-09-05 ~ 2026-09-05 요청',
  '[Yahoo] 005930.KS 246행 수신 → MySQL ohlcv_daily 저장',
  '[Yahoo] 069500.KS 일봉 요청',
  '[Yahoo] 069500.KS 246행 수신 → 저장',
  '[Yahoo] AAPL 일봉 요청',
  '[Yahoo] AAPL 251행 수신 → 저장',
  '[DONE] 3종목 수집 완료 (743행, 4.2초)',
];

DEMO.helper = [
  { q: '관심종목에서 "시작"을 누르면 뭐가 돼요?', a: '그 종목에 지정된 전략이 실시간 틱을 받으며 매수/매도 조건을 평가하기 시작합니다. "중지"를 누르면 신호 평가만 멈추고 보유 포지션은 그대로 둡니다.' },
  { q: '듀얼 전략의 Z-Score가 뭔가요?', a: '정방향 ETF와 인버스 ETF 가격 비율의 최근 N개(윈도우) 평균 대비 표준편차 배수입니다. 임계값을 넘으면 비율이 평균으로 돌아올 것을 기대하고 진입합니다.' },
  { q: 'AI 기능은 API 키가 필요한가요?', a: '아니요. 로컬에 설치된 Claude CLI를 호출하므로 claude 명령이 PATH에 있고 로그인만 되어 있으면 됩니다.' },
];
