<template>
  <div class="dual-backtest-form glass">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem">
      <h3 style="color: var(--primary); margin: 0">📊 듀얼 ETF 스프레드 백테스트</h3>
      <button class="btn-close" @click="$emit('close')">✕</button>
    </div>

    <div class="settings-grid">
      <!-- Ticker Settings -->
      <div class="setting-item">
        <label class="form-label">기준 ETF (ETF1)</label>
        <select v-model="ticker1" class="form-select">
          <option v-for="t in tickerList" :key="t.ticker" :value="t.ticker">
            {{ t.name }} ({{ t.ticker.split('.')[0] }})
          </option>
        </select>
      </div>
      <div class="setting-item">
        <label class="form-label">대응 ETF (ETF2)</label>
        <select v-model="ticker2" class="form-select">
          <option v-for="t in tickerList" :key="t.ticker" :value="t.ticker">
            {{ t.name }} ({{ t.ticker.split('.')[0] }})
          </option>
        </select>
      </div>

      <!-- Strategy Parameters -->
      <div class="setting-item">
        <label class="form-label">Z-Score 임계값 (Threshold)</label>
        <div style="display: flex; align-items: center; gap: 10px">
          <input type="range" v-model.number="threshold" min="0.5" max="3.0" step="0.1" style="flex: 1">
          <span style="width: 40px; font-weight: bold; color: var(--primary)">{{ threshold }}</span>
        </div>
      </div>
      <div class="setting-item">
        <label class="form-label">매수금액 ({{ currencyUnit }})</label>
        <input type="text" v-model="startCashDisplay" @blur="parseStartCash" class="form-input" :placeholder="isUS ? '50,000' : '1,000,000'" />
      </div>
      <div style="grid-column: span 2">
        <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 8px">
          <label class="form-label" style="margin-bottom: 0">백테스트 날짜 선택 (파란색 점: 틱 데이터 존재)</label>
          <div v-if="date" style="color: var(--primary); font-weight: bold; font-size: 0.95rem">
            선택됨: {{ date }}
          </div>
        </div>
        <div v-if="ticker1" class="calendar-container glass">
          <DataCalendar 
            ref="calendarRef"
            :ticker="ticker1" 
            :tickerNames="[ticker1Name, ticker2Name]"
            :interval="'1분'" 
            source="Local"
            :selectedDate="date"
            @date-click="handleDateClick"
          />
          <p class="calendar-hint">
            * <strong>파란색 점</strong>이 표시된 날짜(틱 데이터 존재)를 선택해 주세요. <br/>
            * <strong>{{ ticker1Name }}</strong>과 <strong>{{ ticker2Name }}</strong>의 데이터 현황을 확인해 주세요.
          </p>
        </div>
      </div>

      <!-- Strategy Selection (라디오 버튼 - 단일 선택) -->
      <div style="grid-column: span 2">
        <label class="form-label">매매 전략 선택 (듀얼 전략 전용)</label>
        <div class="strategy-list glass">
          <label v-for="s in dualStrategyList" :key="s.name" class="strat-checkbox" :class="{ selected: selectedStrategy === s.name }">
            <input type="radio" :value="s.name" v-model="selectedStrategy" style="accent-color: var(--primary)" />
            <span>{{ s.name }}</span>
          </label>
        </div>
      </div>
    </div>

    <div style="margin-top: 2rem">
      <button @click="runBacktest" class="btn-primary" :disabled="loading || !date || !isGeneratedDate">
        <span v-if="loading">🚀 전략 분석 중...</span>
        <span v-else>백테스트 실행 <span v-if="date" style="font-size: 0.8rem; opacity: 0.8; font-weight: normal; margin-left: 5px">({{ date }})</span></span>
      </button>
    </div>

    <!-- Results Section -->
    <div v-if="result" class="results-container" style="margin-top: 2rem">
      <div class="metrics-grid">
        <div class="metric-card glass">
          <div class="label">시작 매수금액</div>
          <div class="value">{{ formatAmount(result.metrics.start_cash) }}</div>
        </div>
        <div class="metric-card glass">
          <div class="label">최종 매수금액</div>
          <div class="value">{{ formatAmount(result.metrics.final_value) }}</div>
        </div>
        <div class="metric-card glass">
          <div class="label">수익금(Net)</div>
          <div class="value" :style="{ color: result.metrics.pnl >= 0 ? '#ff6b6b' : '#4dabf7' }">
            {{ result.metrics.pnl > 0 ? '+' : '' }}{{ formatAmount(result.metrics.pnl) }}
          </div>
        </div>
        <div class="metric-card glass">
          <div class="label">총 수익률</div>
          <div class="value" :style="{ color: result.metrics.pnl_rate >= 0 ? '#ff6b6b' : '#4dabf7' }">
            {{ result.metrics.pnl_rate }}%
          </div>
        </div>
        
        <div class="metric-card glass">
          <div class="label">승률</div>
          <div class="value">{{ result.metrics.win_rate }}%</div>
        </div>
        <div class="metric-card glass">
          <div class="label">익절 횟수</div>
          <div class="value" style="color: #ff6b6b">{{ result.metrics.win_count }}회</div>
        </div>
        <div class="metric-card glass">
          <div class="label">최대 낙폭 (MDD)</div>
          <div class="value" style="color: #4dabf7">{{ result.metrics.max_dd }}%</div>
        </div>
        <div class="metric-card glass">
          <div class="label">총 매매 횟수</div>
          <div class="value">{{ result.metrics.trade_count }}회</div>
        </div>
      </div>

      <div class="chart-box glass">
        <img :src="result.chart" class="backtest-chart" />
      </div>

      <div class="logs-box glass">
        <h4 style="margin: 0 0 1rem 0; color: var(--text-muted)">📝 전략 실행 로그</h4>
        <div class="log-entries">
          <div v-for="(log, idx) in result.logs" :key="idx" class="log-entry">
            <span class="log-bullet"></span> {{ log }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { fetchCollectedTickers, fetchStrategies } from '../api';
import DataCalendar from './DataCalendar.vue';

const props = defineProps({
  tickers: Object
});

const emit = defineEmits(['close']);

const allCollectedTickers = ref([]);
const strategyList = ref([]);
const selectedStrategy = ref(localStorage.getItem('dual_backtest_strategy') || 'dual/DUAL_ETFS_SPREAD');
const isGeneratedDate = ref(false);
const calendarRef = ref(null);

const tickerList = computed(() => {
  if (allCollectedTickers.value.length > 0) {
    return allCollectedTickers.value;
  }
  // Fallback to props.tickers if fetch hasn't finished
  return Object.keys(props.tickers || {}).map(t => ({
    ticker: t,
    name: props.tickers[t]?.name || t
  })).sort((a,b) => a.name.localeCompare(b.name));
});

const dualStrategyList = computed(() => {
  // 듀얼 전략만 필터링 (type이 dual이거나 이름에 DUAL이 포함된 경우)
  return strategyList.value.filter(s => s.type === 'dual' || s.name.toUpperCase().includes('DUAL'));
});

const ticker1 = ref(localStorage.getItem('dual_backtest_ticker1') || '069500');
const ticker2 = ref(localStorage.getItem('dual_backtest_ticker2') || '114800');

const ticker1Name = computed(() => {
  const item = tickerList.value.find(t => t.ticker === ticker1.value);
  return item ? item.name : ticker1.value.split('.')[0];
});

const ticker2Name = computed(() => {
  const item = tickerList.value.find(t => t.ticker === ticker2.value);
  return item ? item.name : ticker2.value.split('.')[0];
});

const isUS = computed(() => {
  if (!ticker1.value) return false;
  return !/^\d+/.test(ticker1.value.split('.')[0]);
});

const currencyUnit = computed(() => isUS.value ? 'USD' : '원');

const threshold = ref(Number(localStorage.getItem('dual_backtest_threshold')) || 1.5);
const startCash = ref(Number(localStorage.getItem('dual_backtest_start_cash')) || 1000000);
const startCashDisplay = ref(startCash.value.toLocaleString());
const date = ref(localStorage.getItem('dual_backtest_date') || '');
const loading = ref(false);
const result = ref(null);

const parseStartCash = () => {
  const num = Number(startCashDisplay.value.replace(/[^\d]/g, ''));
  if (num > 0) {
    startCash.value = num;
    startCashDisplay.value = num.toLocaleString();
  }
};

onMounted(async () => {
  // 1. 초기 날짜 설정
  if (!date.value) {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    date.value = yesterday.toISOString().split('T')[0];
  }

  // 2. 종목 목록 가져오기 및 이름 보완
  const fetchedTickers = await fetchCollectedTickers();
  if (fetchedTickers && fetchedTickers.length > 0) {
    let localMap = {};
    try {
      const nameMapRaw = localStorage.getItem('tickerNameMap');
      if (nameMapRaw) Object.assign(localMap, JSON.parse(nameMapRaw));
      
      const savedTickers = localStorage.getItem('collectorSelectedTickers');
      if (savedTickers) {
        JSON.parse(savedTickers).forEach(item => {
          if (item.ticker && item.name) {
            if (!localMap[item.ticker]) localMap[item.ticker] = item.name;
            const norm = item.ticker.split('.')[0];
            if (!localMap[norm]) localMap[norm] = item.name;
          }
        });
      }
    } catch (e) {}

    allCollectedTickers.value = fetchedTickers.map(t => {
      const isMissing = !t.name || /^\d+(\.\w+)?$/.test(t.name) || t.name === t.ticker;
      const resolvedName = isMissing
        ? (localMap[t.ticker] || localMap[t.ticker.split('.')[0]] || t.name || t.ticker)
        : t.name;
      return { ...t, name: resolvedName };
    });
  }

  // 3. 전략 목록 가져오기
  const fetchedStrats = await fetchStrategies();
  if (fetchedStrats) {
    strategyList.value = fetchedStrats;
    // 선택된 전략이 목록에 없으면 첫 번째 듀얼 전략 자동 선택
    const dualStrats = fetchedStrats.filter(s => s.type === 'dual' || s.name.toUpperCase().includes('DUAL'));
    if (dualStrats.length > 0 && !dualStrats.find(s => s.name === selectedStrategy.value)) {
      selectedStrategy.value = dualStrats[0].name;
    }
  }

  // 4. 기본 티커 정규화 확인
  const currentTickers = tickerList.value.map(t => t.ticker);
  if (!currentTickers.includes(ticker1.value)) {
    const ks = ticker1.value + '.KS';
    if (currentTickers.includes(ks)) ticker1.value = ks;
  }
  if (!currentTickers.includes(ticker2.value)) {
    const ks = ticker2.value + '.KS';
    if (currentTickers.includes(ks)) ticker2.value = ks;
  }

  // 5. 초기 진입 시 날짜가 이미 선택되어 있다면 데이터 가능 여부 임시 허용 (사용자 편의성)
  if (date.value) isGeneratedDate.value = true;
});

const handleDateClick = ({ date: clickedDate, status }) => {
  date.value = clickedDate;
  // TICK_GENERATED(파란 점) 혹은 COLLECTED(초록 칸) 이면 실행 가능
  isGeneratedDate.value = (status === 'TICK_GENERATED' || status === 'COLLECTED' || status === 'EXIST');
};

// Watch for changes to save to localStorage
watch(ticker1, (val) => localStorage.setItem('dual_backtest_ticker1', val));
watch(ticker2, (val) => localStorage.setItem('dual_backtest_ticker2', val));
watch(threshold, (val) => localStorage.setItem('dual_backtest_threshold', val.toString()));
watch(startCash, (val) => {
  localStorage.setItem('dual_backtest_start_cash', val.toString());
  startCashDisplay.value = Number(val).toLocaleString();
});
watch(date, (val) => localStorage.setItem('dual_backtest_date', val));
watch(selectedStrategy, async (newVal, oldVal) => {
  localStorage.setItem('dual_backtest_strategy', newVal);
  
  // 전략이 바뀌면 파일에서 기본 파라미터 가져오기
  if (newVal && newVal !== oldVal) {
    try {
      console.log(`[StrategyChange] Strategy changed: '${oldVal}' -> '${newVal}'`);
      const res = await fetch(`http://127.0.0.1:5000/strategies/params?name=${encodeURIComponent(newVal)}`);
      const data = await res.json();
      
      if (data.status === 'SUCCESS' && data.params) {
        if (data.params.threshold !== undefined) {
          threshold.value = data.params.threshold;
        }
        if (data.params.start_cash !== undefined) {
          startCash.value = data.params.start_cash;
          startCashDisplay.value = data.params.start_cash.toLocaleString();
        }
        console.log(`[StrategyParams] Loaded defaults for ${newVal}:`, data.params);
      }
    } catch (e) {
      console.error('Failed to fetch strategy params:', e);
    }
  }
});


const formatAmount = (val) => {
  if (val === undefined || val === null) return '0';
  if (isUS.value) {
    return '$' + Number(val).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  return Math.round(val).toLocaleString() + '원';
};

const runBacktest = async () => {
  loading.value = true;
  result.value = null;
  try {
    const response = await fetch('http://127.0.0.1:5000/backtest/spread', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ticker1: ticker1.value,
        ticker2: ticker2.value,
        threshold: threshold.value,
        date: date.value,
        start_cash: startCash.value,
        strategy: selectedStrategy.value || 'dual/DUAL_ETFS_SPREAD'
      })
    });
    const data = await response.json();
    if (data.status === 'SUCCESS') {
      result.value = data;
    } else {
      alert(data.message || '백테스트 중 오류가 발생했습니다.');
    }
  } catch (error) {
    console.error(error);
    alert('서버 연결 오류가 발생했습니다.');
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.dual-backtest-form {
  max-width: 800px;
  margin: 0 auto;
  padding: 3rem;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 20px;
}

.settings-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
}

