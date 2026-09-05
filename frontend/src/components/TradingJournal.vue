<template>
  <div class="journal-container">
    <div class="journal-layout">
      <!-- Left: Calendar Side -->
      <div class="calendar-section glass">
        <div class="calendar-header">
          <button class="nav-btn" @click="changeMonth(-1)">&lt;</button>
          <h2 class="current-month">{{ year }}년 {{ month }}월</h2>
          <button class="nav-btn" @click="changeMonth(1)">&gt;</button>
        </div>

        <div class="calendar-grid">
          <div v-for="day in weekDays" :key="day" class="day-header">{{ day }}</div>
          <div v-for="n in emptyDays" :key="'e'+n" class="day-cell empty"></div>
          <div 
            v-for="date in monthDates" 
            :key="date.fullDate" 
            class="day-cell"
            :class="getDayClass(date.fullDate)"
            @click="selectDate(date.fullDate)"
          >
            <span class="day-num">{{ date.day }}</span>
            <div v-if="summary[date.fullDate]" class="day-info">
              <div class="trade-count">{{ summary[date.fullDate].trade_count }}건</div>
              <div class="day-profit" :class="getPriceClass(summary[date.fullDate].profit)">
                {{ summary[date.fullDate].profit > 0 ? '+' : '' }}{{ Math.round(summary[date.fullDate].profit).toLocaleString() }}
              </div>
            </div>
          </div>
        </div>

        <!-- Monthly Summary Footer -->
        <div class="monthly-stats">
          <div class="stat-item">
            <span class="label">월간 수익</span>
            <span class="val" :class="getPriceClass(monthlyTotalProfit)">
              {{ monthlyTotalProfit > 0 ? '+' : '' }}{{ Math.round(monthlyTotalProfit).toLocaleString() }}원
            </span>
          </div>
          <div class="stat-item">
            <span class="label">총 매매횟수</span>
            <span class="val">{{ monthlyTotalTrades }}회</span>
          </div>
        </div>
      </div>

      <!-- Right: Trade List Side -->
      <div class="trades-section glass">
        <div class="section-title">
          <h3>📅 {{ selectedDate }} 매매 내역</h3>
            <div class="display-mode-selector">
              <select v-model="displayMode" class="mode-select">
                <option value="detail">매매별 (상세)</option>
                <option value="ticker">종목별 (합산)</option>
              </select>
            </div>
            <button class="sync-btn" @click="handleSync" :disabled="syncing">
              <span v-if="syncing" class="mini-spinner"></span>
              {{ syncing ? '동기화 중...' : '키움 API 동기화' }}
            </button>
            <button class="sync-btn gsheet-btn" @click="handleExportGSheet" :disabled="exporting">
              <span v-if="exporting" class="mini-spinner"></span>
              {{ exporting ? '업로드 중...' : '구글 시트 업로드' }}
            </button>
            <a v-if="gsheetUrl" :href="gsheetUrl" target="_blank" class="gsheet-link" title="구글 시트 열기">시트 열기 ↗</a>
            <div class="summary-info" v-if="filteredTrades.length > 0">
          <span class="profit-label">일일 손익: </span>
          <span :class="getPriceClass(displayDailyProfit)" :title="dailyTotal && dailyTotal.exists ? '키움 정산 기준 (opt10074)' : '종목별 내역 합계'">{{ (displayDailyProfit > 0 ? '+' : '') + Math.round(displayDailyProfit).toLocaleString() }}원</span>
          <span class="yield-label" style="margin-left: 10px; color: var(--text-muted); font-size: 0.85rem;">(수익률: </span>
          <span :class="getPriceClass(dailyTotalYield)" style="font-size: 0.85rem; font-weight: bold;">{{ (dailyTotalYield > 0 ? '+' : '') + dailyTotalYield.toFixed(2) }}%</span>
          <span style="color: var(--text-muted); font-size: 0.85rem;">)</span>
        </div>
            <span class="active-acc" v-if="currentAccNo">
              계좌: {{ currentAccNo }}
            </span>
        </div>

        <div v-if="loading" class="loading-state">
          <div class="spinner"></div>
          <p>데이터를 불러오는 중...</p>
        </div>

        <div v-else-if="dailyTrades.length === 0" class="empty-trades">
          <p>이날의 매매 내역이 없습니다.</p>
        </div>

        <div v-else class="trades-list-wrapper">
          <table class="trades-table">
            <thead>
              <tr>
                <th>종목명</th>
                <th class="text-right">매수단가</th>
                <th class="text-right">매도단가</th>
                <th class="text-right">수량</th>
                <th class="text-right">수수료+제세금</th>
                <th class="text-right">실현손익</th>
                <th class="text-right">수익률</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="trade in filteredTrades" :key="trade.id || trade.order_no || trade.ticker" :class="trade.side?.toLowerCase()">
                <td class="name">
                  <span class="ticker-name">{{ trade.ticker_name }}</span>
                  <span class="ticker-code">{{ trade.ticker }}</span>
                </td>
                
                <!-- 매수단가 -->
                <td class="buy-price text-right" v-if="trade.side === 'SUMMARY'">
                  {{ Math.round(trade.buy_price || (trade.qty > 0 ? (trade.buy_amount / trade.qty) : 0)).toLocaleString() }}
                </td>
                <td class="buy-price text-right" v-else-if="trade.side === 'BUY'">{{ Math.round(trade.price || 0).toLocaleString() }}</td>
                <td class="buy-price text-right" v-else>-</td>
                
                <!-- 매도단가 -->
                <td class="sell-price text-right" v-if="trade.side === 'SUMMARY'">{{ Math.round(trade.price || 0).toLocaleString() }}</td>
                <td class="sell-price text-right" v-else-if="trade.side === 'SELL'">{{ Math.round(trade.price || 0).toLocaleString() }}</td>
                <td class="sell-price text-right" v-else>-</td>

                <!-- 수량 -->
                <td class="qty text-right">{{ (trade.qty || 0).toLocaleString() }}</td>

                <!-- 수수료+제세금 -->
                <td class="fee text-right text-muted" style="font-size: 0.8rem;">
                  {{ Math.round((Number(trade.fee) || 0) + (Number(trade.tax) || 0)).toLocaleString() }}
                </td>

                <td class="profit text-right" :class="getPriceClass(trade.profit)">
                   {{ (trade.profit > 0 ? '+' : '') + Math.round(trade.profit || 0).toLocaleString() }}
                </td>
                
                <td class="ratio text-right" :class="getPriceClass(trade.profit_rate)">
                   {{ (trade.profit_rate > 0 ? '+' : '') + Number(trade.profit_rate || 0).toFixed(2) }}%
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { fetchTrades, fetchTradesSummary, fetchDailyProfitTotal, syncTradesFromKiwoom, exportTradesToGSheet } from '../api';

