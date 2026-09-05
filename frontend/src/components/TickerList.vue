<template>
  <div class="ticker-list-container">
    <!-- Add Ticker Section -->
    <div class="add-ticker-glass glass" style="padding: 1.5rem; margin-bottom: 2rem; position: relative; z-index: 100">
      <h3 style="margin-bottom: 1.2rem; color: var(--primary); display: flex; align-items: center; gap: 8px">
        <span>➕</span> 종목 추가
      </h3>
      <div style="display: flex; gap: 15px; align-items: flex-end; flex-wrap: wrap">
        <!-- 종목 입력 -->
        <div style="display: flex; flex-direction: column; gap: 8px; flex: 1; min-width: 200px">
          <label style="font-size: 0.85rem; color: var(--text-muted)">종목명 또는 코드</label>
          <div style="position: relative; display: flex; align-items: center;">
            <input
              type="text"
              placeholder="예: 삼성전자 또는 005930"
              @keyup.enter="handleAddTicker($event)"
              v-model="tickerInput"
              style="padding: 10px; padding-right: 40px; font-size: 0.9rem; width: 100%"
            />
            <button 
              @click="handleSearch($event)"
              style="position: absolute; right: 5px; background: transparent; border: none; cursor: pointer; font-size: 1.1rem; color: var(--primary); display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; transition: transform 0.2s;"
              title="검색 및 추가"
            >
              🔍
            </button>
            <TickerSelectModal
              v-if="showSelectModal"
              :query="tickerInput"
              :results="searchResults"
              @select="onTickerSelected"
              @close="showSelectModal = false"
            />
          </div>
        </div>

        <!-- 전략 선택 -->
        <div style="display: flex; flex-direction: column; gap: 8px; flex: 1; min-width: 200px">
          <label style="font-size: 0.85rem; color: var(--text-muted)">전략</label>
          <select v-model="selectedRule" @change="handleRuleChange" style="padding: 10px; font-size: 0.9rem; width: 100%">
            <option v-for="r in rules" :key="r" :value="r">{{ r }}</option>
          </select>
        </div>

        <!-- 추가 버튼 -->
        <div style="display: flex; flex-direction: column; gap: 8px; position: relative">
          <button class="primary" @click="handleAddTicker" style="padding: 10px 25px; height: 40px; font-weight: bold">추가</button>
        </div>
      </div>
      
      <!-- 커스텀 전략 정보 -->
      <div v-if="selectedRule === 'CUSTOM'" style="margin-top: 10px; font-size: 0.8rem; color: var(--primary); cursor: pointer; display: inline-block" @click="showModal = true">
        📝 사용자 정의 전략 편집 중... (클릭하여 수정)
      </div>

      <!-- Add Confirm Modal -->
      <AddTickerConfirmModal
        v-if="pendingAddData"
        :ticker="pendingAddData.ticker"
        :name="pendingAddData.name"
        :strategy="pendingAddData.strategy"
        @confirm="onConfirmAdd"
        @cancel="pendingAddData = null"
      />

      <!-- Alert -->
      <AlertPopup
        v-if="showAlert"
        :message="alertMessage"
        :top="alertPos.top"
        :left="alertPos.left"
        @close="showAlert = false"
      />
    </div>

    <!-- Ticker List Section -->
    <div class="ticker-table-glass glass" style="padding: 1.5rem">
      <h3 style="margin-bottom: 1.2rem; display: flex; align-items: center; justify-content: space-between">
        <div style="display: flex; align-items: center; gap: 8px">
          <span>📊</span> 관심 종목
        </div>
        <div style="font-size: 0.8rem; font-weight: normal; color: var(--text-muted)">
          @ {{ tickerKeys.length }}개 종목 운용 중
        </div>
      </h3>
      <div style="overflow-x: auto">
        <table style="width: 100%; border-collapse: collapse; text-align: left">
          <thead>
            <tr style="border-bottom: 1px solid var(--border-color); color: var(--text-muted)">
              <th style="padding: 12px 10px">종목명</th>
              <th>종목코드</th>
              <th>시장/현재가</th>
              <th style="cursor: help" title="클릭하여 시작/중지">상태 ⓘ</th>
              <th>전략</th>
              <th>보유주식</th>
              <th>실현이익</th>
              <th :style="{ textAlign: 'center' }">시작/종료</th>
              <th style="text-align: center; width: 60px">분석</th>
              <th style="text-align: center; width: 60px">삭제</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="tickerKeys.length === 0">
              <td colspan="10" style="padding: 40px; text-align: center; color: var(--text-muted)">
                등록된 종목이 없습니다. 상단에서 추가해주세요.
              </td>
            </tr>
            <tr v-else v-for="t in tickerKeys" :key="t" class="ticker-row">
              <td style="padding: 15px 10px; font-weight: 500">{{ tickers[t].name || '-' }}</td>
              <td style="font-family: monospace; font-weight: bold">{{ t.split('.')[0] }}</td>
              <td>
                <div style="font-size: 0.8rem; color: var(--text-muted)">{{ tickers[t].market || '-' }}</div>
                <div style="font-size: 1rem; font-weight: bold; color: var(--primary)">
                  ₩ {{ tickers[t].price?.toLocaleString() || '0' }}
                </div>
              </td>
              <td
                :style="{
                  color: tickers[t].paused ? 'var(--danger)' : 'var(--primary)',
                  cursor: 'pointer',
                  fontWeight: 'bold',
                  userSelect: 'none'
                }"
                @click="handleToggleStatus(t, tickers[t].name, tickers[t].paused)"
                :title="tickers[t].paused ? '클릭하여 시작' : '클릭하여 중지'"
              >
                <span class="status-dot" :class="{ paused: tickers[t].paused }"></span>
                {{ tickers[t].status || (tickers[t].paused ? '일시정지' : '운용중') }}
              </td>
              <td>
                <span v-if="!tickers[t].buy_rule || tickers[t].buy_rule === 'NONE'" style="color: var(--text-muted); font-size: 0.85rem">-</span>
                <button
                  v-else
                  class="rule-badge"
                  @click="handleEdit(t, tickers[t].buy_rule)"
                >
                  {{ tickers[t].buy_rule?.length > 12 ? tickers[t].buy_rule.substring(0, 12) + '..' : tickers[t].buy_rule }}
                </button>
              </td>
              <td>
                <div v-if="tickers[t].position_qty > 0" style="font-size: 0.85rem">
                  <div style="font-weight: bold; color: var(--primary)">{{ tickers[t].position_qty }}주</div>
                  <div style="font-size: 0.75rem; color: var(--text-muted)">avg. ₩{{ tickers[t].avg_price?.toLocaleString() || '0' }}</div>
                </div>
                <span v-else style="color: var(--text-muted); font-size: 0.85rem">-</span>
              </td>
              <td :style="{
                fontWeight: 'bold',
                fontSize: '0.95rem',
                color: (tickers[t].realized_profit || 0) > 0 ? 'var(--success)' : (tickers[t].realized_profit || 0) < 0 ? 'var(--danger)' : 'var(--text-muted)'
              }">
                {{ tickers[t].realized_profit !== undefined ? `${(tickers[t].realized_profit || 0) > 0 ? '+' : ''}${(tickers[t].realized_profit || 0).toLocaleString()}원` : '-' }}
              </td>
              <td style="text-align: center">
                <div style="position: relative; display: flex; justify-content: center">
                  <button v-if="tickers[t].simulating" class="danger" style="padding: 6px 12px; font-size: 0.8rem" @click="stopSimulation(t)">⏹️ 중지</button>
                  <button v-else-if="tickers[t].market === 'VIRTUAL' || isVirtualMode" class="secondary" style="padding: 6px 12px; font-size: 0.8rem" @click="handleStartSimClick($event, t)">▶️ 시작</button>
                  <span v-else style="color: var(--text-muted); font-size: 0.75rem">실제 계좌</span>

                  <SimulationTypeModal
                    v-if="pendingSimTicker === t"
                    :ticker="t"
                    :name="tickers[t].name"
                    :top="simPos.top"
                    :left="simPos.left"
                    @select="(type) => onSimTypeSelect(t, type)"
                    @cancel="pendingSimTicker = null"
                  />
                </div>
              </td>
              <td style="text-align: center">
                <div style="position: relative; display: flex; justify-content: center">
                  <button @click="handleAnalyzeClick($event, t)" class="action-icon-btn" title="지표 분석">🔍</button>
                  <AnalysisNoticeModal
                    v-if="pendingAnalyzeTicker === t"
                    :ticker="t"
                    :name="tickers[t].name"
                    :top="analyzePos.top"
                    :left="analyzePos.left"
                    @close="pendingAnalyzeTicker = null"
                  />
                </div>
              </td>
              <td style="text-align: center">
                <div style="position: relative; display: flex; justify-content: center">
                  <button @click="handleDelete($event, t)" class="action-icon-btn delete" title="삭제">🗑️</button>
                  <DeleteTickerConfirmModal
                    v-if="pendingDeleteTicker === t"
                    :ticker="t"
                    :name="tickers[t].name"
                    :top="deletePos.top"
                    :left="deletePos.left"
                    @confirm="onConfirmDelete"
                    @cancel="pendingDeleteTicker = null"
                  />
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Common Modals -->
    <StatusConfirmModal
      v-if="confirmData"
      :ticker="confirmData.ticker"
      :name="confirmData.name"
      :is-paused="confirmData.isPaused"
      @confirm="processToggleStatus"
      @cancel="confirmData = null"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue';
