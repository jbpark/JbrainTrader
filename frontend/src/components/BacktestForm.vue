<template>
  <div class="backtest-form glass">
    <h3 style="color: var(--primary); margin-bottom: 1.5rem">🧪 백테스트 실행 설정</h3>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem">
      <!-- Ticker Selection -->
      <div style="grid-column: span 2">
        <label class="form-label">대상 종목 선택</label>
        <select v-model="form.ticker" class="form-select">
          <option v-for="t in collectedTickers" :key="t.ticker" :value="t.ticker">
            {{ t.name }} ({{ t.ticker.split('.')[0] }})
          </option>
        </select>
      </div>

      <!-- Date Selection -->
      <div style="grid-column: span 2">
        <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 8px">
          <label class="form-label" style="margin-bottom: 0">틱 데이터 선택 (파란색 점: 생성 완료)</label>
          <div v-if="form.selectedDate" style="color: var(--primary); font-weight: bold; font-size: 0.95rem">
            선택됨: {{ form.selectedDate }}
          </div>
        </div>
        <div v-if="form.ticker" class="calendar-container glass">
          <DataCalendar 
            ref="calendarRef"
            :ticker="form.ticker" 
            :tickerName="selectedTickerName"
            :interval="'1분'" 
            source="Local"
            :selectedDate="form.selectedDate"
            @date-click="handleDateClick"
          />
          <p class="calendar-hint">
            * <strong>파란색 점</strong>이 표시된 날짜(틱 생성 완료)를 선택해 주세요. <br/>
            * 틱 데이터가 없다면 먼저 <strong>'시세 데이터 > 가상 데이터'</strong>에서 틱을 생성해야 합니다.
          </p>
        </div>
        <div v-else class="date-chips">
          <span style="color: var(--text-muted); font-size: 0.85rem">
            먼저 종목을 선택해 주세요.
          </span>
        </div>
      </div>

      <!-- Strategy Selection -->
      <div style="grid-column: span 2">
        <label class="form-label">매매 전략 선택 (복수 선택 가능)</label>
        <div class="strategy-list glass">
          <label v-for="s in strategyList" :key="s.name" class="strat-checkbox">
            <input type="checkbox" :value="s.name" v-model="form.selectedStrategies" style="accent-color: var(--primary)" />
            <span>{{ s.name }}</span>
          </label>
        </div>
      </div>
      
      <!-- Additional Config (Slippage etc) -->
      <div style="grid-column: span 2; display: flex; align-items: center; gap: 2rem; padding: 15px; border-radius: 12px; background: rgba(255,107,107,0.05); border: 1px solid rgba(255,107,107,0.1)">
        <div style="display: flex; align-items: center; gap: 10px">
          <label style="font-size: 0.9rem; font-weight: bold; color: #ff6b6b; cursor: pointer">
            <input type="checkbox" v-model="form.slippage_enabled" style="width: 16px; height: 16px; accent-color: #ff6b6b" /> 슬리피지 적용
          </label>
        </div>
        <div v-if="form.slippage_enabled" style="display: flex; align-items: center; gap: 10px">
          <label style="font-size: 0.85rem; color: var(--text-muted)">슬리피지율 (%):</label>
          <input type="number" v-model.number="form.slippage_rate_pct" step="0.01" style="width: 80px; padding: 6px 10px; border-radius: 6px; background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.1); color: var(--text-main)" />
        </div>
      </div>
    </div>

    <div style="display: flex; gap: 1rem; margin-top: 2rem">
      <button class="btn-primary" @click="handleBacktest" :disabled="!isReady">
        백테스트 실행 <span v-if="form.selectedDate" style="font-size: 0.8rem; opacity: 0.8; font-weight: normal; margin-left: 5px">({{ form.selectedDate }})</span>
      </button>
      <button class="btn-secondary" @click="$emit('cancel')">취소</button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue';
import { fetchCollectedTickers, fetchStrategies } from '../api';
import DataCalendar from './DataCalendar.vue';

const emit = defineEmits(['backtest', 'cancel']);

const collectedTickers = ref([]);
const strategyList = ref([{ name: 'DEFAULT' }]);
const calendarRef = ref(null);
const isGeneratedDate = ref(false);

const form = reactive({
  ticker: '',
  selectedDate: '',
  selectedStrategies: JSON.parse(localStorage.getItem('backtestSelectedStrategies')) || ['DEFAULT'],
  slippage_enabled: JSON.parse(localStorage.getItem('slippage_enabled')) || false,
  slippage_rate_pct: JSON.parse(localStorage.getItem('slippage_rate_pct')) || 0.05
});

const selectedTickerName = computed(() => {
    const item = collectedTickers.value.find(t => t.ticker === form.ticker);
    return item ? item.name : form.ticker.split('.')[0];
});

const isReady = computed(() => {
  return form.ticker && form.selectedDate && form.selectedStrategies.length > 0 && isGeneratedDate.value;
});

const loadTickers = async () => {
  collectedTickers.value = await fetchCollectedTickers();
  if (collectedTickers.value.length > 0) {
    form.ticker = localStorage.getItem('lastSelectedTicker') || collectedTickers.value[0].ticker;
  }
};

const loadStrategies = async () => {
    const strats = await fetchStrategies();
    if (strats && strats.length > 0) {
        strategyList.value = strats;
        if (!strategyList.value.find(s => s.name === 'DEFAULT')) {
            strategyList.value.unshift({ name: 'DEFAULT' });
        }
    }
};

onMounted(() => {
    loadTickers();
    loadStrategies();
});

const handleDateClick = ({ date, status }) => {
  form.selectedDate = date;
  isGeneratedDate.value = (status === 'TICK_GENERATED');
};

const handleBacktest = () => {
  if (!isReady.value) return;
  
  const config = {
    mode: 'REPLAY',
    date: form.selectedDate,
    strategies: form.selectedStrategies,
    slippage_enabled: form.slippage_enabled,
    slippage_rate_pct: form.slippage_rate_pct
  };
  
  emit('backtest', { ticker: form.ticker, config });
};

// Save preferences
watch(() => form.ticker, (newVal) => localStorage.setItem('lastSelectedTicker', newVal));
watch(() => form.selectedStrategies, (newVal) => {
    localStorage.setItem('backtestSelectedStrategies', JSON.stringify(newVal));
}, { deep: true });
watch(() => form.slippage_enabled, (newVal) => localStorage.setItem('slippage_enabled', JSON.stringify(newVal)));
watch(() => form.slippage_rate_pct, (newVal) => localStorage.setItem('slippage_rate_pct', JSON.stringify(newVal)));

</script>

<style scoped>
.backtest-form {
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

.form-select {
  width: 100%;
  padding: 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--text-main);
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
  transition: background 0.2s;
}

.strat-checkbox:hover {
  background: rgba(255, 255, 255, 0.08);
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
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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
