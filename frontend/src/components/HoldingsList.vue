<template>
  <div class="holdings-container">
    <div v-if="holdings === null" class="empty-state glass loading">
      <div class="spinner"></div>
      <p>계좌 정보를 불러오는 중입니다...</p>
    </div>

    <div v-else class="holdings-content">
      <!-- Account Summary Header -->
      <div class="account-summary-bar glass">
        <div class="summary-card">
          <span class="label">계좌번호</span>
          <span class="value">{{ formattedAccNo }}</span>
        </div>
        <div class="summary-divider"></div>
        <div class="summary-card">
          <span class="label">총 매입금액</span>
          <span class="value">{{ totalBuyAmount.toLocaleString() }}원</span>
        </div>
        <div class="summary-divider"></div>
        <div class="summary-card">
          <span class="label">총 평가손익</span>
          <span class="value" :class="getPriceClass(totalProfit)">
            {{ totalProfit > 0 ? '+' : '' }}{{ totalProfit.toLocaleString() }}원
          </span>
        </div>
        <div class="summary-divider"></div>
        <div class="summary-card">
          <span class="label">총 수익률</span>
          <span class="value">
            <span class="ratio-badge big" :class="getRatioClass(totalRatio)">
              {{ totalRatio > 0 ? '+' : '' }}{{ totalRatio.toFixed(2) }}%
            </span>
          </span>
        </div>
      </div>

      <div class="holdings-toolbar">
        <!-- 보유 종목 전체를 한 프로파일로 분석 -->
        <span class="toolbar-label">🤖 전체 분석</span>
        <select v-model="batchProfileId" class="profile-select" :disabled="batch.running">
          <option v-for="p in aiProfiles" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
        <button
          class="run-btn"
          :disabled="batch.running || holdings.length === 0 || aiProfiles.length === 0"
          @click="handleRunBatch"
          :title="`보유 종목 ${holdings.length}개를 선택한 프로파일로 순차 분석합니다`"
        >
          <span v-if="batch.running" class="spinner-sm"></span>
          {{ batch.running
            ? `분석 중 ${batch.done}/${batch.total}${batch.current ? ' · ' + batch.current : ''}`
            : `보유 종목 ${holdings.length}개 분석` }}
        </button>
        <span v-if="batch.running" class="analysis-hint">한 종목씩 순서대로 진행합니다.</span>
        <span v-else-if="batch.total > 0" class="analysis-hint">
          완료 {{ batch.done }}건{{ batch.errors ? ` · 실패 ${batch.errors}건` : '' }}
        </span>

        <span class="toolbar-spacer"></span>

        <button
          class="gsheet-btn"
          :disabled="refreshing"
          @click="handleRefreshHoldings"
          title="증권사에서 보유 종목과 현재가를 다시 불러옵니다"
        >
          <span v-if="refreshing" class="spinner-sm"></span>
          {{ refreshing ? '업데이트 중...' : '🔄 업데이트' }}
        </button>

        <button
          class="gsheet-btn"
          :disabled="exportingSheet || holdings.length === 0"
          @click="handleExportHoldings"
          title="구글 시트의 '보유종목' 탭에 현재 보유 종목을 업로드합니다"
        >
          <span v-if="exportingSheet" class="spinner-sm"></span>
          {{ exportingSheet ? '업로드 중...' : '📗 구글 시트 업로드' }}
        </button>
        <a v-if="gsheetUrl" :href="gsheetUrl" target="_blank" class="gsheet-link">시트 열기 ↗</a>
      </div>

      <div v-if="holdings.length === 0" class="empty-state glass no-margin">
        <div class="empty-icon">📂</div>
        <p>보유 중인 종목이 없습니다.</p>
      </div>
      <table class="holdings-table">
        <thead>
          <tr>
            <th
              v-for="col in columns"
              :key="col.key"
              class="sortable"
              :class="[col.class, { 'text-right': col.key !== 'name', active: sortKey === col.key }]"
              @click="toggleSort(col.key)"
            >
              {{ col.label }}
              <span class="sort-arrow">{{ sortKey === col.key ? (sortDir === 'asc' ? '▲' : '▼') : '' }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <template v-for="item in sortedHoldings" :key="item.ticker">
          <tr
            class="holding-row clickable"
            :class="{ open: expandedTicker === item.ticker }"
            @click="toggleStrategy(item)"
          >
            <td class="col-name">
              <div class="ticker-info">
                <span class="stock-name">
                  {{ item.name }}
                  <span
                    class="ai-badge"
                    :class="{ dim: !hasStrategy(item) }"
                    :title="hasStrategy(item)
                      ? `AI 매매 전략 ${strategiesFor(item).length}건이 있습니다. 클릭하면 펼쳐집니다.`
                      : '클릭하면 AI 매매 분석을 실행할 수 있습니다.'"
                  >
                    🤖<template v-if="strategiesFor(item).length > 1">{{ strategiesFor(item).length }}</template>
                    {{ expandedTicker === item.ticker ? '▲' : '▼' }}
                  </span>
                </span>
                <span class="stock-ticker">{{ item.ticker }}</span>
              </div>
            </td>
            <td class="text-right font-medium col-qty">{{ (item.qty ?? 0).toLocaleString() }}</td>
            <td class="text-right text-muted col-buy">{{ (item.buy_price ?? item.avg_price ?? 0).toLocaleString() }}</td>
            <td class="text-right col-amount">{{ getBuyAmount(item).toLocaleString() }}</td>
            <td class="text-right col-current">{{ (item.current_price ?? 0).toLocaleString() }}</td>
            <td class="text-right col-profit" :class="getPriceClass(item.profit)">
              {{ (item.profit ?? 0) > 0 ? '+' : '' }}{{ (item.profit ?? 0).toLocaleString() }}
            </td>
            <td class="text-right col-ratio">
              <span class="ratio-badge" :class="getRatioClass(item.ratio)">
                {{ (item.ratio ?? 0) > 0 ? '+' : '' }}{{ (item.ratio ?? 0).toFixed(2) }}%
              </span>
            </td>
          </tr>
          <!-- AI 매매 전략 / 분석 실행 -->
          <tr v-if="expandedTicker === item.ticker" class="strategy-row">
            <td :colspan="columns.length">
              <!-- 분석 실행 (프로파일 선택 + 실행) -->
              <div class="analysis-bar">
                <span class="analysis-label">🤖 AI 매매 분석</span>
                <select v-model="runProfileId" class="profile-select" @click.stop>
                  <option v-for="p in aiProfiles" :key="p.id" :value="p.id">{{ p.name }}</option>
                </select>
                <button
                  class="run-btn"
                  :disabled="runningTicker === item.ticker || aiProfiles.length === 0"
                  @click.stop="handleRunAnalysis(item)"
                >
                  <span v-if="runningTicker === item.ticker" class="spinner-sm"></span>
                  {{ runningTicker === item.ticker ? '분석 중... (최대 15분)' : '분석 실행' }}
                </button>
                <span v-if="!hasStrategy(item) && runningTicker !== item.ticker" class="analysis-hint">
                  아직 이 종목의 분석 결과가 없습니다.
                </span>
              </div>

              <!-- 프로파일이 여러 개면 선택해서 각각의 분석을 본다 -->
              <div v-if="strategiesFor(item).length > 1" class="profile-tabs">
                <button
                  v-for="s in strategiesFor(item)"
                  :key="s.profile_id"
                  class="profile-tab"
                  :class="{ on: activeStrategy(item)?.profile_id === s.profile_id }"
                  @click.stop="selectProfile(item, s.profile_id)"
                >
                  {{ s.profile_name }}
                </button>
              </div>

              <div v-for="s in (activeStrategy(item) ? [activeStrategy(item)] : [])" :key="s.profile_id" class="strategy-card">
                <div class="strategy-head">
                  <span class="strategy-title">🤖 {{ s.profile_name }}</span>
                  <span class="risk-chip" :class="riskClass(s.strategy.risk_level)">
                    리스크 {{ s.strategy.risk_level }}
                  </span>
                  <span class="strategy-meta">{{ s.finished_at }} · {{ s.model }}</span>
                </div>
                <p class="strategy-summary">{{ s.strategy.summary }}</p>
                <div class="strategy-metrics">
                  <div><span>진입 가격대</span><b class="c-entry">{{ s.strategy.entry_price }}</b></div>
                  <div><span>목표가</span><b class="c-up">{{ won(s.strategy.target_price) }}</b></div>
                  <div><span>손절가</span><b class="c-down">{{ won(s.strategy.stop_loss) }}</b></div>
                  <div><span>기대 수익</span><b>{{ s.strategy.expected_return }}</b></div>
                  <div><span>투자 비중</span><b>{{ s.strategy.position_size }}</b></div>
                  <div><span>보유 기간</span><b>{{ s.strategy.holding_period }}</b></div>
                </div>
                <div class="strategy-conds">
                  <div v-if="s.strategy.buy_conditions?.length">
                    <h5 class="c-up">✅ 매수 조건</h5>
                    <ul><li v-for="(c, i) in s.strategy.buy_conditions" :key="i">{{ c }}</li></ul>
                  </div>
                  <div v-if="s.strategy.sell_conditions?.length">
                    <h5 class="c-entry">🎯 매도 조건</h5>
                    <ul><li v-for="(c, i) in s.strategy.sell_conditions" :key="i">{{ c }}</li></ul>
                  </div>
                  <div v-if="s.strategy.risks?.length">
                    <h5 class="c-down">⚠️ 리스크</h5>
                    <ul><li v-for="(c, i) in s.strategy.risks" :key="i">{{ c }}</li></ul>
                  </div>
                </div>
              </div>
            </td>
          </tr>
          </template>
        </tbody>
      </table>
    </div>

  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue';
import {
  fetchAiTradeStrategies, exportHoldingsToGSheet,
  fetchAiTrades, runAiTrade, runAiTradeBatch, fetchAiTradeBatchStatus,
  refreshAccount,
} from '../api';

const props = defineProps({
  holdings: {
    type: Array,
    default: () => []
  },
  account: {
    type: Object,
    default: () => ({ acc_no: '' })
  }
});

const formattedAccNo = computed(() => {
  if (!props.account?.acc_no) return '-';
  const acc = props.account.acc_no;
  if (acc.length < 10) return acc;
  
  // 10자리 계좌번호를 "앞 4자리-중간 4자리[계좌구분]" 형태로 표시한다.
  // 계좌구분은 끝 2자리가 '10'일 때 앞 4자리로 판정하고(위탁종합/연금저축),
  // 그 외에는 기본값 [위탁]을 쓴다. 뒤 2자리는 화면에 노출하지 않는다.

  const prefix = acc.substring(0, 4);
  const middle = acc.substring(4, 8);
  const suffix = acc.substring(8);
  
  let label = '[위탁]';
  if (suffix === '10') {
    if (prefix === '5407') label = '[위탁종합]';
    else if (prefix === '6453') label = '[연금저축]';
    else label = '[위탁종합]';
  }
  
  return `${prefix}-${middle}${label}`;
});

const getBuyAmount = (item) => (item.buy_price ?? item.avg_price ?? 0) * (item.qty || 0);

const totalProfit = computed(() => {
  return props.holdings.reduce((sum, item) => sum + (item.profit || 0), 0);
});

const totalBuyAmount = computed(() => {
  return props.holdings.reduce((sum, item) => sum + getBuyAmount(item), 0);
});

const totalRatio = computed(() => {
  if (totalBuyAmount.value === 0) return 0;
  return (totalProfit.value / totalBuyAmount.value) * 100;
});

// ── 헤더 정렬 ──
const columns = [
  { key: 'name', label: '종목명', class: 'col-name' },
  { key: 'qty', label: '보유수량', class: 'col-qty' },
  { key: 'buy_price', label: '매입단가', class: 'col-buy' },
  { key: 'buy_amount', label: '매입금액', class: 'col-amount' },
  { key: 'current_price', label: '현재가', class: 'col-current' },
  { key: 'profit', label: '평가손익', class: 'col-profit' },
  { key: 'ratio', label: '수익률', class: 'col-ratio' },
];

const sortKey = ref('');
const sortDir = ref('desc');

const toggleSort = (key) => {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc';
  } else {
    sortKey.value = key;
    // 종목명은 오름차순, 숫자 컬럼은 내림차순을 기본으로 한다.
    sortDir.value = key === 'name' ? 'asc' : 'desc';
  }
};