import { addTicker, removeTicker, pauseTicker, resumeTicker, stopSimulation, fetchStrategies, searchCollectorTicker } from '../api';
import StatusConfirmModal from './StatusConfirmModal.vue';
import CustomRuleModal from './CustomRuleModal.vue';
import TickerSelectModal from './TickerSelectModal.vue';
import AddTickerConfirmModal from './AddTickerConfirmModal.vue';
import AlertPopup from './AlertPopup.vue';
import DeleteTickerConfirmModal from './DeleteTickerConfirmModal.vue';
import AnalysisNoticeModal from './AnalysisNoticeModal.vue';
import SimulationTypeModal from './SimulationTypeModal.vue';

const props = defineProps({
  tickers: {
    type: Object,
    default: () => ({})
  },
  status: {
    type: String,
    default: 'OFFLINE'
  }
});

const emit = defineEmits(['editRule', 'startSim', 'analyze']);

// Add Ticker Logic
const tickerInput = ref('');
const selectedRule = ref(localStorage.getItem('lastSelectedRule') || 'DEFAULT');
const customRule = ref('');
const showModal = ref(false);
const savedStrategies = ref([]);

// Ticker Search & Select Modal State
const showSelectModal = ref(false);
const searchResults = ref([]);
const pendingRule = ref('');
const pendingAddData = ref(null);

