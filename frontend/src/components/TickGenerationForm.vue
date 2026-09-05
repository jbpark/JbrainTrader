<template>
  <div class="tick-generation-form glass">
    <h3 style="color: var(--primary); margin-bottom: 1.5rem">📉 기존 데이터 기반 틱 생성 설정</h3>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem">
      <!-- Ticker Selection -->
      <div style="grid-column: span 2">
        <label class="form-label">대상 종목 선택</label>
        <select v-model="form.ticker" class="form-select">
          <option v-for="t in collectedTickers" :key="t.ticker" :value="t.ticker">
            {{ t.name }} ({{ t.ticker }})
          </option>
        </select>
      </div>

      <!-- Interval Selection -->
      <div>
        <label class="form-label">기준 데이터 인터벌</label>
        <select v-model="form.interval" class="form-select" :disabled="!showGeneratorButton">
          <option value="틱">틱 데이터</option>
          <option value="1분">1분봉</option>
          <option value="5분">5분봉</option>
          <option value="일봉">일봉</option>
        </select>
      </div>

      <!-- Generation Mode -->
      <div>
        <label class="form-label">생성 알고리즘</label>
        <select v-model="form.mode" class="form-select">
          <option value="SIMPLE">Simple (O-H-L-C)</option>
          <option value="REALISTIC">Realistic (Random Walk)</option>
          <option value="PATTERNED">Patterned (Trend-based)</option>
        </select>
      </div>

      <!-- Date Selection -->
      <div style="grid-column: span 2">
        <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 8px">
          <label class="form-label" style="margin-bottom: 0">대상 날짜 선택 (최근 수집된 날짜 기준)</label>
          <div v-if="form.selectedDate" style="color: var(--primary); font-weight: bold; font-size: 0.95rem">
            선택됨: {{ form.selectedDate }}
          </div>
        </div>
        <div v-if="form.ticker && form.interval" class="calendar-container glass">
          <DataCalendar 
            ref="calendarRef"
            :ticker="form.ticker" 
            :tickerName="selectedTickerName"
            :interval="form.interval" 
            source="Local"
            :selectedDate="form.selectedDate"
            @date-click="handleDateClick"
          />
          <p class="calendar-hint">
            * <strong>녹색 점</strong>이 표시된 날짜만 선택 가능합니다. <br/>
            * 데이터가 없다면 먼저 <strong>'데이터 수집'</strong> 탭에서 {{ form.ticker }}의 {{ form.interval }} 데이터를 수집해 주세요.
          </p>
        </div>
        <div v-else class="date-chips">
          <span style="color: var(--text-muted); font-size: 0.85rem">
            먼저 종목과 인터벌을 선택해 주세요.
          </span>
        </div>
      </div>

      <!-- Assigned Strategy (Simulation Mode Only) -->
      <div v-if="showSimulationButton" style="grid-column: span 2">
        <label class="form-label">적용 매매 전략</label>
        <div style="padding: 12px; border-radius: 8px; background: rgba(0, 255, 149, 0.1); border: 1px solid var(--primary); color: var(--primary); font-weight: bold; font-size: 1.1rem; display: flex; align-items: center; gap: 10px">
          <span style="font-size: 1.2rem">🔒</span> {{ selectedTickerStrategy }}
        </div>
      </div>

      <!-- Density Setting -->
      <div>
        <label class="form-label">틱 밀도 (초당 생성 틱)</label>
        <input type="number" v-model.number="form.density" min="1" max="10" class="form-input" />
      </div>

      <!-- Preview Info -->
      <div class="preview-info" style="grid-column: span 2">
        <p v-if="form.selectedDate">
          <strong>프리뷰:</strong> {{ form.ticker }}의 {{ form.selectedDate }} ({{ form.interval }}) 데이터를 기반으로 
          약 {{ estimatedTicks.toLocaleString() }}개의 틱을 생성합니다.
        </p>
      </div>
    </div>

    <div style="display: flex; gap: 1rem; margin-top: 2rem">
      <button v-if="showGeneratorButton" class="btn-primary" @click="handleGenerate" :disabled="!isReady || isLoading">
        <span v-if="isLoading">생성 중...</span>
        <span v-else>
          {{ showSimulationButton ? '가상 데이터 생성' : '틱 데이터 생성' }}
          <span v-if="form.selectedDate" style="font-size: 0.8rem; opacity: 0.8; font-weight: normal; margin-left: 5px">({{ form.selectedDate }})</span>
        </span>
      </button>
      <button 
        v-if="showSimulationButton"
        class="btn-primary" 
        style="background: var(--secondary); border: 1px solid var(--secondary)" 
        @click="handleStartSimulation" 
        :disabled="!isReady || isLoading || !isGenerated"
      >
        <span>시뮬레이션 시작</span>
      </button>
      <button class="btn-secondary" @click="$emit('cancel')">취소</button>
    </div>

    <!-- Custom Alert Modal -->
    <StatusAlertModal
      :show="alertState.show"
      :type="alertState.type"
      :title="alertState.title"
      :message="alertState.message"
      :details="alertState.details"
      @close="alertState.show = false"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue';