const getSortValue = (item, key) => {
  switch (key) {
    case 'name': return item.name ?? '';
    case 'qty': return item.qty ?? 0;
    case 'buy_price': return item.buy_price ?? item.avg_price ?? 0;
    case 'buy_amount': return getBuyAmount(item);
    case 'current_price': return item.current_price ?? 0;
    case 'profit': return item.profit ?? 0;
    case 'ratio': return item.ratio ?? 0;
    default: return 0;
  }
};

const sortedHoldings = computed(() => {
  if (!sortKey.value) return props.holdings;
  const dir = sortDir.value === 'asc' ? 1 : -1;
  return [...props.holdings].sort((a, b) => {
    const va = getSortValue(a, sortKey.value);
    const vb = getSortValue(b, sortKey.value);
    if (typeof va === 'string') return va.localeCompare(vb, 'ko') * dir;
    return (va - vb) * dir;
  });
});

// ── AI 매매 전략 (종목코드 -> 전략 목록) ──
const strategies = ref({});
const expandedTicker = ref(null);
const aiProfiles = ref([]);          // AI 매매 프로파일 목록 (분석 실행용)
const selectedProfileId = ref({});   // 종목코드 -> 펼침 상태에서 보고 있는 프로파일 id
const runProfileId = ref(null);      // 분석 실행에 쓸 프로파일 id
const runningTicker = ref(null);     // 분석 실행 중인 종목코드
let strategyTimer = null;