// Alert UI State
const showAlert = ref(false);
const alertMessage = ref('');
const alertPos = ref({ top: 0, left: 0 });

const showAlertPopup = (msg, event = null) => {
  alertMessage.value = msg;
  
  // 이벤트 전파 방지 및 위치 계산
  let target = null;
  if (event) {
    if (event.preventDefault) event.preventDefault();
    target = event.currentTarget || event.target;
  }

  if (target && target.getBoundingClientRect) {
    const rect = target.getBoundingClientRect();
    // 돋보기 버튼이거나 입력창일 때 위치 조정
    alertPos.value = {
      top: rect.top + rect.height / 2,
      left: rect.left - 10
    };
  } else {
    // 버튼 정보를 못 찾으면 화면 중앙
    alertPos.value = { top: undefined, left: undefined };
  }
  showAlert.value = true;
};

// Delete Ticker State
const pendingDeleteTicker = ref(null);
const deletePos = ref({ top: 0, left: 0 });

// Analyze Ticker State
const pendingAnalyzeTicker = ref(null);
const analyzePos = ref({ top: 0, left: 0 });

// Simulation Start State
const pendingSimTicker = ref(null);
const simPos = ref({ top: 0, left: 0 });

const loadSavedStrategies = async () => {
  const strats = await fetchStrategies();
  savedStrategies.value = strats.map(s => s.name);
};

// Watch for changes and save to localStorage
watch(selectedRule, (newVal) => {
  localStorage.setItem('lastSelectedRule', newVal);
});

onMounted(() => {
  loadSavedStrategies();
});

const rules = computed(() => ["없음", "DEFAULT", "GOLDEN_CROSS", "CUSTOM", ...savedStrategies.value]);