import { fetchCollectedTickers, fetchCollectedDates, startSimulation } from '../api';
import DataCalendar from './DataCalendar.vue';
import StatusAlertModal from './StatusAlertModal.vue';

const props = defineProps({
  mode: {
    type: String,
    default: 'REALISTIC'
  },
  ticker: String,
  showSimulationButton: {
    type: Boolean,
    default: true
  },
  showGeneratorButton: {
    type: Boolean,
    default: true
  }
});

const emit = defineEmits(['generated', 'cancel', 'start']);

const collectedTickers = ref([]);
const availableDates = ref([]);
const isLoading = ref(false);
const isGenerated = ref(false);
const calendarRef = ref(null);

// Custom Alert Modal State
const alertState = reactive({
  show: false,
  type: 'success',
  title: '',
  message: '',
  details: ''
});

const showAlert = (type, title, message, details = '') => {
  alertState.type = type;
  alertState.title = title;
  alertState.message = message;
  alertState.details = details;
  alertState.show = true;
};

const form = reactive({
  ticker: '',
  interval: props.showGeneratorButton ? '1분' : '틱',
  mode: props.mode,
  selectedDate: '',
  density: 1
});

// localStorage Persistence Keys
const STORAGE_KEY = 'tick_gen_form_state';

const saveState = () => {
  const state = {
    ticker: form.ticker,
    interval: form.interval,
    mode: form.mode,
    density: form.density
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
};

const loadState = () => {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) {
    try {
      const state = JSON.parse(saved);
      if (state.ticker) form.ticker = state.ticker;
      if (state.interval) form.interval = state.interval;
      if (state.mode) form.mode = state.mode;
      if (state.density) form.density = state.density;
    } catch (e) {
      console.error('Failed to load form state:', e);
    }
  }
};

// watch for changes and save
watch([() => form.ticker, () => form.interval, () => form.mode, () => form.density], saveState);

watch(() => props.mode, (newMode) => {
  if (newMode && newMode !== '기존 데이터 기반 생성') {
    form.mode = newMode;
  }
});

watch(() => props.ticker, (newTicker) => {
  if (newTicker) {
    form.ticker = newTicker;
  }
}, { immediate: true });

watch(() => props.showGeneratorButton, (canGen) => {
  if (!canGen) {
    form.interval = '틱';
  } else if (form.interval === '틱') {
    form.interval = '1분';
  }
}, { immediate: true });

const isReady = computed(() => {
  return form.ticker && form.interval && form.selectedDate;
});

const selectedTickerName = computed(() => {
  const item = collectedTickers.value.find(t => t.ticker === form.ticker);
  return item ? item.name : form.ticker.split('.')[0];
});

const selectedTickerStrategy = computed(() => {
  const info = collectedTickers.value.find(t => t.ticker === form.ticker);
  return info?.buy_rule || '기본 전략 (DEFAULT)';
});

const estimatedTicks = computed(() => {
  if (form.interval === '틱') return 0;
  // Simple estimation: 1m (6.5h = 390m), 5m (78), Daily (1)
  const multipliers = { '1분': 390, '5분': 78, '일봉': 1 };
  const baseCount = multipliers[form.interval] || 1;
  const ticksPerCandle = form.interval === '1분' ? 60 : (form.interval === '5분' ? 300 : 23400); // 23400 is rough 6.5h
  return baseCount * form.density; 
});

const loadTickers = async () => {
  collectedTickers.value = await fetchCollectedTickers();
  
  // Load saved state after tickers are fetched
  loadState();

  // [IMPORTANT] Favor props.ticker if provided (e.g., from 'Start' button)
  if (props.ticker) {
    form.ticker = props.ticker;
  }

  // If no saved ticker or saved ticker not in list, fallback to first
  if (collectedTickers.value.length > 0) {
    // Normalize comparison to find even with .KS mismatch
    const tickerExists = collectedTickers.value.some(t => {
      const t1 = t.ticker.split('.')[0];
      const t2 = form.ticker.split('.')[0];
      return t1 === t2;
    });

    if (!form.ticker || !tickerExists) {
      form.ticker = collectedTickers.value[0].ticker;
    } else if (tickerExists && props.ticker) {
      // If it exists but format is different (000660 vs 000660.KS), use the list version
      const found = collectedTickers.value.find(t => t.ticker.split('.')[0] === form.ticker.split('.')[0]);
      if (found) form.ticker = found.ticker;
    }
  }
  
  // Ensure interval is correct based on generator button after loading state
  if (!props.showGeneratorButton) {
    form.interval = '틱';
  }
};

