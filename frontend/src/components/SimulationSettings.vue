<template>
  <div class="simulation-settings" :class="{ 'in-pane': !isModal }">
    <h3 v-if="!isModal" style="color: var(--primary); margin-bottom: 1.5rem">📊 가상 시뮬레이션 설정</h3>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem">
      <div style="grid-column: span 2">
        <label style="font-size: 0.85rem; color: var(--text-muted); display: block; margin-bottom: 5px">종목코드</label>
        <select v-if="tickerList.length > 0" v-model="ticker" style="width: 100%; padding: 10px; border-radius: 8px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); color: var(--text-main)">
          <option v-for="t in tickerList" :key="t" :value="t">{{ t.split('.')[0] }} - {{ (tickers[t]?.name) || t }}</option>
        </select>
        <input v-else type="text" v-model="ticker" placeholder="종목코드 입력" style="width: 100%; padding: 10px; border-radius: 8px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); color: var(--text-main)" />
      </div>
      <div>
        <label style="font-size: 0.85rem; color: var(--text-muted); display: block; margin-bottom: 5px">시작 가격 (Start Price)</label>
        <input type="number" v-model.number="config.start_price" style="width: 100%; padding: 10px; border-radius: 8px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); color: var(--text-main)" />
      </div>
      <div>
        <label style="font-size: 0.85rem; color: var(--text-muted); display: block; margin-bottom: 5px">시뮬레이션 시간 (초)</label>
        <input type="number" v-model.number="config.duration" style="width: 100%; padding: 10px; border-radius: 8px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); color: var(--text-main)" />
      </div>
      <div>
        <label style="font-size: 0.85rem; color: var(--text-muted); display: block; margin-bottom: 5px">랜덤 시드 (Random Seed)</label>
        <input type="number" v-model.number="config.seed" placeholder="기본 랜덤" style="width: 100%; padding: 10px; border-radius: 8px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); color: var(--text-main)" />
      </div>
      <div>
        <label style="font-size: 0.85rem; color: var(--text-muted); display: block; margin-bottom: 5px">초기 시나리오</label>
        <select v-model="config.scenario" style="width: 100%; padding: 10px; border-radius: 8px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); color: var(--text-main)">
          <option value="SIDEWAYS">SIDEWAYS (횡보)</option>
          <option value="UPTREND">UPTREND (상승)</option>
          <option value="DOWNTREND">DOWNTREND (하락)</option>
          <option value="VOLATILE">VOLATILE (변동성)</option>
          <option value="FLASH_CRASH">FLASH_CRASH (폭락)</option>
        </select>
      </div>
      <div style="grid-column: span 2">
        <label style="font-size: 0.85rem; color: var(--text-muted); display: block; margin-bottom: 5px">
          {{ showAnalyzeButton ? '매매 전략 (Strategies - 분석 시 복수 선택 가능)' : '적용 매매 전략' }}
        </label>
        <div v-if="showAnalyzeButton" style="display: flex; flex-wrap: wrap; gap: 0.8rem; padding: 12px; border-radius: 8px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1)">
          <label v-for="s in strategyList" :key="s.name" style="display: flex; align-items: center; gap: 8px; cursor: pointer; padding: 4px 8px; border-radius: 4px; transition: background 0.2s" class="strat-checkbox">
            <input type="checkbox" :value="s.name" v-model="selectedStrategies" style="accent-color: var(--primary)" />
            <span style="font-size: 0.9rem; color: var(--text-main)">{{ s.name }}</span>
          </label>
        </div>
        <div v-else style="padding: 12px; border-radius: 8px; background: rgba(0, 255, 149, 0.1); border: 1px solid var(--primary); color: var(--primary); font-weight: bold; font-size: 1.1rem; display: flex; align-items: center; gap: 10px">
          <span style="font-size: 1.2rem">🔒</span> {{ selectedStrategies[0] || '기본 전략 (DEFAULT)' }}
        </div>
      </div>
      <div style="grid-column: span 2; display: flex; align-items: center; gap: 2rem; padding: 15px; border-radius: 12px; background: rgba(255,107,107,0.05); border: 1px solid rgba(255,107,107,0.1)">
        <div style="display: flex; align-items: center; gap: 10px">
          <label style="font-size: 0.9rem; font-weight: bold; color: #ff6b6b; cursor: pointer">
            <input type="checkbox" v-model="config.slippage_enabled" style="width: 16px; height: 16px; accent-color: #ff6b6b" /> 슬리피지 적용 (Slippage)
          </label>
        </div>
        <div v-if="config.slippage_enabled" style="display: flex; align-items: center; gap: 10px">
          <label style="font-size: 0.85rem; color: var(--text-muted)">슬리피지율 (%):</label>
          <input type="number" v-model.number="config.slippage_rate_pct" step="0.01" style="width: 80px; padding: 6px 10px; border-radius: 6px; background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.1); color: var(--text-main)" />
          <span style="font-size: 0.75rem; color: var(--text-muted)">({{ (config.slippage_rate_pct / 100).toFixed(4) }})</span>
        </div>
      </div>
    </div>

    <div style="display: flex; gap: 10px; margin-top: 2rem">
      <button v-if="showAnalyzeButton" class="primary" @click="emit('analyze', { ticker: ticker, config: { ...config, strategies: selectedStrategies } })" style="flex: 1; padding: 12px; border-radius: 8px; font-weight: bold; background: var(--secondary); color: white; border: none; cursor: pointer; transition: all 0.2s" :disabled="selectedStrategies.length === 0">{{ showSimulationButton ? '분석 (Analyze)' : '백테스트 실행' }}</button>
      <button v-if="showSimulationButton" class="primary" @click="emit('start', { ticker: ticker, config: { ...config, strategy: selectedStrategies[0] || null } })" style="flex: 2; padding: 12px; border-radius: 8px; font-weight: bold; background: var(--primary); color: white; border: none; cursor: pointer; transition: all 0.2s">시뮬레이션 시작 ({{ selectedStrategies[0] || '전략없음' }})</button>
      <button v-if="isModal" @click="emit('close')" style="flex: 1; padding: 12px; border-radius: 8px; background: rgba(255,255,255,0.1); color: var(--text-muted); border: none; cursor: pointer">닫기</button>
      <button v-else @click="emit('close')" style="flex: 1; background: transparent; border: 1px solid rgba(255,255,255,0.1); padding: 12px">취소</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { fetchStrategies } from '../api';