const handleSearch = async (e) => {
  if (!tickerInput.value) {
    showAlertPopup('검색할 종목명 또는 코드를 입력해주세요.', e);
    return;
  }
  
  pendingRule.value = ''; // 검색 전용으로 호출됨을 표시
  const query = tickerInput.value.trim();
  try {
    const results = await searchCollectorTicker(query);
    
    if (results.length === 0) {
      showAlertPopup(`'${query}'에 대한 검색 결과가 없습니다.`, e);
    } else if (results.length === 1) {
      // 결과가 하나면 입력필드만 종목명으로 업데이트
      tickerInput.value = results[0].name;
    } else {
      // 결과가 여러 개면 선택 팝업 표시
      searchResults.value = results;
      showSelectModal.value = true;
    }
  } catch (error) {
    console.error("Search failed:", error);
    showAlertPopup("검색 중 오류가 발생했습니다.", e);
  }
};

const handleAddTicker = async (e) => {
  if (!tickerInput.value) {
    showAlertPopup('종목명 또는 종목코드를 입력해주세요.', e);
    return;
  }

  const query = tickerInput.value.trim();
  const ruleToSend = selectedRule.value === 'CUSTOM' ? customRule.value : (selectedRule.value === '없음' ? 'NONE' : selectedRule.value);

  // 중복 체크 함수
  const isAlreadyExists = (t) => {
    const normalized = t.includes('.') ? t.split('.')[0] : t;
    return Object.keys(props.tickers).some(existing => 
      existing === normalized || existing.split('.')[0] === normalized
    );
  };

  // 1. 이미 규격에 맞는 티커인 경우 (.KS, .KQ 등) 바로 추가
  if (query.includes('.') || /^\d{6}$/.test(query)) {
    if (isAlreadyExists(query)) {
      showAlertPopup('이미 존재하는 종목입니다.', e);
      return;
    }
    pendingAddData.value = {
      ticker: query,
      name: query,
      strategy: ruleToSend
    };
    return;
  }

  // 2. 종목명으로 판단되는 경우 검색 시도
  try {
    const results = await searchCollectorTicker(query);
    if (results.length === 0) {
      showAlertPopup(`'${query}'에 대한 검색 결과가 없습니다.`, e);
    } else {
      // 2-1. 정교한 이름 매칭 (공백 무시, 대소문자 무시)
      const normalize = (s) => s ? s.replace(/\s+/g, '').toUpperCase() : '';
      const qNorm = normalize(query);
      
      const exactMatch = results.find(r => 
        normalize(r.name) === qNorm || 
        r.ticker.split('.')[0] === query ||
        normalize(r.ticker) === qNorm
      );

      if (exactMatch) {
        if (isAlreadyExists(exactMatch.ticker)) {
          showAlertPopup('이미 존재하는 종목입니다.', e);
          return;
        }
        showSelectModal.value = false;
        pendingAddData.value = {
          ticker: exactMatch.ticker,
          name: exactMatch.name,
          strategy: ruleToSend
        };
        return;
      }

      // 2-2. 결과가 하나뿐인 경우
      if (results.length === 1) {
        const targetTicker = results[0].ticker;
        if (isAlreadyExists(targetTicker)) {
          showAlertPopup('이미 존재하는 종목입니다.', e);
          return;
        }
        showSelectModal.value = false;
        pendingAddData.value = {
          ticker: targetTicker,
          name: results[0].name,
          strategy: ruleToSend
        };
      } else {
        // 2-3. 여러 개면 선택 팝업 표시
        searchResults.value = results;
        pendingRule.value = ruleToSend;
        showSelectModal.value = true;
      }
    }
  } catch (error) {
    console.error("Add ticker failed during search:", error);
  }
};

const onConfirmAdd = async () => {
  if (pendingAddData.value) {
    await processAddTicker(pendingAddData.value.ticker, pendingAddData.value.strategy);
    pendingAddData.value = null;
  }
};

const onConfirmDelete = async () => {
  if (pendingDeleteTicker.value) {
    await removeTicker(pendingDeleteTicker.value);
    pendingDeleteTicker.value = null;
  }
};

const processAddTicker = async (ticker, rule) => {
  try {
    await addTicker(ticker, rule);
    tickerInput.value = '';
    customRule.value = '';
    showSelectModal.value = false;
  } catch (error) {
    console.error("Add ticker failed:", error);
    showAlertPopup("종목 추가 중 오류가 발생했습니다.");
  }
};

