<template>
  <div class="data-panel-container" style="display: flex; height: 100%; gap: 1px; background: rgba(255, 255, 255, 0.05)">
    <!-- Left: Hierarchical Menu -->
    <div class="data-sidebar glass" style="width: 280px; min-width: 280px; padding: 20px; overflow-y: auto; border-right: 1px solid rgba(255, 255, 255, 0.05)">

      <div class="menu-container">
        <template v-for="menu in menuData" :key="menu.name">
          <MenuItem :item="menu" @action="handleMenuAction" />
        </template>
      </div>
    </div>

    <!-- Right: Content Area -->
    <div class="data-content glass" style="flex: 1; padding: 2.5rem; overflow-y: auto; display: flex; flex-direction: column; gap: 2rem">
      <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid var(--primary); padding-bottom: 1rem">
        <h2 style="color: var(--primary); margin: 0; display: flex; align-items: center; gap: 12px">
          <span style="font-size: 1.8rem">📦</span> {{ selectedMenuName || '데이터 관리 센터' }}
        </h2>
        <div style="text-align: right">
          <div style="font-size: 0.9rem; color: var(--text-main); font-weight: 600">서버 데이터베이스 상태</div>
          <div style="font-size: 0.8rem; color: var(--primary)">● 정상 작동 중</div>
        </div>
      </div>

      <!-- Overview Cards (Default View) -->
      <div v-if="!selectedMenuName" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem">
        <!-- Price Data -->
        <div class="data-card">
          <div class="card-header">
            <span class="icon">📈</span>
            <h3>시세 데이터</h3>
          </div>
          <div class="card-body">
            <div class="stat-row">
              <span>총 보관 종목</span>
              <span class="value">12개</span>
            </div>
            <div class="stat-row">
              <span>데이터 용량</span>
              <span class="value">45.2 MB</span>
            </div>
            <div class="stat-row">
              <span>가상 데이터 세트</span>
              <span class="value">3개</span>
            </div>
          </div>
          <button class="primary" style="width: 100%; margin-top: 1rem">시세 데이터 브라우저</button>
        </div>

        <!-- Trading Data -->
        <div class="data-card">
          <div class="card-header" style="--card-color: var(--secondary)">
            <span class="icon">💰</span>
            <h3>매매 및 전략 데이터</h3>
          </div>
          <div class="card-body">
            <div class="stat-row">
              <span>누적 매매 기록</span>
              <span class="value">856건</span>
            </div>
            <div class="stat-row">
              <span>저장된 전략 결과</span>
              <span class="value">12건</span>
            </div>
            <div class="stat-row">
              <span>가상 시뮬레이션 결과</span>
              <span class="value">8건</span>
            </div>
          </div>
          <button style="width: 100%; margin-top: 1rem; background-color: var(--secondary)">통계 분석 리포트</button>
        </div>

        <!-- System Logs -->
        <div class="data-card">
          <div class="card-header" style="--card-color: var(--accent)">
            <span class="icon">📜</span>
            <h3>동기화 및 이력</h3>
          </div>
          <div class="card-body">
            <div class="stat-row">
              <span>최근 동기화</span>
              <span class="value">10분 전</span>
            </div>
            <div class="stat-row">
              <span>API 호출 횟수 (오늘)</span>
              <span class="value">2,450회</span>
            </div>
            <div class="stat-row">
              <span>무결성 검증</span>
              <span class="value" style="color: var(--primary)">PASS</span>
            </div>
          </div>
          <button style="width: 100%; margin-top: 1rem; background-color: var(--accent)">데이터 로그 뷰어</button>
        </div>
      </div>

      <!-- Content Area -->
      <div v-else style="flex: 1; padding: 0.5rem; overflow: hidden; display: flex; flex-direction: column">
        <!-- Analysis Loading State -->
        <div v-if="isAnalyzing" style="flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2rem; background: rgba(0,0,0,0.3); border-radius: 20px; margin: 2rem">
          <div class="analysis-spinner"></div>
          <div style="text-align: center">
            <h3 style="color: var(--primary); margin: 0 0 10px 0; font-size: 1.5rem">📊 전략 분석 중...</h3>
            <p style="color: var(--text-muted); margin: 0 0 1.5rem 0">선택한 전략들의 성과를 백테스트 엔진에서 계산하고 있습니다.</p>
            
            <!-- Progress Logs -->
            <div ref="analysisLogsRef" class="analysis-logs glass">
              <div v-for="(log, idx) in progressLogs" :key="idx" class="analysis-log-item">
                <span class="dot"></span> {{ log }}
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="isSimulationTool && !simulatingTicker && !analysisResult" style="flex: 1; display: flex; flex-direction: column; justify-content: center; padding: 2rem; overflow-y: auto">
          <SimulationSettings 
            :tickers="tickers"
            :initialTicker="forcedTicker"
            :show-simulation-button="!isBacktest"
            :show-analyze-button="!hideAnalyze"
            @start="handleStartSimulation"
            @analyze="handleAnalyzeSimulation"
            @close="handleCloseSettings"
          />
        </div>

        <!-- Analysis Report View (Multi-Strategy) -->
        <div v-else-if="analysisResult" style="flex: 1; display: flex; flex-direction: column; padding: 1.5rem; overflow-y: auto">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem">
            <h3 style="display: flex; align-items: center; gap: 10px; margin: 0">
              📊 시뮬레이션 분석 리포트 (전략 비교)
              <span v-if="analysisResult.config?.slippage_enabled" style="font-size: 0.75rem; background: rgba(255,107,107,0.2); color: #ff6b6b; padding: 4px 10px; border-radius: 4px; border: 1px solid rgba(255,107,107,0.3)">
                🚨 슬리피지 반영됨 ({{ analysisResult.config.slippage_rate_pct }}%)
              </span>
            </h3>
            <button @click="analysisResult = null" style="background: rgba(255,255,255,0.1); padding: 8px 16px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.1); color: white; cursor: pointer">뒤로 가기</button>
          </div>
          
          <!-- Summary Table -->
          <div style="overflow-x: auto; margin-bottom: 2rem; background: rgba(0,0,0,0.2); border-radius: 12px; border: 1px solid rgba(255,255,255,0.05)">
            <table style="width: 100%; border-collapse: collapse; text-align: left">
              <thead>
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.1); color: var(--text-muted); font-size: 0.85rem">
                  <th style="padding: 12px 20px">전략명</th>
                  <th style="padding: 12px 20px">자산 수익률</th>
                  <th style="padding: 12px 20px">실현 손익(총)</th>
                  <th style="padding: 12px 20px">세금/수수료</th>
                  <th style="padding: 12px 20px">순 손익(최종)</th>
                  <th style="padding: 12px 20px">종목 수익률</th>
                  <th style="padding: 12px 20px">최대 낙폭 (MDD)</th>
                  <th style="padding: 12px 20px">총 매매</th>
                  <th style="padding: 12px 20px">최종 자산</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(sum, name) in analysisResult.summaries" :key="name" style="border-bottom: 1px solid rgba(255,255,255,0.05)">
                  <td style="padding: 12px 20px; font-weight: bold; color: var(--primary)">{{ name }}</td>
                  <td style="padding: 12px 20px" :style="{ color: sum.portfolio_return >= 0 ? '#ff6b6b' : '#4dabf7' }">
                    {{ sum.portfolio_return.toFixed(2) }}%
                  </td>
                  <td style="padding: 12px 20px" :style="{ color: (sum.gross_pnl || sum.realized_pnl) >= 0 ? '#ff6b6b' : '#4dabf7' }">
                    {{ Math.round(sum.gross_pnl || sum.realized_pnl || 0).toLocaleString() }}원
                  </td>
                  <td style="padding: 12px 20px; color: #adb5bd">
                    -{{ Math.round(sum.total_fees || 0).toLocaleString() }}원
                  </td>
                  <td style="padding: 12px 20px" :style="{ color: sum.realized_pnl >= 0 ? '#ff6b6b' : '#4dabf7' }">
                    {{ Math.round(sum.realized_pnl || 0).toLocaleString() }}원
                  </td>
                  <td style="padding: 12px 20px" :style="{ color: sum.profit_rate >= 0 ? '#ff6b6b' : '#4dabf7' }">
                    {{ sum.profit_rate.toFixed(2) }}%
                  </td>
                  <td style="padding: 12px 20px; color: #ff6b6b">{{ sum.max_drawdown.toFixed(2) }}%</td>
                  <td style="padding: 12px 20px">{{ sum.total_trades }}회</td>
                  <td style="padding: 12px 20px">{{ Math.round(sum.final_value).toLocaleString() }}원</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div style="flex: 1; background: rgba(0,0,0,0.2); border-radius: 12px; overflow: hidden; border: 1px solid rgba(255,255,255,0.05)">
            <TickChart 
              :comparison-data="analysisResult.comparisons" 
              :base-data="analysisResult.base_chart"
              :trade-data="analysisResult.details"
            />
          </div>
        </div>

        <!-- Real-time Simulation View -->
        <div v-else-if="simulatingTicker" style="flex: 1; display: flex; flex-direction: column; gap: 1.5rem; padding: 1rem">
          <div style="display: flex; justify-content: space-between; align-items: center">
            <h3 style="margin: 0">🖥️ 실시간 시뮬레이션: {{ simulatingTicker }}</h3>
            <button @click="handleStopSimulation" class="danger" style="padding: 8px 16px">시뮬레이션 중지</button>
          </div>
          <div style="flex: 1; min-height: 400px; background: rgba(0,0,0,0.2); border-radius: 12px; overflow: hidden">
            <TickChart :ticker="simulatingTicker" />
          </div>
        </div>

        <!-- Collector Panel View -->
        <div v-else-if="selectedMenuName === 'API에서 가져오기'" style="flex: 1; overflow-y: auto">
          <CollectorPanel ref="collectorPanelRef" />
        </div>

        <!-- Ticker Data Viewer (종목별 조회) -->
        <div v-else-if="selectedMenuName === '종목별 조회'" style="flex: 1; overflow-y: auto">
          <TickerDataViewer 
            viewMode="ticker"
            :initial-ticker="viewerHandover?.ticker" 
            :initial-date="viewerHandover?.date" 
            @mounted="viewerHandover = null"
            @data-deleted="handleDataDeleted"
          />
        </div>

        <!-- Ticker Data Viewer (날짜별 조회) -->
        <div v-else-if="selectedMenuName === '날짜별 조회'" style="flex: 1; overflow-y: auto">
          <TickerDataViewer 
            viewMode="date"
            :initial-ticker="viewerHandover?.ticker" 
            :initial-date="viewerHandover?.date" 
            @mounted="viewerHandover = null"
            @data-deleted="handleDataDeleted"
          />
        </div>

        <!-- File Import Panel -->
        <div v-else-if="selectedMenuName === '파일에서 가져오기 (CSV)'" style="flex: 1; overflow-y: auto">
          <FileImportPanel 
            :initial-ticker="viewerHandover?.ticker"
            @cancel="selectedMenuName = ''" 
            @imported="(res) => {
              viewerHandover = { ticker: res.ticker };
              selectedMenuName = '종목별 조회';
            }"
          />
        </div>

        <!-- Backtest Execution View -->
        <div v-else-if="selectedMenuName === '기존 데이터 기반' && isBacktest" style="flex: 1; overflow-y: auto">
          <BacktestForm 
            @backtest="handleAnalyzeSimulation"
            @cancel="selectedMenuName = ''"
          />
        </div>

        <!-- Dual Backtest Execution View -->
        <div v-else-if="selectedMenuName === '듀얼 데이터 기반'" style="flex: 1; overflow-y: auto">
          <DualBacktestForm 
            :tickers="tickers"
            @close="selectedMenuName = ''"
          />
        </div>

        <!-- Backtest History View -->
        <div v-else-if="selectedMenuName === '조회' && !['시세 데이터', '매매 데이터'].includes(itemParentName)" style="flex: 1; overflow-y: auto">
          <BacktestHistory 
            @view-detail="(res) => {
              analysisResult = res;
            }"
          />
        </div>

        <div v-else-if="reconstructionTriggers.includes(selectedMenuName) && !isBacktest" style="flex: 1; overflow-y: auto">
          <TickGenerationForm 
            :ticker="forcedTicker"
            :mode="selectedMenuName === '기존 데이터 기반' ? 'REALISTIC' : 'SIMPLE'"
            :show-simulation-button="!isGeneratorOnly"
            :show-generator-button="!hideGenerator"
            @start="({ ticker }) => simulatingTicker = ticker"
            @generated="(res) => {
              viewerHandover = { ticker: res.ticker, date: res.selectedDate };
              selectedMenuName = '종목별 조회';
            }"
            @cancel="selectedMenuName = ''"
          />
        </div>

        <!-- Default Placeholder for other implementations -->
        <div v-else style="flex: 1; display: flex; align-items: center; justify-content: center; color: var(--text-muted); border: 1px dashed rgba(255,255,255,0.1); border-radius: 12px; margin: 2rem">
          <div style="text-align: center">
            <h3>{{ selectedMenuName }}</h3>
            <p>해당 기능은 현재 구현 준비 중입니다.</p>
          </div>
        </div>
      </div>

      <!-- Quick Tool Footer -->
      <div style="margin-top: auto; padding: 1.5rem; background: rgba(255, 255, 255, 0.03); border-radius: 12px; border: 1px dashed rgba(255, 255, 255, 0.1)">
        <h4 style="margin: 0 0 1rem 0; font-size: 0.9rem; color: var(--text-muted)">⚡ 빠른 도구</h4>
        <div style="display: flex; gap: 1rem; flex-wrap: wrap">
          <button 
            v-for="tool in recentTools" 
            :key="tool" 
            class="small-tool"
            @click="handleMenuAction(tool)"
            @contextmenu.prevent="handleContextMenu($event, tool)"
          >
            {{ tool }}
          </button>
        </div>
      </div>
    </div>

    <!-- Right-click Context Menu (Optional/Removed in favor of Modal) -->
    <!-- We can either keep the menu or open modal directly. User asked for "삭제 팝업" on right-click. -->
    
    <!-- Localized Delete Popup -->
    <Teleport to="body">
      <div v-if="deleteModal.show" ref="deleteModalRef" class="localized-delete-popup glass" :style="{ top: deleteModal.y + 'px', left: deleteModal.x + 'px' }">
        <div class="popup-header">
          삭제 확인
        </div>
        <div class="popup-body">
          '{{ deleteModal.tool }}' 항목을 삭제할까요?
        </div>
        <div class="popup-footer">
          <button class="popup-btn cancel" @click="cancelDelete">취소</button>
          <button class="popup-btn confirm" @click="confirmDelete">삭제</button>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, defineComponent, h, onMounted, onUnmounted, computed, nextTick, watch } from 'vue';