.setting-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-label {
  font-size: 0.85rem;
  color: var(--text-muted);
}

.form-select, .form-input {
  width: 100%;
  padding: 12px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: white;
  outline: none;
}

.calendar-container {
  background: rgba(0, 0, 0, 0.4);
  padding: 10px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.calendar-hint {
  margin-top: 10px;
  font-size: 0.8rem;
  color: #888;
  line-height: 1.4;
}

.calendar-hint strong {
  color: #aaa;
}

.strategy-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.8rem;
  padding: 15px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.strat-checkbox {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 6px 12px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
  transition: all 0.2s;
  border: 1px solid transparent;
}

.strat-checkbox:hover {
  background: rgba(255, 255, 255, 0.08);
}

.strat-checkbox.selected {
  background: rgba(0, 255, 149, 0.1);
  border-color: var(--primary);
  color: var(--primary);
}

.btn-primary {
  width: 100%;
  padding: 14px;
  background: var(--primary);
  color: black;
  font-weight: bold;
  border: none;
  border-radius: 10px;
  cursor: pointer;
}

.btn-close {
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 1.5rem;
  cursor: pointer;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.metric-card {
  padding: 1rem;
  text-align: center;
  background: rgba(255, 255, 255, 0.03);
}

.metric-card .label {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.metric-card .value {
  font-size: 1.2rem;
  font-weight: bold;
}

.chart-box {
  background: rgba(0, 0, 0, 0.2);
  padding: 1rem;
  border-radius: 12px;
  margin-bottom: 1.5rem;
}

.backtest-chart {
  width: 100%;
  border-radius: 8px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.5);
}

.logs-box {
  background: rgba(0, 0, 0, 0.4);
  padding: 1.5rem;
  border-radius: 12px;
  height: 300px;
  overflow-y: auto;
}

.log-entries {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.log-entry {
  font-family: 'Fira Code', monospace;
  font-size: 0.85rem;
  color: #adb5bd;
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.log-bullet {
  width: 6px;
  height: 6px;
  background: var(--primary);
  border-radius: 50%;
  margin-top: 6px;
  flex-shrink: 0;
}
</style>