const onTickerSelected = (item) => {
  // 입력창 업데이트
  tickerInput.value = item.name;
  showSelectModal.value = false;

  // '추가' 버튼을 통해 검색된 것이라면 즉시 추가 확인 단계로 진입
  if (pendingRule.value) {
    // 중복 체크
    const normalized = item.ticker.split('.')[0];
    const exists = Object.keys(props.tickers).some(existing => 
      existing === normalized || existing.split('.')[0] === normalized
    );

    if (exists) {
      showAlertPopup('이미 존재하는 종목입니다.');
    } else {
      pendingAddData.value = {
        ticker: item.ticker,
        name: item.name,
        strategy: pendingRule.value
      };
    }
    pendingRule.value = ''; // 상태 초기화
  }
};

const handleRuleChange = (e) => {
  const val = e.target.value;
  if (val === 'CUSTOM') {
    showModal.value = true;
  }
};

const onCustomRuleSave = (rule) => {
  customRule.value = rule;
  showModal.value = false;
};

const onCustomRuleClose = () => {
  if (!customRule.value) selectedRule.value = 'DEFAULT';
  showModal.value = false;
};

// Existing Ticker List Logic
const confirmData = ref(null);

const handleDelete = (e, t) => {
  const rect = e.currentTarget.getBoundingClientRect();
  deletePos.value = {
    top: rect.top + rect.height / 2,
    left: rect.left - 10
  };
  pendingDeleteTicker.value = t;
};

const handleEdit = async (t, rule) => {
  await pauseTicker(t);
  emit('editRule', t, rule);
};

const handleAnalyzeClick = (e, t) => {
  const tickerData = props.tickers[t];
  const isStarted = tickerData.market === 'REAL' ? !tickerData.paused : tickerData.simulating;

  if (!isStarted) {
    const rect = e.currentTarget.getBoundingClientRect();
    analyzePos.value = {
      top: rect.top + rect.height / 2,
      left: rect.left - 10
    };
    pendingAnalyzeTicker.value = t;
    return;
  }
  
  emit('analyze', t);
};

const handleToggleStatus = (t, name, isPaused) => {
  confirmData.value = { ticker: t, name, isPaused };
};

const handleStartSimClick = (e, t) => {
  const rect = e.currentTarget.getBoundingClientRect();
  simPos.value = {
    top: rect.top + rect.height / 2,
    left: rect.left - 10
  };
  pendingSimTicker.value = t;
};

const onSimTypeSelect = (ticker, type) => {
  emit('startSim', { ticker, type });
  pendingSimTicker.value = null;
};

const processToggleStatus = async () => {
  if (!confirmData.value) return;
  const { ticker, isPaused } = confirmData.value;
  if (isPaused) {
    await resumeTicker(ticker);
  } else {
    await pauseTicker(ticker);
  }
  confirmData.value = null;
};

const tickerKeys = computed(() => {
  const keys = Object.keys(props.tickers || {});
  return keys.sort((a, b) => {
    const nameA = props.tickers[a].name || a;
    const nameB = props.tickers[b].name || b;
    return nameA.localeCompare(nameB, 'ko', { sensitivity: 'base' });
  });
});
const isVirtualMode = computed(() => props.status?.includes('VIRTUAL'));
</script>

<style scoped>
.ticker-list-container {
  margin-top: 2rem;
  animation: fadeIn 0.4s ease-out;
}

.ticker-row {
  border-bottom: 1px solid var(--border-color);
  transition: background 0.2s;
}

.ticker-row:hover {
  background: rgba(255, 255, 255, 0.02);
}

.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--primary);
  margin-right: 6px;
  box-shadow: 0 0 8px var(--primary);
}

.status-dot.paused {
  background: var(--danger);
  box-shadow: 0 0 8px var(--danger);
}

.rule-badge {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-color);
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 0.8rem;
  color: var(--text-main);
  cursor: pointer;
  transition: all 0.2s;
}

.rule-badge:hover {
  border-color: var(--primary);
  background: rgba(0, 255, 136, 0.05);
}

.action-icon-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 1.1rem;
  padding: 8px;
  border-radius: 50%;
  transition: all 0.2s;
}

.action-icon-btn:hover {
  background: rgba(255, 255, 255, 0.05);
  transform: scale(1.1);
}

.action-icon-btn.delete:hover {
  background: rgba(255, 77, 77, 0.1);
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
```