import SimulationSettings from './SimulationSettings.vue';
import BacktestForm from './BacktestForm.vue';
import BacktestHistory from './BacktestHistory.vue';
import DualBacktestForm from './DualBacktestForm.vue';
import TickChart from './TickChart.vue';
import CollectorPanel from './CollectorPanel.vue';
import TickerDataViewer from './TickerDataViewer.vue';
import TickGenerationForm from './TickGenerationForm.vue';
import FileImportPanel from './FileImportPanel.vue';
import { startSimulation, stopSimulation, analyzeSimulation } from '../api';

const props = defineProps({
  tickers: {
    type: Object,
    default: () => ({})
  },
  handover: {
    type: Object,
    default: null
  }
});

const emit = defineEmits(['handover-processed']);

// Recursive MenuItem Component
const MenuItem = defineComponent({
  name: 'MenuItem',
  props: ['item'],
  emits: ['action'],
  setup(props, { emit }) {
    const isOpen = ref(props.item.open || false);

    const handleClick = () => {
      if (props.item.children) {
        isOpen.value = !isOpen.value;
      } else {
        // Find parent name if possible
        emit('action', props.item);
      }
    };

    return () => h('div', { class: 'menu-node' }, [
      h('div', { 
        class: ['menu-item', { active: isOpen.value && props.item.children }],
        onClick: handleClick
      }, [
        props.item.children ? h('span', { class: ['menu-toggle', { open: isOpen.value }] }, '▶') : h('span', { style: 'width: 12px' }),
        props.item.icon ? h('span', { style: 'margin-right: 4px' }, props.item.icon) : null,
        h('span', props.item.name)
      ]),
      (isOpen.value && props.item.children) ? h('div', { class: 'menu-children' }, 
        props.item.children.map(child => h(MenuItem, { 
          item: child, 
          onAction: (item) => emit('action', item) 
        }))
      ) : null
    ]);
  }
});

