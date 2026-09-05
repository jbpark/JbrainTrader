<template>
  <div class="main-tab-content glass" style="flex: 1; overflow: hidden; display: flex; flex-direction: column; gap: 1.5rem; padding: 2.5rem">
    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid var(--primary); padding-bottom: 1rem">
      <h2 style="color: var(--primary); margin: 0; display: flex; align-items: center; gap: 12px">
        <span style="font-size: 1.8rem">🤖</span> AI 매매
      </h2>
      <div style="display: flex; align-items: center; gap: 14px">
        <button class="refresh-btn" @click="loadProfiles" title="모바일 등 다른 기기에서 변경된 내용을 다시 불러옵니다">🔄 새로고침</button>
        <div style="text-align: right">
          <div style="font-size: 0.9rem; color: var(--text-main); font-weight: 600">매매 전략 프로파일</div>
          <div style="font-size: 0.8rem; color: var(--primary)">{{ profiles.length }}개</div>
        </div>
      </div>
    </div>

    <div style="display: flex; gap: 20px; flex: 1; min-height: 0">
      <!-- List -->
      <div style="width: 280px; border-right: 1px solid rgba(255,255,255,0.1); overflow-y: auto; padding-right: 10px; display: flex; flex-direction: column; gap: 1rem">
        <button class="primary" style="width: 100%" @click="handleNew">+ 새 프로파일 생성</button>

        <div style="display: flex; flex-direction: column; gap: 8px">
          <div
            v-for="p in profiles"
            :key="p.id"
            class="trade-item-card"
            :class="{ active: selected?.id === p.id }"
            @click="handleSelect(p)"
          >
            <div style="display: flex; justify-content: space-between; align-items: center; width: 100%">
              <span class="trade-name">{{ p.name }}</span>
              <button class="danger-btn" @click.stop="handleDelete(p)">삭제</button>
            </div>
            <div class="trade-model">{{ modelLabel(p.model) }}</div>
            <div class="trade-status" v-if="p.last_status">
              <span :class="'st-' + p.last_status">{{ statusLabel(p.last_status) }}</span>
              <span v-if="p.last_ticker_name || p.last_ticker" class="trade-target">
                {{ p.last_ticker_name || p.last_ticker }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Editor + Result -->
      <div style="flex: 1; display: flex; flex-direction: column; gap: 1rem; min-width: 0; overflow-y: auto">
        <template v-if="isEditing">
          <div style="display: flex; flex-direction: column; gap: 8px">
            <label style="font-size: 0.85rem; color: var(--text-muted)">프로파일 명칭</label>
            <input
              type="text"
              placeholder="프로파일 이름을 입력하세요 (예: 단기_스윙전략)"
              v-model="name"
              style="padding: 12px; font-size: 1.1rem; font-weight: bold; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1); color: white; border-radius: 8px"
            />
          </div>

          <!-- 대상 종목 선택 -->
          <div style="display: flex; flex-direction: column; gap: 8px">
            <label style="font-size: 0.85rem; color: var(--text-muted)">대상 종목</label>
            <div style="display: flex; gap: 10px; flex-wrap: wrap">
              <select v-model="selectedProfileId" class="ticker-select" @change="onProfileChange">
                <option :value="null">— AI 종목 프로파일 선택 —</option>
                <option v-if="holdings.length > 0" :value="HOLDINGS_KEY">
                  💼 보유종목 ({{ holdings.length }}종목)
                </option>
                <option v-for="g in pickGroups" :key="g.profileId" :value="g.profileId">
                  {{ g.profileName }} ({{ g.stocks.length }}종목)
                </option>
              </select>
              <select v-model="selectedTicker" class="ticker-select" :disabled="!selectedProfileId">
                <option value="">
                  {{ selectedProfileId ? (isHoldingsGroup ? '— 보유종목 선택 —' : '— 종목 선택 (수익률 높은 순) —') : '— 프로파일을 먼저 선택 —' }}
                </option>
                <option v-for="(s, i) in profileStocks" :key="s.ticker" :value="s.ticker">
                  {{ !isHoldingsGroup && i === 0 ? '🥇 ' : '' }}{{ s.name }} ({{ s.ticker }}){{ s.upside ? ' · ' + s.upside : '' }}
                </option>
              </select>
              <input
                type="text"
                v-model="manualTicker"
                placeholder="또는 직접 입력 (종목명 또는 6자리 코드)"
                class="ticker-input"
              />
            </div>
            <div v-if="pickStocks.length === 0" style="font-size: 0.8rem; color: var(--warning)">
              ⚠️ AI 종목에서 선별된 종목이 없습니다. AI 종목 탭에서 먼저 실행하거나 직접 입력하세요.
            </div>
            <div v-if="targetLabel" style="font-size: 0.8rem; color: var(--secondary)">
              분석 대상: {{ targetLabel }}
            </div>

            <!-- 선택한 종목을 보유 중이면 현재 보유 현황 표시 -->
            <div v-if="selectedHolding" class="holding-box">
              <div class="holding-head">
                💼 현재 보유 중
                <span class="muted" style="font-weight: 400">{{ selectedHolding.name }} ({{ selectedHolding.ticker }})</span>
              </div>
              <div class="holding-grid">
                <div class="h-item">
                  <span class="h-label">보유수량</span>
                  <span class="h-value">{{ Number(selectedHolding.qty || 0).toLocaleString() }}주</span>
                </div>
                <div class="h-item">
                  <span class="h-label">매입단가</span>
                  <span class="h-value">{{ won(selectedHolding.buy_price) }}</span>
                </div>
                <div class="h-item">
                  <span class="h-label">현재가</span>
                  <span class="h-value">{{ won(selectedHolding.current_price) }}</span>
                </div>
                <div class="h-item">
                  <span class="h-label">매입금액</span>
                  <span class="h-value">{{ won(holdingStats.cost) }}</span>
                </div>
                <div class="h-item">
                  <span class="h-label">평가손익</span>
                  <span class="h-value" :class="holdingStats.profitClass">
                    {{ holdingStats.profit >= 0 ? '+' : '' }}{{ Math_round(holdingStats.profit).toLocaleString() }}원
                  </span>
                </div>
                <div class="h-item">
                  <span class="h-label">수익률</span>
                  <span class="h-value" :class="holdingStats.profitClass">
                    {{ holdingStats.rate >= 0 ? '+' : '' }}{{ holdingStats.rate.toFixed(2) }}%
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div style="display: flex; flex-direction: column; gap: 8px">
            <label style="font-size: 0.85rem; color: var(--text-muted)">실행 AI 모델</label>
            <select v-model="model" class="model-select">
              <option v-for="m in models" :key="m.id" :value="m.id">{{ m.label }}</option>
            </select>
          </div>

          <div style="display: flex; flex-direction: column; gap: 8px">
            <label style="font-size: 0.85rem; color: var(--text-muted)">매매 전략 프롬프트</label>
            <textarea
              placeholder="선택한 종목을 어떻게 매매할지 AI에게 물어볼 내용을 입력하세요"
              style="min-height: 130px; font-size: 0.95rem; padding: 15px; background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.1); color: #00f2fe; border-radius: 8px; resize: vertical; line-height: 1.6"
              v-model="prompt"
            ></textarea>
          </div>

          <div style="display: flex; gap: 12px; justify-content: flex-end">
            <button class="secondary" @click="cancelEdit" style="padding: 10px 20px">편집 취소</button>
            <button class="primary" @click="handleSave" style="padding: 10px 25px">저장하기</button>
            <button
              class="run-btn"
              @click="handleRun"
              :disabled="running || !selected?.id || !effectiveTicker"
              :title="!effectiveTicker ? '대상 종목을 먼저 선택하세요' : '선택한 종목의 매매 전략을 AI에게 요청합니다'"
            >
              <span v-if="running" class="mini-spinner"></span>
              {{ running ? '분석 중... (수 분 소요)' : '▶ 전략 요청' }}
            </button>
          </div>

          <!-- Result -->
          <div v-if="result" class="result-box">
            <div class="result-header">
              <h3 style="margin: 0; color: var(--primary); font-size: 1rem">
                📈 매매 전략
                <span v-if="result.ticker_name || result.ticker" style="color: var(--text-main); font-weight: 500">
                  — {{ result.ticker_name || result.ticker }}
                </span>
              </h3>
              <div style="display: flex; align-items: center; gap: 12px">
                <button
                  v-if="result.status === 'done' && chartLevels"
                  class="chart-btn"
                  :class="{ on: showChart }"
                  @click="showChart = !showChart"
                  title="가격대별 매매 전략을 그래프로 표시합니다"
                >
                  📈 {{ showChart ? '그래프 닫기' : '그래프' }}
                </button>
                <button
                  v-if="result.status === 'done' && result.strategy"
                  class="gsheet-btn"
                  :disabled="exportingSheet"
                  @click="handleExportStrategy"
                  :title="`구글 시트의 '${selected?.name}' 탭에 업로드합니다 (같은 종목은 갱신)`"
                >
                  <span v-if="exportingSheet" class="mini-spinner"></span>
                  {{ exportingSheet ? '업로드 중...' : '📗 구글 시트 업로드' }}
                </button>
                <a v-if="gsheetUrl" :href="gsheetUrl" target="_blank" class="gsheet-link">시트 열기 ↗</a>
                <span v-if="result.finished_at" style="font-size: 0.78rem; color: var(--text-muted)">
                  {{ result.finished_at }} · {{ result.model }}
                </span>
              </div>
            </div>

            <div v-if="result.status === 'running'" class="result-empty">
              <span class="mini-spinner"></span> AI가 매매 전략을 분석하는 중입니다... (최대 15분)
            </div>

            <div v-else-if="result.status === 'error'" class="result-error">
              ⚠️ {{ result.error }}
              <pre v-if="result.raw_text" class="raw-text">{{ result.raw_text }}</pre>
            </div>

            <template v-else-if="result.status === 'done' && result.strategy">
              <div class="strategy-summary">
                <span class="market-badge" :class="result.strategy.market === '코스피' ? 'kospi' : 'kosdaq'">
                  {{ result.strategy.market }}
                </span>
                <strong style="font-size: 1.05rem">{{ result.strategy.name }}</strong>
                <span class="muted">{{ result.strategy.ticker }}</span>
                <span class="risk-badge" :class="riskClass(result.strategy.risk_level)">
                  리스크 {{ result.strategy.risk_level }}
                </span>
              </div>
              <p class="summary-text">{{ result.strategy.summary }}</p>

              <!-- 가격대별 매매 전략 그래프 -->
              <div v-if="showChart && chartLevels" class="chart-box">
                <svg :viewBox="`0 0 ${CH.w} ${CH.h}`" class="price-chart" preserveAspectRatio="xMidYMid meet">
                  <!-- 진입 가격대 밴드 -->
                  <rect
                    :x="CH.padL" :y="chartLevels.entryTop"
                    :width="CH.plotW" :height="chartLevels.entryHeight"
                    fill="rgba(0,212,255,0.13)" stroke="rgba(0,212,255,0.5)" stroke-dasharray="4 3"
                  />
                  <!-- 손절 ~ 목표 구간 세로축 -->
                  <line :x1="CH.padL" :y1="chartLevels.target.y" :x2="CH.padL" :y2="chartLevels.stop.y"
                        stroke="rgba(255,255,255,0.15)" stroke-width="1" />

                  <!-- 각 가격 레벨 -->
                  <g v-for="lv in chartLevels.lines" :key="lv.key">
                    <line
                      :x1="CH.padL" :y1="lv.y" :x2="CH.w - CH.padR" :y2="lv.y"
                      :stroke="lv.color" :stroke-width="lv.key === 'current' ? 2 : 1.6"
                      :stroke-dasharray="lv.key === 'current' ? '5 4' : ''"
                    />
                    <text :x="CH.padL - 8" :y="lv.y + 4" text-anchor="end"
                          :fill="lv.color" font-size="11" font-weight="600">
                      {{ lv.price.toLocaleString() }}
                    </text>
                    <text :x="CH.w - CH.padR + 8" :y="lv.y + 4" :fill="lv.color" font-size="11">
                      {{ lv.label }}<tspan v-if="lv.diff" fill="rgba(255,255,255,0.45)"> ({{ lv.diff }})</tspan>
                    </text>
                  </g>
                </svg>

                <div class="chart-legend">
                  <span class="lg"><i style="background: #00D084"></i>목표가</span>
                  <span class="lg"><i style="background: #00A8CC"></i>진입 가격대</span>
                  <span class="lg"><i style="background: #FFFFFF"></i>현재가</span>
                  <span class="lg"><i style="background: #FF4D4D"></i>손절가</span>
                  <span v-if="chartLevels.rr" class="rr-badge" :class="chartLevels.rrClass">
                    손익비 {{ chartLevels.rr }} : 1
                  </span>
                </div>
              </div>

              <div class="metric-grid">
                <div class="metric">
                  <span class="m-label">현재가</span>
                  <span class="m-value">{{ won(result.strategy.current_price) }}</span>
                </div>
                <div class="metric">
                  <span class="m-label">진입 가격대</span>
                  <span class="m-value entry">{{ result.strategy.entry_price }}</span>
                </div>
                <div class="metric">
                  <span class="m-label">목표가</span>
                  <span class="m-value target">{{ won(result.strategy.target_price) }}</span>
                </div>
                <div class="metric">
                  <span class="m-label">손절가</span>
                  <span class="m-value stop">{{ won(result.strategy.stop_loss) }}</span>
                </div>
                <div class="metric">
                  <span class="m-label">기대 수익</span>
                  <span class="m-value target">{{ result.strategy.expected_return }}</span>
                </div>
                <div class="metric">
                  <span class="m-label">투자 비중</span>
                  <span class="m-value">{{ result.strategy.position_size }}</span>
                </div>
                <div class="metric">
                  <span class="m-label">보유 기간</span>
                  <span class="m-value">{{ result.strategy.holding_period }}</span>
                </div>
              </div>

              <div class="cond-grid">
                <div class="cond-box buy">
                  <h4>✅ 매수 조건</h4>
                  <ul><li v-for="(c, i) in result.strategy.buy_conditions" :key="'b'+i">{{ c }}</li></ul>
                </div>
                <div class="cond-box sell">
                  <h4>🎯 매도 조건</h4>
                  <ul><li v-for="(c, i) in result.strategy.sell_conditions" :key="'s'+i">{{ c }}</li></ul>
                </div>
                <div class="cond-box risk">
                  <h4>⚠️ 리스크 요인</h4>
                  <ul><li v-for="(c, i) in result.strategy.risks" :key="'r'+i">{{ c }}</li></ul>
                </div>
              </div>

              <div v-if="result.strategy.reason" class="reason-box">
                <strong>근거</strong>
                <p>{{ result.strategy.reason }}</p>
              </div>

              <p class="disclaimer">※ AI가 생성한 참고용 정보입니다. 투자 판단과 책임은 본인에게 있습니다.</p>
            </template>
          </div>
        </template>

        <div v-else style="flex: 1; display: flex; align-items: center; justify-content: center; color: var(--text-muted); border: 1px dashed rgba(255,255,255,0.1); border-radius: 12px">
          <div style="text-align: center">
            <div style="font-size: 3rem; margin-bottom: 1rem">🤖</div>
            <h3>프로파일을 선택하거나 새로 만들어주세요</h3>
            <p>종목을 선택하고 실행하면 AI가 제안한 매매 전략이 표시됩니다.</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import {
  fetchAiTrades, createAiTrade, updateAiTrade, deleteAiTrade,
  runAiTrade, fetchAiTradeResult, fetchAiPickModels, fetchAiPickStocks,
  exportAiTradeToGSheet,
} from '../api';

const props = defineProps({
  holdings: { type: Array, default: () => [] },
});

// 보유종목 그룹 식별자 (AI 종목 프로파일 id와 구분되도록 문자열 사용)
const HOLDINGS_KEY = 'HOLDINGS';

const FALLBACK_MODELS = [
  { id: 'claude-fable-5', label: 'Fable 5 (최고 성능)' },
  { id: 'claude-opus-5', label: 'Opus 5' },
  { id: 'claude-sonnet-5', label: 'Sonnet 5' },
  { id: 'claude-haiku-4-5', label: 'Haiku 4.5 (빠름/저비용)' },
];

const profiles = ref([]);
const pickStocks = ref([]);   // AI 종목이 선별한 종목 목록
const models = ref(FALLBACK_MODELS);
const defaultModel = ref('claude-opus-5');
const selected = ref(null);
const isEditing = ref(false);
const name = ref('');
const prompt = ref('');
const model = ref('claude-opus-5');
const selectedProfileId = ref(null);
const selectedTicker = ref('');
const manualTicker = ref('');
const result = ref(null);
const running = ref(false);
const exportingSheet = ref(false);
const gsheetUrl = ref(null);

let pollId = null;

// AI 종목 선별 결과를 프로파일별로 그룹화 (각 그룹은 서버에서 수익률 내림차순 정렬됨)
const pickGroups = computed(() => {
  const groups = new Map();
  for (const s of pickStocks.value) {
    if (!groups.has(s.profile_id)) {
      groups.set(s.profile_id, { profileId: s.profile_id, profileName: s.profile_name, stocks: [] });
    }
    groups.get(s.profile_id).stocks.push(s);
  }
  return [...groups.values()];
});

const holdings = computed(() => props.holdings || []);
const isHoldingsGroup = computed(() => selectedProfileId.value === HOLDINGS_KEY);

// 수수료·세금이 반영된 평가손익 기준 수익률 (서버 ratio와 동일 기준)
const holdingRate = (h) => {
  const cost = (Number(h.buy_price) || 0) * (Number(h.qty) || 0);
  if (cost > 0) return (Number(h.profit) || 0) / cost * 100;
  return Number(h.ratio) || 0;
};

// 보유종목을 종목 목록 형태로 변환 (수익률을 upside 자리에 표시)
const holdingStocks = computed(() =>
  holdings.value.map(h => {
    const rate = holdingRate(h);
    return {
      ticker: String(h.ticker || ''),
      name: h.name || h.ticker,
      upside: `${rate >= 0 ? '+' : ''}${rate.toFixed(1)}%`,
    };
  })
);

// 선택된 그룹의 종목 (AI 종목은 수익률 높은 순, 보유종목은 보유 순서)
const profileStocks = computed(() => {
  if (isHoldingsGroup.value) return holdingStocks.value;
  return pickGroups.value.find(g => g.profileId === selectedProfileId.value)?.stocks || [];
});

// 선택한 종목의 보유 정보 (보유 중이 아니면 null)
const selectedHolding = computed(() => {
  const t = effectiveTicker.value;
  if (!t) return null;
  return holdings.value.find(h => String(h.ticker) === t) || null;
});

const holdingStats = computed(() => {
  const h = selectedHolding.value;
  if (!h) return { cost: 0, profit: 0, rate: 0, profitClass: '' };
  const cost = (Number(h.buy_price) || 0) * (Number(h.qty) || 0);
  const profit = Number(h.profit) || 0;   // 수수료·세금 반영된 서버 평가손익
  const rate = holdingRate(h);
  return {
    cost, profit, rate,
    profitClass: profit > 0 ? 'val-pos' : profit < 0 ? 'val-neg' : '',
  };
});

const Math_round = (v) => Math.round(v);

const onProfileChange = () => {
  // 프로파일이 바뀌면 종목 선택 초기화
  selectedTicker.value = '';
};

// 드롭다운 선택이 우선, 없으면 직접 입력값 사용
const effectiveTicker = computed(() => selectedTicker.value || manualTicker.value.trim());
const effectiveTickerName = computed(() => {
  if (selectedTicker.value) {
    return pickStocks.value.find(s => s.ticker === selectedTicker.value)?.name
        || holdings.value.find(h => String(h.ticker) === selectedTicker.value)?.name
        || '';
  }
  // 직접 입력이 6자리 숫자가 아니면 종목명으로 간주
  const v = manualTicker.value.trim();
  return /^\d{6}$/.test(v) ? '' : v;
});
const targetLabel = computed(() => {
  if (!effectiveTicker.value) return '';
  const n = effectiveTickerName.value;
  return n && n !== effectiveTicker.value ? `${n} (${effectiveTicker.value})` : effectiveTicker.value;
});

const statusLabel = (s) => ({ running: '실행 중', done: '완료', error: '오류' }[s] || s);
const modelLabel = (id) => models.value.find(m => m.id === id)?.label || id || '';
const won = (v) => (Number(v) || 0).toLocaleString() + '원';
const riskClass = (lv) => ({ '낮음': 'low', '중간': 'mid', '높음': 'high' }[lv] || 'mid');

// ── 가격대별 매매 전략 그래프 ──
const showChart = ref(false);

// SVG 좌표 상수
const CH = { w: 720, h: 300, padL: 78, padR: 150, padT: 26, padB: 26, plotW: 720 - 78 - 150 };

const toNum = (v) => {
  if (v === null || v === undefined || v === '') return null;
  if (typeof v === 'number') return v;
  const m = String(v).replace(/,/g, '').match(/-?\d+(\.\d+)?/);
  return m ? parseFloat(m[0]) : null;
};

// "105,000 ~ 113,000" -> [105000, 113000] / "270,000" -> [270000, 270000]
const parseRange = (v) => {
  if (v === null || v === undefined) return null;
  const nums = String(v).replace(/,/g, '').match(/\d+(\.\d+)?/g);
  if (!nums || nums.length === 0) return null;
  const arr = nums.map(parseFloat);
  return [Math.min(...arr), Math.max(...arr)];
};

const chartLevels = computed(() => {
  const s = result.value?.strategy;
  if (!s) return null;
  const cur = toNum(s.current_price);
  const target = toNum(s.target_price);
  const stop = toNum(s.stop_loss);
  const entry = parseRange(s.entry_price);
  // 최소한 현재가/목표가/손절가가 있어야 그래프를 그릴 수 있음
  if (cur === null || target === null || stop === null) return null;

  const all = [cur, target, stop, ...(entry || [])];
  let min = Math.min(...all), max = Math.max(...all);
  const pad = (max - min) * 0.12 || Math.max(max * 0.02, 1);
  min -= pad; max += pad;

  const plotH = CH.h - CH.padT - CH.padB;
  const y = (p) => CH.padT + ((max - p) / (max - min)) * plotH;
  const pct = (p) => {
    const d = ((p - cur) / cur) * 100;
    return `${d >= 0 ? '+' : ''}${d.toFixed(1)}%`;
  };

  const lines = [
    { key: 'target', price: target, y: y(target), color: '#00D084', label: '목표가', diff: pct(target) },
  ];
  if (entry) {
    lines.push({ key: 'entryHi', price: entry[1], y: y(entry[1]), color: '#00A8CC', label: '진입 상단', diff: pct(entry[1]) });
    if (entry[0] !== entry[1]) {
      lines.push({ key: 'entryLo', price: entry[0], y: y(entry[0]), color: '#00A8CC', label: '진입 하단', diff: pct(entry[0]) });
    }
  }
  lines.push({ key: 'current', price: cur, y: y(cur), color: '#FFFFFF', label: '현재가', diff: '' });
  lines.push({ key: 'stop', price: stop, y: y(stop), color: '#FF4D4D', label: '손절가', diff: pct(stop) });

  // 손익비 = (목표가 - 진입가) / (진입가 - 손절가), 진입가는 밴드 중앙값
  const entryMid = entry ? (entry[0] + entry[1]) / 2 : cur;
  const risk = entryMid - stop;
  const reward = target - entryMid;
  let rr = null, rrClass = '';
  if (risk > 0 && reward > 0) {
    const v = reward / risk;
    rr = v.toFixed(1);
    rrClass = v >= 2 ? 'rr-good' : v >= 1 ? 'rr-mid' : 'rr-bad';
  }

  const entryTop = entry ? y(entry[1]) : y(cur);
  const entryBottom = entry ? y(entry[0]) : y(cur);

  return {
    lines,
    target: { y: y(target) },
    stop: { y: y(stop) },
    entryTop,
    entryHeight: Math.max(entryBottom - entryTop, 2),
    rr, rrClass,
  };
});

const loadModels = async () => {
  const res = await fetchAiPickModels();
  if (res && Array.isArray(res.models) && res.models.length > 0) {
    models.value = res.models;
    defaultModel.value = res.default || res.models[0].id;
  }
};

const loadProfiles = async () => {
  const res = await fetchAiTrades();
  if (Array.isArray(res)) profiles.value = res;
  // AI 종목 선별 결과도 함께 갱신 (대상 종목 드롭다운)
  const stocks = await fetchAiPickStocks();
  if (Array.isArray(stocks)) pickStocks.value = stocks;
};

const loadResult = async (id) => {
  const res = await fetchAiTradeResult(id);
  if (!res || res.status === 'NONE') {
    result.value = null;
    running.value = false;
    return;
  }
  result.value = res;
  running.value = res.status === 'running';
  if (!running.value) stopPolling();
};

const startPolling = (id) => {
  stopPolling();
  pollId = setInterval(async () => {
    await loadResult(id);
    if (!running.value) loadProfiles();
  }, 3000);
};

const stopPolling = () => {
  if (pollId) { clearInterval(pollId); pollId = null; }
};

const handleSelect = async (p) => {
  selected.value = p;
  showChart.value = false;
  gsheetUrl.value = null;
  name.value = p.name;
  prompt.value = p.prompt;
  model.value = p.model || defaultModel.value;
  // 이전 실행 종목을 기본 선택으로 복원 (그룹까지 함께 복원)
  const prev = p.last_ticker ? pickStocks.value.find(s => s.ticker === p.last_ticker) : null;
  const prevHolding = p.last_ticker
    ? holdings.value.find(h => String(h.ticker) === p.last_ticker) : null;
  if (prev) {
    selectedProfileId.value = prev.profile_id;
    selectedTicker.value = prev.ticker;
    manualTicker.value = '';
  } else if (prevHolding) {
    selectedProfileId.value = HOLDINGS_KEY;
    selectedTicker.value = String(prevHolding.ticker);
    manualTicker.value = '';
  } else {
    selectedProfileId.value = null;
    selectedTicker.value = '';
    manualTicker.value = p.last_ticker || '';
  }
  isEditing.value = true;
  await loadResult(p.id);
  if (running.value) startPolling(p.id);
};

const handleNew = () => {
  selected.value = null;
  name.value = '';
  prompt.value = '';
  model.value = defaultModel.value;
  selectedProfileId.value = null;
  selectedTicker.value = '';
  manualTicker.value = '';
  result.value = null;
  running.value = false;
  stopPolling();
  isEditing.value = true;
};

const cancelEdit = () => {
  isEditing.value = false;
  selected.value = null;
  result.value = null;
  stopPolling();
};

const handleSave = async () => {
  if (!name.value.trim() || !prompt.value.trim()) {
    alert('이름과 프롬프트를 모두 입력하세요.');
    return;
  }
  const res = selected.value?.id
    ? await updateAiTrade(selected.value.id, name.value, prompt.value, model.value)
    : await createAiTrade(name.value, prompt.value, model.value);
  if (res.status !== 'SUCCESS') {
    alert('저장 실패: ' + res.message);
    return;
  }
  if (!selected.value?.id) {
    selected.value = { id: res.id, name: name.value, prompt: prompt.value, model: model.value };
  } else {
    selected.value = { ...selected.value, name: name.value, prompt: prompt.value, model: model.value };
  }
  await loadProfiles();
  alert('저장되었습니다.');
};

const handleDelete = async (p) => {
  if (!confirm(`'${p.name}' 프로파일을 삭제할까요?`)) return;
  await deleteAiTrade(p.id);
  if (selected.value?.id === p.id) cancelEdit();
  loadProfiles();
};

const handleRun = async () => {
  if (!selected.value?.id) {
    alert('먼저 프로파일을 저장한 뒤 실행하세요.');
    return;
  }
  if (!effectiveTicker.value) {
    alert('대상 종목을 선택하거나 직접 입력하세요.');
    return;
  }
  // 편집 중 변경 사항이 있으면 저장 후 실행
  if (name.value !== selected.value.name || prompt.value !== selected.value.prompt
      || model.value !== (selected.value.model || defaultModel.value)) {
    const res = await updateAiTrade(selected.value.id, name.value, prompt.value, model.value);
    if (res.status !== 'SUCCESS') {
      alert('저장 실패: ' + res.message);
      return;
    }
    selected.value = { ...selected.value, name: name.value, prompt: prompt.value, model: model.value };
  }
  const res = await runAiTrade(selected.value.id, effectiveTicker.value, effectiveTickerName.value);
  if (res.status === 'ERROR') {
    alert('실행 실패: ' + res.message);
    return;
  }
  running.value = true;
  showChart.value = false;
  gsheetUrl.value = null;
  result.value = {
    status: 'running',
    ticker: effectiveTicker.value,
    ticker_name: effectiveTickerName.value,
  };
  startPolling(selected.value.id);
};

// 매매 전략을 구글 시트에 업로드 (탭 = 프로파일명, 같은 종목이면 해당 행 갱신)
const handleExportStrategy = async () => {
  if (!selected.value?.id || exportingSheet.value) return;
  exportingSheet.value = true;
  gsheetUrl.value = null;
  try {
    const res = await exportAiTradeToGSheet(selected.value.id);
    if (res.status === 'SUCCESS') {
      gsheetUrl.value = res.url || null;
      alert(`구글 시트 '${res.sheet}' 탭에 ${res.ticker_name || res.ticker} 전략을 `
            + `${res.updated ? '갱신' : '추가'}했습니다. (총 ${res.rows}종목)`);
    } else {
      alert('업로드 실패: ' + (res.message || '알 수 없는 오류'));
    }
  } finally {
    exportingSheet.value = false;
  }
};

onMounted(() => {
  loadModels();
  loadProfiles();
});
onUnmounted(stopPolling);
</script>

<style scoped>
.trade-item-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 12px 14px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.trade-item-card:hover { background: rgba(255, 255, 255, 0.07); }
.trade-item-card.active {
  border-color: var(--primary);
  background: rgba(0, 255, 136, 0.06);
}
.trade-name {
  font-size: 0.92rem;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.trade-model { font-size: 0.7rem; color: var(--secondary); }

.refresh-btn {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: var(--text-muted);
  border-radius: 6px;
  padding: 5px 12px;
  cursor: pointer;
  font-size: 0.82rem;
  white-space: nowrap;
}
.refresh-btn:hover { background: rgba(255, 255, 255, 0.1); color: var(--text-main); }
.trade-status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.72rem;
}
.trade-target { color: var(--text-muted); }
.st-done { color: var(--success); }
.st-running { color: var(--warning); }
.st-error { color: var(--danger); }

.danger-btn {
  background: rgba(255, 77, 77, 0.1);
  border: 1px solid rgba(255, 77, 77, 0.35);
  color: var(--danger);
  border-radius: 6px;
  padding: 2px 10px;
  font-size: 0.75rem;
  cursor: pointer;
  flex-shrink: 0;
}
.danger-btn:hover { background: rgba(255, 77, 77, 0.25); }

.ticker-select, .model-select {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: white;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 0.92rem;
  outline: none;
  cursor: pointer;
  min-width: 240px;
}
.ticker-select option, .model-select option {
  background: #161B22;
  color: white;
}
.ticker-select:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.ticker-input {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: white;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 0.92rem;
  outline: none;
  flex: 1;
  min-width: 220px;
}

/* 보유 현황 */
.holding-box {
  background: rgba(255, 204, 0, 0.05);
  border: 1px solid rgba(255, 204, 0, 0.25);
  border-radius: 10px;
  padding: 12px 14px;
}
.holding-head {
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--warning);
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.holding-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 8px 14px;
}
.h-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.h-label { font-size: 0.7rem; color: var(--text-muted); }
.h-value { font-size: 0.88rem; font-weight: 600; }
.val-pos { color: var(--success); }
.val-neg { color: var(--danger); }