const loadStrategies = async () => {
  strategies.value = await fetchAiTradeStrategies() || {};
};

const loadAiProfiles = async () => {
  const list = await fetchAiTrades();
  aiProfiles.value = Array.isArray(list) ? list : [];
  if (aiProfiles.value.length) {
    if (!runProfileId.value) runProfileId.value = aiProfiles.value[0].id;
    if (!batchProfileId.value) batchProfileId.value = aiProfiles.value[0].id;
    // 새로고침 시에도 진행 중인 일괄 분석을 이어서 표시
    const st = await fetchAiTradeBatchStatus(batchProfileId.value);
    if (st.running) {
      batch.value = { ...batch.value, ...st };
      pollBatch(batchProfileId.value);
    }
  }
};

onMounted(() => {
  loadStrategies();
  loadAiProfiles();
  // AI 매매에서 새 전략을 실행하면 반영되도록 주기적으로 갱신
  strategyTimer = setInterval(loadStrategies, 30000);
});
onUnmounted(() => {
  clearInterval(strategyTimer);
  clearInterval(batchTimer);
  clearTimeout(refreshTimer);
});

const strategiesFor = (item) => strategies.value[String(item.ticker)] || [];
const hasStrategy = (item) => strategiesFor(item).length > 0;

// 펼침 상태에서 현재 보고 있는 전략 (프로파일이 여러 개면 선택된 것)
const activeStrategy = (item) => {
  const list = strategiesFor(item);
  if (!list.length) return null;
  const pid = selectedProfileId.value[item.ticker];
  return list.find(s => s.profile_id === pid) || list[0];
};