// No emits needed here anymore

const selectedMenuName = ref('');
const itemParentName = ref('');
const isGeneratorOnly = ref(false);
const isBacktest = ref(false);
const hideGenerator = ref(false);
const hideAnalyze = ref(false);
const recentTools = ref([]);
const deleteModalRef = ref(null);
const collectorPanelRef = ref(null);
const simulatingTicker = ref('');
const analysisResult = ref(null);
const isAnalyzing = ref(false);
const progressLogs = ref([]);
const analysisLogsRef = ref(null);
const viewerHandover = ref(null);
const forcedTicker = ref(null);
let analysisWS = null;

watch(() => props.handover, (newHandover) => {
  if (newHandover) {
    selectedMenuName.value = newHandover.type;
    forcedTicker.value = newHandover.ticker;
    
    // Set operation flags based on handover type
    if (newHandover.type === '기존 데이터 기반') {
      hideGenerator.value = true;
      hideAnalyze.value = false;
      isBacktest.value = false;
    }
    
    // If it's a simulation/generation tool, wait for next tick and set the ticker
    nextTick(() => {
      if (newHandover.ticker) {
        if (reconstructionTriggers.includes(newHandover.type)) {
          // Handover for TickGenerationForm is handled by its internal loadState usually, 
          // but we might need to force it if it's already mounted or via local storage
          localStorage.setItem('tick_gen_form_state', JSON.stringify({
            ...JSON.parse(localStorage.getItem('tick_gen_form_state') || '{}'),
            ticker: newHandover.ticker
          }));
        } else if (simulationTriggers.includes(newHandover.type)) {
          localStorage.setItem('lastSelectedTicker', newHandover.ticker);
        }
      }
      emit('handover-processed');
    });
  }
}, { immediate: true });