.run-btn {
  background: rgba(0, 212, 255, 0.12);
  border: 1px solid var(--secondary);
  color: var(--secondary);
  border-radius: 8px;
  padding: 10px 25px;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
}
.run-btn:hover:not(:disabled) { background: rgba(0, 212, 255, 0.25); }
.run-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.mini-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-top-color: currentColor;
  border-radius: 50%;
  display: inline-block;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.result-box {
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 1.2rem;
  background: rgba(0, 0, 0, 0.2);
}
.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.result-empty {
  color: var(--text-muted);
  padding: 20px 0;
  display: flex;
  align-items: center;
  gap: 10px;
}
.result-error { color: var(--danger); font-size: 0.9rem; }
.raw-text {
  margin-top: 10px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 10px;
  font-size: 0.78rem;
  color: var(--text-muted);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 260px;
  overflow-y: auto;
}

.strategy-summary {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.summary-text {
  margin: 0 0 14px;
  color: var(--text-main);
  font-size: 0.92rem;
  line-height: 1.6;
}

/* 구글 시트 업로드 */
.gsheet-btn {
  background: rgba(15, 157, 88, 0.15);
  border: 1px solid rgba(15, 157, 88, 0.5);
  color: #34A853;
  border-radius: 6px;
  padding: 5px 12px;
  cursor: pointer;
  font-size: 0.82rem;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.gsheet-btn:hover:not(:disabled) { background: rgba(15, 157, 88, 0.3); }
.gsheet-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.gsheet-link {
  font-size: 0.75rem;
  color: #34A853;
  text-decoration: none;
}
.gsheet-link:hover { text-decoration: underline; }

/* 가격대 전략 그래프 */
.chart-btn {
  background: rgba(0, 208, 132, 0.12);
  border: 1px solid var(--success);
  color: var(--success);
  border-radius: 6px;
  padding: 5px 12px;
  cursor: pointer;
  font-size: 0.82rem;
  white-space: nowrap;
}
.chart-btn:hover { background: rgba(0, 208, 132, 0.25); }
.chart-btn.on { background: var(--success); color: #04121a; font-weight: 700; }

.chart-box {
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 12px 10px 10px;
  margin-bottom: 16px;
}
.price-chart {
  width: 100%;
  height: auto;
  max-height: 320px;
  display: block;
}
.chart-legend {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  padding: 8px 6px 0;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  margin-top: 6px;
}
.chart-legend .lg {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.75rem;
  color: var(--text-muted);
}
.chart-legend .lg i {
  width: 12px;
  height: 3px;
  border-radius: 2px;
  display: inline-block;
}
.rr-badge {
  margin-left: auto;
  font-size: 0.75rem;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 6px;
}
.rr-badge.rr-good { background: rgba(0, 208, 132, 0.15); color: var(--success); }
.rr-badge.rr-mid { background: rgba(255, 204, 0, 0.15); color: var(--warning); }
.rr-badge.rr-bad { background: rgba(255, 77, 77, 0.15); color: var(--danger); }
.market-badge {
  font-size: 0.72rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 6px;
  white-space: nowrap;
}
.market-badge.kospi { background: rgba(0, 212, 255, 0.12); color: var(--secondary); }
.market-badge.kosdaq { background: rgba(255, 204, 0, 0.12); color: var(--warning); }
.risk-badge {
  font-size: 0.7rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 6px;
}
.risk-badge.low { background: rgba(0, 208, 132, 0.12); color: var(--success); }
.risk-badge.mid { background: rgba(255, 204, 0, 0.12); color: var(--warning); }
.risk-badge.high { background: rgba(255, 77, 77, 0.12); color: var(--danger); }
.muted { color: var(--text-muted); font-size: 0.82rem; }

.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}
.metric {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.m-label { font-size: 0.72rem; color: var(--text-muted); }
.m-value { font-size: 0.92rem; font-weight: 600; }
.m-value.target { color: var(--success); }
.m-value.stop { color: var(--danger); }
.m-value.entry { color: var(--secondary); }

.cond-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
.cond-box {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 10px;
  padding: 12px 14px;
}
.cond-box h4 {
  margin: 0 0 8px;
  font-size: 0.85rem;
}
.cond-box.buy h4 { color: var(--success); }
.cond-box.sell h4 { color: var(--secondary); }
.cond-box.risk h4 { color: var(--danger); }
.cond-box ul {
  margin: 0;
  padding-left: 18px;
}
.cond-box li {
  font-size: 0.82rem;
  color: var(--text-muted);
  line-height: 1.6;
  margin-bottom: 4px;
}

.reason-box {
  margin-top: 14px;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.02);
  border-left: 3px solid var(--primary);
  border-radius: 6px;
}
.reason-box strong { font-size: 0.82rem; color: var(--primary); }
.reason-box p {
  margin: 6px 0 0;
  font-size: 0.85rem;
  color: var(--text-muted);
  line-height: 1.6;
}

.disclaimer {
  margin: 12px 0 0;
  font-size: 0.75rem;
  color: var(--text-muted);
}
</style>