const props = defineProps({
  account: { type: Object, default: () => ({}) }
});

const savedDate = localStorage.getItem('lastSelectedJournalDate');
const parts = savedDate ? savedDate.split('-').map(Number) : null;
const year = ref(parts ? parts[0] : new Date().getFullYear());
const month = ref(parts ? parts[1] : new Date().getMonth() + 1);
const selectedDate = ref(savedDate || new Date().toISOString().split('T')[0]);
const summary = ref({});
const dailyTrades = ref([]);
const dailyTotal = ref(null); // 정산 기준(opt10074) 일일 손익 — 키움 앱 표시값과 동일
// 표시 모드: 'detail'(매매별) / 'ticker'(종목별 합산). 기본은 종목별 합산이며,
// 사용자가 바꾸면 localStorage에 기억해 다음 접속 때도 유지한다.
const DISPLAY_MODE_KEY = 'journal_display_mode';
const savedMode = localStorage.getItem(DISPLAY_MODE_KEY);
const displayMode = ref(savedMode === 'detail' || savedMode === 'ticker' ? savedMode : 'ticker');
watch(displayMode, (v) => localStorage.setItem(DISPLAY_MODE_KEY, v));
const loading = ref(false);
const syncing = ref(false);
const exporting = ref(false);
const gsheetUrl = ref(null);

const currentAccNo = computed(() => props.account?.acc_no);

const weekDays = ['일', '월', '화', '수', '목', '금', '토'];

const emptyDays = computed(() => {
  return new Date(year.value, month.value - 1, 1).getDay();
});

const monthDates = computed(() => {
  const lastDay = new Date(year.value, month.value, 0).getDate();
  const dates = [];
  for (let i = 1; i <= lastDay; i++) {
    const fullDate = `${year.value}-${String(month.value).padStart(2, '0')}-${String(i).padStart(2, '0')}`;
    dates.push({ day: i, fullDate });
  }
  return dates;
});

const monthlyTotalProfit = computed(() => {
  return Object.values(summary.value).reduce((s, v) => s + (Number(v.profit) || 0), 0);
});