const loadDates = async () => {
  if (!form.ticker || !form.interval) return;
  // availableDates is used for estimation or background info
  const dates = await fetchCollectedDates(form.ticker, form.interval);
  availableDates.value = dates;
  if (availableDates.value.length > 0 && !form.selectedDate) {
    const first = availableDates.value[0];
    form.selectedDate = typeof first === 'object' ? (first.date || first.date_str) : first;
  }
};

watch(() => form.ticker, loadDates);
watch(() => form.interval, loadDates);

onMounted(loadTickers);

const handleDateClick = ({ date, status }) => {
  form.selectedDate = date;
  // 클릭한 날짜가 이미 틱이 생성된 날짜라면 '시뮬레이션 시작' 버튼 활성화
  isGenerated.value = (status === 'TICK_GENERATED');
};

const handleGenerate = async () => {
  isLoading.value = true;
  isGenerated.value = false;
  try {
    const response = await fetch('http://127.0.0.1:5000/simulation/reconstruct', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form)
    });
    const result = await response.json();
    if (result.status === 'SUCCESS') {
      showAlert('success', '틱 데이터 생성 성공', '틱 데이터 생성이 완료되었습니다.', `${result.count}개의 틱 데이터가 저장되었습니다.`);
      isGenerated.value = true;
      if (calendarRef.value) calendarRef.value.refresh();
      // emit('generated', { ticker: result.ticker, selectedDate: form.selectedDate });
    } else {
      showAlert('error', '틱 데이터 생성 실패', result.message);
    }
  } catch (e) {
    console.error(e);
    showAlert('error', '서버 오류', '서버 연결 중 오류가 발생했습니다.');
  } finally {
    isLoading.value = false;
  }
};

const handleStartSimulation = async () => {
  if (!isGenerated.value) return;
  
  // 1. 해당 종목에 설정된 전략 찾기 (DB 값)
  const currentTickerInfo = collectedTickers.value.find(t => t.ticker === form.ticker);
  let strategy = currentTickerInfo?.buy_rule;

  // 2. DB에 설정된 전략이 없거나 DEFAULT인 경우, 마지막으로 선택했던 전략 사용 시도
  if (!strategy || strategy === 'DEFAULT') {
    const savedStrategies = JSON.parse(localStorage.getItem('lastSelectedStrategies')) || ['DEFAULT'];
    strategy = savedStrategies[0] || 'DEFAULT';
  }
  
  const config = {
    mode: 'REPLAY',
    date: form.selectedDate,
    strategy: strategy,
    // 기본 설정값 (필요시 SimulationSettings와 동기화 가능)
    slippage_enabled: JSON.parse(localStorage.getItem('slippage_enabled')) || false,
    slippage_rate_pct: JSON.parse(localStorage.getItem('slippage_rate_pct')) || 0.05
  };

  const res = await startSimulation(form.ticker, config);
  if (res && res.status === 'STARTED') {
    // 시뮬레이션이 시작되면 'DataPanel'에서 전용 화면을 보여주도록 emit
    emit('start', { ticker: form.ticker, config });
  } else {
    showAlert('error', '시뮬레이션 시작 실패', '시뮬레이션 시작에 실패했습니다.');
  }
};
</script>

<style scoped>
.tick-generation-form {
  max-width: 800px;
  margin: 0 auto;
  padding: 3rem;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.form-label {
  font-size: 0.85rem;
  color: var(--text-muted);
  display: block;
  margin-bottom: 8px;
}

.form-select, .form-input {
  width: 100%;
  padding: 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--text-main);
  outline: none;
  transition: border-color 0.2s;
}

.form-select:focus, .form-input:focus {
  border-color: var(--primary);
}

.calendar-container {
  background: rgba(0, 0, 0, 0.4);
  padding: 10px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.date-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px;
  background: rgba(0,0,0,0.2);
  border-radius: 12px;
  min-height: 50px;
}

.chip {
  padding: 6px 12px;
  border-radius: 20px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.1);
  color: var(--text-muted);
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.2s;
}

.chip:hover {
  background: rgba(255,255,255,0.1);
}

.chip.active {
  background: var(--primary);
  color: white;
  border-color: var(--primary);
}

.preview-info {
  background: rgba(var(--primary-rgb, 0, 255, 149), 0.1);
  padding: 15px;
  border-radius: 12px;
  border: 1px dashed var(--primary);
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

.btn-primary {
  flex: 2;
  padding: 14px;
  border-radius: 10px;
  font-weight: bold;
  background: var(--primary);
  color: white;
  border: none;
  cursor: pointer;
  transition: transform 0.1s, opacity 0.2s;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary:active:not(:disabled) {
  transform: scale(0.98);
}

.btn-secondary {
  flex: 1;
  padding: 14px;
  border-radius: 10px;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--text-muted);
  cursor: pointer;
}
</style>
