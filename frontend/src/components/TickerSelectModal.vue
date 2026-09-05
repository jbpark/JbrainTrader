<template>
  <div class="search-results-popup glass">
    <div v-if="results.length === 0" class="no-results-item">검색 결과가 없습니다.</div>
    <div 
      v-for="item in results" 
      :key="item.ticker" 
      class="search-result-item"
      @click="selectTicker(item)"
    >
      <div class="res-ticker">{{ formatTicker(item.ticker) }}</div>
      <div class="res-name">{{ item.name }}</div>
      <div class="res-market">{{ formatMarket(item.market) }}</div>
    </div>
    <div class="search-results-footer" @click="emit('close')">닫기</div>
  </div>
</template>

<script setup>
const props = defineProps({
  query: String,
  results: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits(['select', 'close']);

const selectTicker = (item) => {
  emit('select', item);
};

const formatTicker = (ticker) => {
  if (!ticker) return '';
  return ticker.split('.')[0];
};

const formatMarket = (market) => {
  if (!market) return '-';
  const m = market.toUpperCase();
  if (m === 'KSC' || m === 'KRX' || m === 'KOSPI' || m === 'ETF') return '코스피';
  if (m === 'KOE' || m === 'KOSDAQ' || m === 'KSQ') return '코스닥';
  return '해외';
};
</script>

<style scoped>
.search-results-popup {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 9999;
  max-height: 300px;
  overflow-y: auto;
  background: rgba(25, 25, 40, 0.98);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  margin-top: 5px;
  box-shadow: 0 15px 35px rgba(0, 0, 0, 0.8), 0 0 15px rgba(0, 255, 136, 0.1);
  animation: fadeIn 0.2s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-5px); }
  to { opacity: 1; transform: translateY(0); }
}

.search-result-item {
  padding: 10px 15px;
  cursor: pointer;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: background 0.2s;
  color: #e0e0e0;
}

.search-result-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.res-ticker {
  flex: 0 0 80px;
  font-size: 0.85rem;
  color: #8b949e;
  font-family: monospace;
}

.res-name {
  flex: 1;
  font-size: 0.9rem;
  font-weight: bold;
  color: var(--primary, #00ff88);
  margin-left: 10px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-align: left;
}

.res-market {
  flex: 0 0 60px;
  font-size: 0.8rem;
  color: #8b949e;
  text-align: right;
}

.no-results-item {
  padding: 15px;
  text-align: center;
  color: #8b949e;
  font-size: 0.85rem;
}

.search-results-footer {
  padding: 8px;
  text-align: center;
  font-size: 0.75rem;
  color: var(--primary, #00ff88);
  background: rgba(255, 255, 255, 0.02);
  cursor: pointer;
}

/* Scrollbar styling */
.search-results-popup::-webkit-scrollbar {
  width: 6px;
}
.search-results-popup::-webkit-scrollbar-track {
  background: transparent;
}
.search-results-popup::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}
.search-results-popup::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}
</style>