const monthlyTotalTrades = computed(() => {
  return Object.values(summary.value).reduce((s, v) => s + (Number(v.trade_count) || 0), 0);
});

const dailyTotalProfit = computed(() => {
  return dailyTrades.value.reduce((s, t) => s + (Number(t.profit) || 0), 0);
});

// 표시용 일일 손익: 정산 기준 값이 있으면 우선 사용 (키움 앱과 원단위 일치)
const displayDailyProfit = computed(() => {
  if (dailyTotal.value && dailyTotal.value.exists) return Number(dailyTotal.value.profit) || 0;
  return dailyTotalProfit.value;
});

const dailyTotalYield = computed(() => {
  const totalBuy = dailyTrades.value.reduce((s, t) => {
    const buyAmt = Number(t.buy_amount || 0) || (t.side === 'BUY' ? Number(t.amount || 0) : 0);
    return s + buyAmt;
  }, 0);
  if (totalBuy === 0) return 0;
  return (dailyTotalProfit.value / totalBuy) * 100;
});

const filteredTrades = computed(() => {
  if (displayMode.value === 'detail') {
    return dailyTrades.value;
  }
  
  // 1단계: 종목별로 SUMMARY 데이터가 있는지 확인
  const hasSummary = {};
  dailyTrades.value.forEach(t => {
    if (t.side === 'SUMMARY') hasSummary[t.ticker] = true;
  });

  // 2단계: 합산 로직
  const groups = {};
  dailyTrades.value.forEach(t => {
    // 해당 종목에 SUMMARY가 있는데 현재 레코드가 BUY/SELL이면 건너뜀 (중복 방지)
    if (hasSummary[t.ticker] && (t.side === 'BUY' || t.side === 'SELL')) return;
    
    // 중복된 SUMMARY 데이터도 order_no 기준으로 한 번 더 거름 (동기화 여러 번 했을 경우 대비)
    const orderKey = t.order_no || `${t.ticker}_${t.side}_${t.execution_time}`;
    if (!groups[t.ticker]) {
      groups[t.ticker] = {
        ticker: t.ticker,
        ticker_name: t.ticker_name,
        buy_amount: 0,
        sell_amount: 0,
        total_qty: 0,
        buy_qty: 0,
        sell_qty: 0,
        profit: 0,
        fee: 0,
        tax: 0,
        side: 'SUMMARY',
        time_str: t.time_str,
        processed_orders: new Set()
      };
    }
    
    const g = groups[t.ticker];
    if (g.processed_orders.has(orderKey)) return;
    g.processed_orders.add(orderKey);
    
    // 매수 데이터 합산
    if (t.side === 'SUMMARY' || t.side === 'BUY') {
      const bAmt = Number(t.buy_amount || 0) || (t.side === 'BUY' ? Number(t.amount || 0) : 0);
      const bQty = Number(t.qty || 0);
      g.buy_amount += bAmt;
      g.buy_qty += bQty;
    }
    
    // 매도 데이터 합산
    if (t.side === 'SUMMARY' || t.side === 'SELL') {
      const sAmt = Number(t.amount || 0);
      const sQty = Number(t.qty || 0);
      g.sell_amount += sAmt;
      g.sell_qty += sQty;
    }

    g.total_qty = g.sell_qty || g.buy_qty;
    g.profit += Number(t.profit || 0);
    g.fee += Number(t.fee || 0);
    g.tax += Number(t.tax || 0);
  });
  
  const results = Object.values(groups).map(g => {
    // 수익률 및 평균 단가 재계산
    const profitRate = g.buy_amount > 0 ? (g.profit / g.buy_amount) * 100 : 0;
    const avgBuyPrice = g.buy_qty > 0 ? g.buy_amount / g.buy_qty : 0;
    const avgSellPrice = g.sell_qty > 0 ? g.sell_amount / g.sell_qty : 0;

    return {
      ...g,
      buy_price: avgBuyPrice,
      price: avgSellPrice,
      qty: g.total_qty,
      amount: g.sell_amount, // 테이블 표시용
      profit_rate: profitRate
    };
  });

  // 손익이 0인 종목 제외 (합산 모드에서만) 및 정렬
  return results
    .filter(g => Math.abs(g.profit) > 0)
    .sort((a, b) => a.ticker_name.localeCompare(b.ticker_name));
});

const loadSummary = async (silent = false) => {
  if (!currentAccNo.value) return;
  const res = await fetchTradesSummary(year.value, month.value, currentAccNo.value);
  summary.value = res;
};