const selectProfile = (item, pid) => {
  selectedProfileId.value = { ...selectedProfileId.value, [item.ticker]: pid };
};

// 분석 이력이 없는 종목도 눌러서 분석을 시작할 수 있도록 항상 펼친다
const toggleStrategy = (item) => {
  expandedTicker.value = expandedTicker.value === item.ticker ? null : item.ticker;
};

// ── 보유 종목 전체 일괄 분석 ──
const batchProfileId = ref(null);
const batch = ref({ running: false, total: 0, done: 0, current: '', errors: 0 });
let batchTimer = null;

const pollBatch = (pid) => {
  clearInterval(batchTimer);
  batchTimer = setInterval(async () => {
    const st = await fetchAiTradeBatchStatus(pid);
    batch.value = { ...batch.value, ...st };
    await loadStrategies();          // 완료된 종목부터 바로 반영
    if (!st.running) clearInterval(batchTimer);
  }, 5000);
};

const handleRunBatch = async () => {
  const pid = batchProfileId.value;
  if (!pid) {
    alert('AI 매매 프로파일이 없습니다. AI 매매 탭에서 먼저 프로파일을 만들어 주세요.');
    return;
  }
  const items = props.holdings.map(h => ({ ticker: String(h.ticker), name: h.name || '' }));
  const name = aiProfiles.value.find(p => p.id === pid)?.name || '';
  if (!confirm(`보유 종목 ${items.length}개를 '${name}' 프로파일로 분석합니다.\n`
             + `한 종목씩 순서대로 진행하며 종목당 최대 15분이 걸릴 수 있습니다.\n계속할까요?`)) {
    return;
  }
  const res = await runAiTradeBatch(pid, items);
  if (res.status === 'ERROR') {
    alert('일괄 분석 실행 실패: ' + res.message);
    return;
  }
  if (res.status === 'RUNNING') {
    alert('이미 실행 중입니다.');
  }
  batch.value = { running: true, total: items.length, done: 0, current: '', errors: 0 };
  pollBatch(pid);
};