const handleDataDeleted = () => {
  // CollectorPanel의 달력을 새로고침
  if (collectorPanelRef.value && typeof collectorPanelRef.value.refreshCalendar === 'function') {
    collectorPanelRef.value.refreshCalendar();
  }
};

const initAnalysisWS = () => {
  if (analysisWS) return;
  analysisWS = new WebSocket('ws://' + window.location.hostname + ':8765');
  analysisWS.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.type === 'analysis_progress') {
      progressLogs.value.push(message.data);
      // Keep only last 50 logs for display
      if (progressLogs.value.length > 50) progressLogs.value.shift();
      
      // Auto-scroll to bottom
      nextTick(() => {
        if (analysisLogsRef.value) {
          analysisLogsRef.value.scrollTop = analysisLogsRef.value.scrollHeight;
        }
      });
    }
  };
  analysisWS.onclose = () => {
    analysisWS = null;
    // Reconnect after 3 seconds if needed
    setTimeout(initAnalysisWS, 3000);
  };
};
const deleteModal = reactive({
  show: false,
  tool: null,
  x: 0,
  y: 0
});

const saveRecentTools = () => {
  localStorage.setItem('recentTools', JSON.stringify(recentTools.value));
};

const handleContextMenu = (event, tool) => {
  const popupWidth = 200;
  const popupHeight = 160; // Estimated height including padding and buttons
  
  let x = event.clientX;
  let y = event.clientY;

  // Horizontal check
  if (x + popupWidth > window.innerWidth) {
    x = x - popupWidth;
  }

  // Vertical check
  if (y + popupHeight > window.innerHeight) {
    y = y - popupHeight;
  }

  deleteModal.tool = tool;
  deleteModal.x = x;
  deleteModal.y = y;
  deleteModal.show = true;
};