const loadDailyTrades = async (silent = false) => {
  if (!currentAccNo.value) return;
  if (!silent) loading.value = true;
  try {
    const res = await fetchTrades(selectedDate.value, currentAccNo.value);
    dailyTrades.value = res;
    dailyTotal.value = await fetchDailyProfitTotal(selectedDate.value, currentAccNo.value);
  } finally {
    if (!silent) loading.value = false;
  }
};

const handleSync = async () => {
  const accNo = currentAccNo.value;
  if (!accNo) {
    alert("연결된 계좌 정보가 없습니다. 상단 '계정' 탭에서 로그인을 확인해 주세요.");
    return;
  }
  if (!confirm(`${selectedDate.value} 매매 내역을 키움 API에서 다시 불러올까요?\n해당 날짜의 기존 내역은 새 데이터로 교체됩니다.`)) return;
  syncing.value = true;
  try {
    const res = await syncTradesFromKiwoom(selectedDate.value, accNo);
    if (res.status === 'SUCCESS') {
      setTimeout(async () => {
        await loadDailyTrades();
        await loadSummary();
        syncing.value = false;
      }, 2000);
    } else {
      alert("동기화 요청 실패: " + res.message);
      syncing.value = false;
    }
  } catch (err) {
    console.error(err);
    syncing.value = false;
  }
};

const handleExportGSheet = async () => {
  const accNo = currentAccNo.value;
  if (!accNo) {
    alert("연결된 계좌 정보가 없습니다. 상단 '계정' 탭에서 로그인을 확인해 주세요.");
    return;
  }
  if (dailyTrades.value.length === 0) {
    alert("업로드할 매매 내역이 없습니다. 먼저 '키움 API 동기화'를 실행해 주세요.");
    return;
  }
  if (!confirm(`${selectedDate.value} 매매일지를 구글 시트에 업로드할까요?\n같은 날짜의 기존 행은 덮어씁니다.`)) return;
  exporting.value = true;
  try {
    const res = await exportTradesToGSheet(selectedDate.value, accNo);
    if (res.status === 'SUCCESS') {
      gsheetUrl.value = res.url || null;
      alert(`구글 시트 업로드 완료 (매매 ${res.rows}건)`);
    } else {
      alert("구글 시트 업로드 실패: " + res.message);
    }
  } catch (err) {
    console.error(err);
    alert("구글 시트 업로드 중 오류: " + err.message);
  } finally {
    exporting.value = false;
  }
};

const changeMonth = (delta) => {
  month.value += delta;
  if (month.value > 12) {
    month.value = 1;
    year.value++;
  } else if (month.value < 1) {
    month.value = 12;
    year.value--;
  }
};

const selectDate = (date) => {
  selectedDate.value = date;
  localStorage.setItem('lastSelectedJournalDate', date);
  loadDailyTrades();
};

const getDayClass = (date) => {
  const classes = [];
  if (date === selectedDate.value) classes.push('selected');
  if (summary.value[date]) classes.push('has-trade');
  
  const d = new Date(date).getDay();
  if (d === 0) classes.push('sun');
  if (d === 6) classes.push('sat');
  
  return classes.join(' ');
};

const getPriceClass = (val) => {
  if (val > 0) return 'text-up';
  if (val < 0) return 'text-down';
  return '';
};

watch([year, month], () => loadSummary());

// 핵심 수정: 계좌번호가 실제로 '변경'될 때만 새로고침 (실시간 손익 업데이트 시 깜빡임 방지)
watch(() => currentAccNo.value, (newVal, oldVal) => {
  if (newVal && newVal !== oldVal) {
    loadSummary();
    loadDailyTrades();
  }
});

let refreshInterval = null;

onMounted(() => {
  loadSummary();
  loadDailyTrades();
  
  // 오늘 날짜인 경우에만 30초마다 자동 갱신
  refreshInterval = setInterval(() => {
    const todayStr = new Date().toLocaleDateString('en-CA'); // YYYY-MM-DD
    if (selectedDate.value === todayStr) {
      loadSummary(true);
      loadDailyTrades(true);
    }
  }, 30000);
});

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval);
});
</script>

<style scoped>
.journal-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.journal-layout {
  display: grid;
  grid-template-columns: 450px 1fr;
  gap: 1.5rem;
  height: 100%;
  min-height: 0;
}

.calendar-section {
  display: flex;
  flex-direction: column;
  padding: 1.5rem;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.03);
}