const props = defineProps({
  initialTicker: String,
  tickers: {
    type: Object,
    default: () => ({})
  },
  isModal: {
    type: Boolean,
    default: false
  },
  showSimulationButton: {
    type: Boolean,
    default: true
  },
  showAnalyzeButton: {
    type: Boolean,
    default: true
  }
});

const emit = defineEmits(['start', 'analyze', 'close']);

const tickerList = computed(() => Object.keys(props.tickers));
const strategyList = ref([{ name: 'DEFAULT' }]);

const ticker = ref(props.initialTicker || localStorage.getItem('lastSelectedTicker') || '');
const selectedStrategies = ref(JSON.parse(localStorage.getItem('lastSelectedStrategies')) || ['DEFAULT']); // Load from LS
const config = ref({
  start_price: 100000,
  duration: 3600,
  seed: 42,
  scenario: 'SIDEWAYS',
  slippage_enabled: localStorage.getItem('slippage_enabled') === null ? true : JSON.parse(localStorage.getItem('slippage_enabled')),
  slippage_rate_pct: localStorage.getItem('slippage_rate_pct') === null ? 0.05 : JSON.parse(localStorage.getItem('slippage_rate_pct')),
});

watch(ticker, (newVal) => {
  if (newVal) {
    localStorage.setItem('lastSelectedTicker', newVal);
    
    // Auto-select the strategy currently set for the ticker
    const tickerInfo = props.tickers[newVal];
    if (tickerInfo && tickerInfo.buy_rule) {
      selectedStrategies.value = [tickerInfo.buy_rule];
    }
  }
});

watch(() => props.tickers, (newTickers) => {
  if (ticker.value && newTickers[ticker.value]) {
    const buyRule = newTickers[ticker.value].buy_rule;
    if (buyRule) {
      selectedStrategies.value = [buyRule];
    }
  }
}, { deep: true, immediate: true });

watch(() => props.initialTicker, (newVal) => {
  if (newVal) {
    ticker.value = newVal;
  }
});

watch(selectedStrategies, (newVal) => {
  localStorage.setItem('lastSelectedStrategies', JSON.stringify(newVal));
}, { deep: true });

watch(() => config.value.slippage_enabled, (newVal) => {
  localStorage.setItem('slippage_enabled', JSON.stringify(newVal));
});

watch(() => config.value.slippage_rate_pct, (newVal) => {
  localStorage.setItem('slippage_rate_pct', JSON.stringify(newVal));
});

watch(tickerList, (newList) => {
  if (newList.length > 0) {
    const saved = localStorage.getItem('lastSelectedTicker');
    if (saved && newList.includes(saved)) {
      ticker.value = saved;
    } else if (!ticker.value || !newList.includes(ticker.value)) {
      ticker.value = newList[0];
    }
  }
}, { immediate: true });

onMounted(async () => {
    const strats = await fetchStrategies();
    if (strats && strats.length > 0) {
        strategyList.value = strats;
        // if DEFAULT is not in list, add it or select first
        if (!strategyList.value.find(s => s.name === 'DEFAULT')) {
            strategyList.value.unshift({ name: 'DEFAULT' });
        }
    }
});
</script>

<style scoped>
.simulation-settings.in-pane {
  max-width: 800px;
  margin: 0 auto;
  padding: 3rem;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}
</style>