const handleRunAnalysis = async (item) => {
  const pid = runProfileId.value;
  if (!pid) {
    alert('AI 매매 프로파일이 없습니다. AI 매매 탭에서 먼저 프로파일을 만들어 주세요.');
    return;
  }
  // 같은 종목을 재분석하면 기존 결과가 남아 있으므로, 완료 판정은
  // '결과가 생겼는지'가 아니라 '완료 시각이 바뀌었는지'로 한다
  const prev = strategiesFor(item).find(s => s.profile_id === pid);
  const prevFinishedAt = prev ? prev.finished_at : null;

  const res = await runAiTrade(pid, String(item.ticker), item.name || '');
  if (res.status === 'ERROR') {
    alert('분석 실행 실패: ' + res.message);
    return;
  }
  runningTicker.value = item.ticker;
  const started = Date.now();
  const poll = setInterval(async () => {
    await loadStrategies();
    const cur = strategiesFor(item).find(s => s.profile_id === pid);
    const done = cur && cur.finished_at !== prevFinishedAt;
    if (done || Date.now() - started > 15 * 60 * 1000) {
      clearInterval(poll);
      runningTicker.value = null;
      if (done) selectProfile(item, pid);
    }
  }, 5000);
};

const won = (v) => (typeof v === 'number' ? v.toLocaleString() + '원' : (v ?? '-'));

// ── 보유 종목 업데이트 (브로커 계좌 새로고침) ──
const refreshing = ref(false);
let refreshTimer = null;

const handleRefreshHoldings = async () => {
  if (refreshing.value) return;
  if (!confirm('증권사에서 보유 종목과 현재가를 다시 불러올까요?')) return;
  refreshing.value = true;
  const res = await refreshAccount();
  if (res.status === 'ERROR') {
    alert('업데이트 실패: ' + (res.message || '알 수 없는 오류'));
    refreshing.value = false;
    return;
  }
  // 키움은 게이트웨이 TR 조회 후 반영되므로 잠시 뒤 /status 폴링으로 갱신된다
  refreshTimer = setTimeout(() => { refreshing.value = false; }, 6000);
};

// ── 구글 시트 업로드 ('보유종목' 탭) ──
const exportingSheet = ref(false);
const gsheetUrl = ref(null);

const handleExportHoldings = async () => {
  if (exportingSheet.value) return;
  if (!confirm(`보유 종목 ${props.holdings.length}개를 구글 시트 '보유종목' 탭에 업로드할까요?\n기존 탭 내용은 덮어씁니다.`)) return;
  exportingSheet.value = true;
  gsheetUrl.value = null;
  try {
    const res = await exportHoldingsToGSheet();
    if (res.status === 'SUCCESS') {
      gsheetUrl.value = res.url || null;
      alert(`구글 시트 '${res.sheet}' 탭에 ${res.rows}종목을 업로드했습니다.`);
    } else {
      alert('업로드 실패: ' + (res.message || '알 수 없는 오류'));
    }
  } finally {
    exportingSheet.value = false;
  }
};