const cancelDelete = () => {
  deleteModal.show = false;
  deleteModal.tool = null;
};

const confirmDelete = () => {
  if (deleteModal.tool) {
    recentTools.value = recentTools.value.filter(t => t !== deleteModal.tool);
    saveRecentTools();
  }
  cancelDelete();
};

const closeOnOutsideClick = (event) => {
  if (deleteModal.show && deleteModalRef.value && !deleteModalRef.value.contains(event.target)) {
    cancelDelete();
  }
};

onMounted(() => {
  initAnalysisWS();
  window.addEventListener('click', closeOnOutsideClick);
  const saved = localStorage.getItem('recentTools');
  if (saved) {
    try {
      const parsed = JSON.parse(saved);
      const unwanted = ['DB 백업', '캐시 최적화', '무결성 검사 실행', '가상 데이터 초기화'];
      recentTools.value = parsed.filter(t => !unwanted.includes(t));
      saveRecentTools();
    } catch (e) {
      console.error("Failed to parse saved tools", e);
    }
  }
});

onUnmounted(() => {
  if (analysisWS) {
    analysisWS.onclose = null;
    analysisWS.close();
  }
  window.removeEventListener('click', closeOnOutsideClick);
});

const menuData = ref([
  {
    name: '시세 데이터',
    open: false,
    children: [
      {
        name: '가져오기',
        children: [
          { name: '파일에서 가져오기 (CSV)' },
          { 
            name: 'API에서 가져오기'
          }
        ]
      },
      {
        name: '가상',
        children: [
          { name: '기존 데이터 기반', generatorOnly: true }
        ]
      },
      { 
        name: '조회',
        children: [
          { name: '종목별 조회' },
          { name: '날짜별 조회' }
        ]
      }
    ]
  },
  {
    name: '매매 데이터',
    children: [
      { 
        name: '가져오기',
        children: [
          { name: '파일에서 가져오기' },
          { name: '전략 결과에서 생성' },
          { 
            name: '가상 매매',
            children: [
              { name: '가상 시세 기반 생성' },
              { name: '랜덤 매매 생성' }
            ]
          }
        ]
      },
      { 
        name: '조회',
        children: [
          { name: '매수 / 매도 내역' },
          { name: '전략별 조회' },
          { name: '날짜별 조회' },
          { name: '가상 매매' },
          { name: '매매 요약' }
        ]
      },
      { 
        name: '통계',
        children: [
          { name: '손익 분석' },
          { name: '승률' },
          { name: '최대 낙폭' },
          { name: '매매 횟수' }
        ]
      }
    ]
  },
  {
    name: '백테스트',
    children: [
      { 
        name: '실행',
        children: [
          { name: '기존 데이터 기반', isBacktest: true },
          { name: '랜덤 데이터', isBacktest: true },
          { name: '듀얼 데이터 기반', isBacktest: true }
        ]
      },
      { name: '조회' }
    ]
  },
  {
    name: '시뮬레이션',
    children: [
      { name: '기존 데이터 기반', hideGenerator: true },
      { name: '랜덤 데이터', hideAnalyze: true }
    ]
  }
]);