.calendar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.current-month {
  font-size: 1.3rem;
  font-weight: 800;
  color: var(--primary);
  margin: 0;
}

.nav-btn {
  background: rgba(255, 255, 255, 0.1);
  border: none;
  color: white;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.nav-btn:hover {
  background: var(--primary);
  color: black;
}

.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 5px;
}

.day-header {
  text-align: center;
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--text-muted);
  padding-bottom: 10px;
}

.day-cell {
  height: 60px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  padding: 5px;
  display: flex;
  flex-direction: column;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.day-cell:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.2);
}

.day-cell.empty {
  cursor: default;
  opacity: 0.3;
}

.day-cell.selected {
  background: rgba(0, 255, 149, 0.1);
  border-color: var(--primary);
  box-shadow: 0 0 10px rgba(0, 255, 149, 0.2);
}

.day-num {
  font-size: 0.75rem;
  font-weight: 800;
  color: var(--text-muted);
}

.sun .day-num { color: #ff4d4d; }
.sat .day-num { color: #4d94ff; }

.day-info {
  margin-top: auto;
  text-align: right;
  line-height: 1.2;
}

.trade-count {
  font-size: 0.65rem;
  color: var(--text-muted);
}

.day-profit {
  font-size: 0.75rem;
  font-weight: 800;
}

.monthly-stats {
  margin-top: auto;
  padding-top: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stat-item .label {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.stat-item .val {
  font-weight: 800;
  font-size: 1.1rem;
}

/* Trades Section */
.trades-section {
  padding: 1.5rem;
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.03);
}

.section-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.section-title h3 {
  margin: 0;
  color: var(--text-main);
  font-size: 1.2rem;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.sync-btn {
  background: rgba(var(--primary-rgb), 0.1);
  border: 1px solid var(--primary);
  color: var(--primary);
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 0.8rem;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s;
}

.sync-btn:hover:not(:disabled) {
  background: var(--primary);
  color: black;
}

.sync-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.mini-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(0, 255, 149, 0.2);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.daily-summary {
  font-size: 0.95rem;
  font-weight: 700;
}

.gsheet-btn {
  background: rgba(15, 157, 88, 0.15);
  border-color: rgba(15, 157, 88, 0.5);
  color: #34A853;
  margin-left: 6px;
}

.gsheet-btn:hover:not(:disabled) {
  background: rgba(15, 157, 88, 0.3);
}

.gsheet-link {
  font-size: 0.75rem;
  color: #34A853;
  margin-left: 6px;
  text-decoration: none;
}

.gsheet-link:hover {
  text-decoration: underline;
}

.active-acc {
  font-size: 0.75rem;
  color: var(--text-muted);
  background: rgba(255, 255, 255, 0.05);
  padding: 2px 8px;
  border-radius: 4px;
}

.display-mode-selector {
  margin-right: 0.5rem;
}

.mode-select {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: white;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 0.85rem;
  outline: none;
  cursor: pointer;
  transition: all 0.2s;
}

.mode-select:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: var(--primary);
}

.trades-list-wrapper {
  flex: 1;
  overflow-y: auto;
}

.trades-table {
  width: 100%;
  border-collapse: collapse;
}

.trades-table th {
  text-align: left;
  padding: 10px;
  font-size: 0.85rem;
  color: var(--text-muted);
  border-bottom: 2px solid rgba(255, 255, 255, 0.1);
}

.trades-table th.text-right, 
.trades-table td.text-right {
  text-align: right;
}

.trades-table td {
  padding: 12px 10px;
  font-size: 0.9rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.time { color: var(--text-muted); font-family: monospace; }
.ticker-name { display: block; font-weight: 700; color: var(--text-main); }
.ticker-code { display: block; font-size: 0.75rem; color: var(--text-muted); }

.side-badge {
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 800;
}

.side-badge.buy { background: rgba(255, 77, 77, 0.15); color: #ff4d4d; }
.side-badge.sell { background: rgba(77, 148, 255, 0.15); color: #4d94ff; }

.price, .qty, .buy-price, .sell-price { font-weight: 700; color: var(--text-main); }
.profit { font-weight: 800; }
.memo { font-size: 0.8rem; color: var(--text-muted); }


.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--text-muted);
}

.empty-trades {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-muted);
  font-style: italic;
}

.spinner {
  width: 30px;
  height: 30px;
  border: 3px solid rgba(0, 255, 149, 0.1);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 10px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.text-up { color: #ff4d4d !important; }
.text-down { color: #4d94ff !important; }
</style>
