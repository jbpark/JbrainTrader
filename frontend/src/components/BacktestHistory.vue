<template>
  <div class="backtest-history glass">
    <div class="header">
      <h3 style="color: var(--primary); margin: 0">🕒 백테스트 결과 내역</h3>
      <button class="btn-refresh" @click="loadResults">새로고침</button>
    </div>

    <div class="table-container">
      <table v-if="results.length > 0" class="history-table">
        <thead>
          <tr>
            <th>실행 시각</th>
            <th>종목</th>
            <th>전략</th>
            <th>데이터 날짜</th>
            <th>수익률</th>
            <th>매매 횟수</th>
            <th>MDD</th>
            <th>관리</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in results" :key="r.id">
            <td class="timestamp">{{ r.executed_at }}</td>
            <td class="ticker">{{ r.ticker_name || r.ticker }}</td>
            <td class="strategy">{{ r.strategy_name }}</td>
            <td class="date">{{ r.data_date }}</td>
            <td :class="['profit', (r.profit_rate || 0) >= 0 ? 'plus' : 'minus']">
              {{ (r.profit_rate || 0) >= 0 ? '+' : '' }}{{ (r.profit_rate || 0).toFixed(2) }}%
            </td>
            <td>{{ r.total_trades || 0 }}회</td>
            <td class="mdd">{{ (r.max_dd || 0).toFixed(2) }}%</td>
            <td class="actions">
              <button class="btn-view" @click="viewDetail(r.id)">조회</button>
              <button class="btn-delete" @click="confirmDelete(r.id)">삭제</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty-state">
        <p>저장된 백테스트 결과가 없습니다.</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { fetchBacktestResults, fetchBacktestDetail, deleteBacktestResult } from '../api';

const emit = defineEmits(['view-detail']);
const results = ref([]);

const loadResults = async () => {
    results.value = await fetchBacktestResults();
};

onMounted(() => {
    loadResults();
});

const viewDetail = async (id) => {
    const detail = await fetchBacktestDetail(id);
    if (detail) {
        emit('view-detail', detail);
    } else {
        alert("상세 데이터를 불러오지 못했습니다.");
    }
};

const confirmDelete = async (id) => {
    if (confirm("정말로 이 백테스트 결과를 삭제하시겠습니까?")) {
        const res = await deleteBacktestResult(id);
        if (res.status === 'SUCCESS') {
            loadResults();
        } else {
            alert("삭제에 실패했습니다.");
        }
    }
};
</script>

<style scoped>
.backtest-history {
  padding: 2rem;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.btn-refresh {
  padding: 8px 16px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--text-main);
  cursor: pointer;
}

.table-container {
  flex: 1;
  overflow-y: auto;
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.history-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.history-table th {
  position: sticky;
  top: 0;
  background: rgba(30,30,30,0.9);
  padding: 12px;
  text-align: left;
  color: var(--text-muted);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.history-table td {
  padding: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.timestamp { color: var(--text-muted); font-size: 0.8rem; }
.ticker { font-weight: bold; }
.strategy { color: var(--secondary); }
.profit.plus { color: #ff6b6b; }
.profit.minus { color: #4dabf7; }
.mdd { color: #fab005; }

.actions {
  display: flex;
  gap: 8px;
}

.btn-view {
  padding: 4px 10px;
  background: var(--primary);
  border: none;
  border-radius: 4px;
  color: white;
  cursor: pointer;
}

.btn-delete {
  padding: 4px 10px;
  background: rgba(255, 0, 0, 0.2);
  border: 1px solid rgba(255, 0, 0, 0.2);
  border-radius: 4px;
  color: #ff6b6b;
  cursor: pointer;
}

.btn-delete:hover {
  background: rgba(255, 0, 0, 0.4);
}

.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
  color: var(--text-muted);
}
</style>