const simulationTriggers = [
  '랜덤 데이터'
];

const reconstructionTriggers = [
  '기존 데이터 기반'
];

const isSimulationTool = computed(() => {
  if (!selectedMenuName.value) return false;
  const current = selectedMenuName.value.trim();
  return simulationTriggers.some(trigger => trigger.trim() === current);
});

const handleMenuAction = (item) => {
  const name = typeof item === 'string' ? item : item.name;
  selectedMenuName.value = name;
  isGeneratorOnly.value = item.generatorOnly || false;
  isBacktest.value = item.isBacktest || false;
  hideGenerator.value = item.hideGenerator || false;
  hideAnalyze.value = item.hideAnalyze || false;
  simulatingTicker.value = ''; // Reset simulation view when changing menu
  analysisResult.value = null; // Reset analysis report when changing menu
  
  // Update Recent Tools: add to front, ensure unique, limit to 6
  const updated = [name, ...recentTools.value.filter(t => t !== name)];
  recentTools.value = updated.slice(0, 6);
  saveRecentTools();
};

const handleStartSimulation = async ({ ticker, config }) => {
  const result = await startSimulation(ticker.value || ticker, config.value || config);
  if (result && result.status === 'STARTED') {
    simulatingTicker.value = ticker.value || ticker;
    // alert(`시뮬레이션이 시작되었습니다: ${simulatingTicker.value}`);
  } else {
    alert(`시뮬레이션 시작 실패: ${result?.status || 'Unknown error'}`);
  }
};