const riskClass = (level) => {
  if (level === '높음') return 'risk-high';
  if (level === '낮음') return 'risk-low';
  return 'risk-mid';
};

const getPriceClass = (val) => {
  if (val > 0) return 'text-up';
  if (val < 0) return 'text-down';
  return '';
};

const getRatioClass = (val) => {
  if (val > 0) return 'badge-up';
  if (val < 0) return 'badge-down';
  return 'badge-neutral';
};
</script>

<style scoped>
.holdings-container {
  width: 100%;
  padding-bottom: 2rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.holdings-content {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.account-summary-bar {
  display: flex;
  align-items: center;
  justify-content: space-around;
  padding: 1.5rem 2rem;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.03);
}

.summary-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
}

.summary-card .label {
  font-size: 0.8rem;
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.summary-card .value {
  font-size: 1.3rem;
  font-weight: 800;
  color: var(--text-main);
}

.summary-divider {
  width: 1px;
  height: 40px;
  background: rgba(255, 255, 255, 0.1);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 5rem;
  border-radius: 20px;
  color: var(--text-muted);
  animation: fadeIn 0.5s ease-out;
}

.empty-state.no-margin {
  padding: 8rem 0;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Spinner Styles */
.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(255, 255, 255, 0.1);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 1.5rem;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-icon {

  font-size: 3rem;
  margin-bottom: 1rem;
  opacity: 0.3;
}

.holdings-table-wrapper {
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.holdings-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.95rem;
  table-layout: fixed; /* 고정 레이아웃으로 열 너비 유지 */
}

.holdings-table th {
  background: rgba(255, 255, 255, 0.03);
  padding: 1rem 1.2rem;
  text-align: left;
  color: var(--text-muted);
  font-weight: 600;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.holdings-table td {
  padding: 1.2rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  transition: background 0.2s;
  vertical-align: middle;
}

/* 열 너비 설정 */
.col-name { width: 22%; }
.col-qty { width: 10%; }
.col-buy { width: 13%; }
.col-amount { width: 15%; }
.col-current { width: 13%; }
.col-profit { width: 14%; }
.col-ratio { width: 13%; }

.holdings-table th.text-right {
  text-align: right;
}

.holdings-table th.sortable {
  cursor: pointer;
  user-select: none;
  transition: color 0.2s;
}

.holdings-table th.sortable:hover {
  color: var(--text-main);
}

.holdings-table th.sortable.active {
  color: var(--primary);
}

.sort-arrow {
  display: inline-block;
  width: 0.9em;
  font-size: 0.7em;
}

.holding-row:hover td {
  background: rgba(255, 255, 255, 0.04);
}

.ticker-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  text-align: left;
}


.stock-name {
  font-weight: 700;
  color: var(--text-main);
}

.stock-ticker {
  font-size: 0.75rem;
  color: var(--text-muted);
  font-family: 'JetBrains Mono', monospace;
}

.text-right {
  text-align: right;
}

.font-medium {
  font-weight: 600;
}

.text-up { color: #ff4d4d; }
.text-down { color: #4d94ff; }

/* ── 구글 시트 업로드 ── */
.holdings-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: -0.75rem;
}
.toolbar-label { color: #4FC3F7; font-weight: 700; font-size: 0.88rem; }
.toolbar-spacer { flex: 1; }
.gsheet-btn {
  background: rgba(15, 157, 88, 0.15);
  border: 1px solid rgba(15, 157, 88, 0.5);
  color: #34A853;
  border-radius: 6px;
  padding: 6px 14px;
  cursor: pointer;
  font-size: 0.85rem;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.gsheet-btn:hover:not(:disabled) { background: rgba(15, 157, 88, 0.3); }
.gsheet-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.gsheet-link {
  font-size: 0.8rem;
  color: #34A853;
  text-decoration: none;
}
.gsheet-link:hover { text-decoration: underline; }
.spinner-sm {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(52, 168, 83, 0.3);
  border-top-color: #34A853;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── AI 매매 전략 펼침 ── */
.holding-row.clickable { cursor: pointer; }
.holding-row.open td { background: rgba(79, 195, 247, 0.06); }

.ai-badge {
  margin-left: 6px;
  font-size: 0.72rem;
  color: #4FC3F7;
  white-space: nowrap;
}
/* 분석 이력이 없는 종목은 흐리게 (클릭은 가능) */
.ai-badge.dim { opacity: 0.35; }

/* 분석 실행 바 */
.analysis-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 0.6rem 0 0.9rem;
}
.analysis-label { color: #4FC3F7; font-weight: 700; font-size: 0.88rem; }
.analysis-hint { color: var(--text-muted); font-size: 0.8rem; }
.profile-select {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: var(--text-main);
  border-radius: 6px;
  padding: 5px 10px;
  font-size: 0.82rem;
}
.run-btn {
  background: rgba(79, 195, 247, 0.15);
  border: 1px solid rgba(79, 195, 247, 0.5);
  color: #4FC3F7;
  border-radius: 6px;
  padding: 5px 14px;
  cursor: pointer;
  font-size: 0.82rem;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.run-btn:hover:not(:disabled) { background: rgba(79, 195, 247, 0.3); }
.run-btn:disabled { opacity: 0.6; cursor: not-allowed; }

/* 프로파일 선택 탭 */
.profile-tabs {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 0.7rem;
}
.profile-tab {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: var(--text-muted);
  border-radius: 999px;
  padding: 4px 14px;
  cursor: pointer;
  font-size: 0.8rem;
}
.profile-tab:hover { background: rgba(255, 255, 255, 0.1); }
.profile-tab.on {
  background: rgba(79, 195, 247, 0.18);
  border-color: rgba(79, 195, 247, 0.6);
  color: #4FC3F7;
  font-weight: 700;
}

.strategy-row td {
  background: rgba(255, 255, 255, 0.02);
  padding: 0 1rem 1rem;
}

.strategy-card {
  border: 1px solid rgba(79, 195, 247, 0.25);
  border-radius: 12px;
  padding: 1rem 1.2rem;
  background: rgba(79, 195, 247, 0.04);
}
.strategy-card + .strategy-card { margin-top: 0.8rem; }

.strategy-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 0.5rem;
}
.strategy-title { color: #4FC3F7; font-weight: 700; }
.strategy-meta { color: var(--text-muted); font-size: 0.75rem; margin-left: auto; }

.risk-chip {
  font-size: 0.72rem;
  padding: 2px 8px;
  border-radius: 999px;
}
.risk-low { background: rgba(0, 208, 132, 0.15); color: #00D084; }
.risk-mid { background: rgba(255, 193, 7, 0.15); color: #FFC107; }
.risk-high { background: rgba(255, 77, 77, 0.15); color: #FF4D4D; }

.strategy-summary {
  margin: 0 0 0.9rem;
  font-size: 0.9rem;
  line-height: 1.6;
  color: var(--text-main);
}

.strategy-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 0.6rem 1rem;
  margin-bottom: 0.9rem;
}
.strategy-metrics > div {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 0.85rem;
  border-bottom: 1px dashed rgba(255, 255, 255, 0.08);
  padding-bottom: 4px;
}
.strategy-metrics span { color: var(--text-muted); }
.c-up { color: #00D084; }
.c-down { color: #FF4D4D; }
.c-entry { color: #4FC3F7; }

.strategy-conds {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
}
.strategy-conds h5 { margin: 0 0 0.4rem; font-size: 0.82rem; }
.strategy-conds ul { margin: 0; padding-left: 1.1rem; }
.strategy-conds li {
  font-size: 0.82rem;
  line-height: 1.55;
  color: var(--text-main);
  margin-bottom: 0.25rem;
}
.text-muted { color: var(--text-muted); }

.ratio-badge {
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 0.85rem;
  font-weight: 700;
}

.ratio-badge.big {
  padding: 6px 14px;
  font-size: 1.1rem;
}

.badge-up {
  background: rgba(255, 77, 77, 0.15);
  color: #ff4d4d;
}

.badge-down {
  background: rgba(77, 148, 255, 0.15);
  color: #4d94ff;
}

.badge-neutral {
  background: rgba(255, 255, 255, 0.1);
  color: var(--text-muted);
}
</style>