const handleAnalyzeSimulation = async ({ ticker, config }) => {
  isAnalyzing.value = true;
  progressLogs.value = ["분석 준비 중..."];
  try {
    const result = await analyzeSimulation(ticker.value || ticker, config.value || config);
    if (result && result.status === 'SUCCESS') {
      analysisResult.value = result;
    } else {
      alert('분석에 실패했습니다.');
    }
  } finally {
    isAnalyzing.value = false;
  }
};

const handleStopSimulation = async () => {
  if (!simulatingTicker.value) return;
  await stopSimulation(simulatingTicker.value);
  simulatingTicker.value = '';
  alert('시뮬레이션이 중지되었습니다.');
};

const handleCloseSettings = () => {
  selectedMenuName.value = '';
};
</script>

<style scoped>
.analysis-spinner {
  width: 60px;
  height: 60px;
  border: 4px solid rgba(0, 255, 149, 0.1);
  border-left-color: var(--primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.analysis-logs {
  background: rgba(0, 0, 0, 0.4);
  padding: 1rem;
  border-radius: 12px;
  width: 400px;
  max-width: 90vw;
  height: 200px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  border: 1px solid rgba(255, 255, 255, 0.05);
  text-align: left;
}

.analysis-log-item {
  font-family: 'Fira Code', monospace;
  font-size: 0.85rem;
  color: #adb5bd;
  display: flex;
  align-items: center;
  gap: 10px;
  animation: logFadeIn 0.3s ease-out;
}

.analysis-log-item .dot {
  width: 6px;
  height: 6px;
  background: var(--primary);
  border-radius: 50%;
  box-shadow: 0 0 8px var(--primary);
}

@keyframes logFadeIn {
  from { opacity: 0; transform: translateX(-10px); }
  to { opacity: 1; transform: translateX(0); }
}

.data-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 16px;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.stat-card {
  background: rgba(255, 255, 255, 0.05);
  padding: 1rem;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-card .label {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.stat-card .value {
  font-size: 1.25rem;
  font-weight: bold;
}

.data-card:hover {
  transform: translateY(-5px);
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.1);
  box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 1.5rem;
}

.card-header .icon {
  font-size: 1.5rem;
  background: rgba(255, 255, 255, 0.05);
  width: 45px;
  height: 45px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
}

.card-header h3 {
  margin: 0;
  font-size: 1.15rem;
  color: var(--card-color, var(--primary));
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.stat-row .value {
  color: var(--text-main);
  font-weight: 600;
}

.small-tool {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 6px 14px;
  font-size: 0.8rem;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.small-tool:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: var(--primary);
  color: var(--primary);
}

.localized-delete-popup {
  position: fixed;
  width: 200px;
  background: rgba(30, 30, 45, 0.98);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 12px;
  padding: 0;
  z-index: 10000;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
  animation: popupFadeIn 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

@keyframes popupFadeIn {
  from { opacity: 0; transform: scale(0.95) translateY(-5px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

.popup-header {
  padding: 8px 12px;
  font-size: 0.75rem;
  font-weight: bold;
  color: var(--text-muted);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  background: rgba(255, 255, 255, 0.02);
}

.popup-body {
  padding: 12px;
  font-size: 0.85rem;
  line-height: 1.4;
  color: var(--text-main);
}

.popup-footer {
  display: flex;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.popup-btn {
  flex: 1;
  border: none;
  background: transparent;
  padding: 10px;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.2s;
  color: var(--text-muted);
}

.popup-btn:first-child {
  border-right: 1px solid rgba(255, 255, 255, 0.05);
}

.popup-btn:hover {
  background: rgba(255, 255, 255, 0.05);
}

.popup-btn.confirm {
  color: #ff6b6b;
  font-weight: bold;
}

.popup-btn.confirm:hover {
  background: rgba(255, 107, 107, 0.1);
}
</style>
