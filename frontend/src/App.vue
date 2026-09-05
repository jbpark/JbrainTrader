<template>
  <div style="display: flex; height: 100vh; overflow: hidden">
    <Sidebar
      :status="data.status"
      :account="data.account"
      @open-sim="handleOpenSim"
      @select-tab="handleSelectTab"
    />

    <main style="flex: 1; padding: 1.5rem 2rem; display: flex; flex-direction: column; width: 100%; overflow: hidden">
      <h1 style="margin-bottom: 1.2rem; color: var(--primary); font-size: 1.8rem; display: flex; align-items: center; gap: 15px">
        단타 매매 시스템
      </h1>

      <!-- Tab Navigation Bar -->
      <div class="tabs-container">
        <div 
          v-for="tab in analysisTabs" 
          :key="tab.ticker"
          class="tab-item"
          :class="{ active: activeTabTicker === tab.ticker, 'non-closable': ['MAIN', 'LOG', 'HOLDINGS', 'MONITORING', 'DATA', 'STRATEGY', 'AIPICKS', 'AITRADES', 'AICALENDAR', 'AINOTICE', 'COLLECTOR', 'JOURNAL', 'CLI', 'SETTINGS'].includes(tab.ticker) }"
          @click="activeTabTicker = tab.ticker"
        >
          <span class="tab-title">{{ tab.name }} <span v-if="!['MAIN', 'LOG', 'HOLDINGS', 'MONITORING', 'DATA', 'STRATEGY', 'AIPICKS', 'AITRADES', 'AICALENDAR', 'AINOTICE', 'COLLECTOR', 'JOURNAL', 'CLI', 'SETTINGS'].includes(tab.ticker)">({{ tab.ticker }})</span></span>
          <span v-if="!['MAIN', 'LOG', 'HOLDINGS', 'MONITORING', 'DATA', 'STRATEGY', 'AIPICKS', 'AITRADES', 'AICALENDAR', 'AINOTICE', 'COLLECTOR', 'JOURNAL', 'CLI', 'SETTINGS'].includes(tab.ticker)" class="tab-close" @click.stop="handleCloseTab(tab.ticker)">×</span>

        </div>
      </div>

      <!-- Tab Content Area -->
      <div class="analysis-panels-container">
        <!-- Main Tab Content -->
        <div v-show="activeTabTicker === 'MAIN'" class="main-tab-content">
          <Header :account="data.account" @refresh="updateStatus" />
        </div>

        <!-- Log Tab Content -->
        <div v-show="activeTabTicker === 'LOG'" style="flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden">
          <LogViewer :logs="data.logs" />
        </div>

        <!-- Monitoring Tab Content -->
        <div v-show="activeTabTicker === 'MONITORING'" style="flex: 1; overflow-y: auto">
          <TickerList
            :tickers="data.tickers"
            :status="data.status"
            @edit-rule="handleEditRule"
            @start-sim="handleStartSim"
            @analyze="handleAnalyze"
          />
        </div>

        <!-- Holdings Tab Content -->
        <div v-show="activeTabTicker === 'HOLDINGS'" style="flex: 1; overflow-y: auto">
          <HoldingsList :holdings="data.account.holdings || []" :account="data.account" />
        </div>



        <div v-show="activeTabTicker === 'DATA'" style="flex: 1; overflow-y: auto">
          <DataPanel 
            :tickers="data.tickers" 
            :handover="dataHandover"
            @handover-processed="dataHandover = null"
          />
        </div>

        <div v-show="activeTabTicker === 'STRATEGY'" style="flex: 1; display: flex; flex-direction: column; overflow: hidden; min-height: 0">
          <StrategyPanel />
        </div>

        <div v-show="activeTabTicker === 'AIPICKS'" style="flex: 1; display: flex; flex-direction: column; overflow: hidden; min-height: 0">
          <AiPicksPanel />
        </div>

        <div v-show="activeTabTicker === 'AITRADES'" style="flex: 1; display: flex; flex-direction: column; overflow: hidden; min-height: 0">
          <AiTradesPanel :holdings="data.account.holdings || []" />
        </div>

        <div v-show="activeTabTicker === 'AICALENDAR'" style="flex: 1; display: flex; flex-direction: column; overflow-y: auto; min-height: 0">
          <AiCalendarPanel />
        </div>

        <div v-show="activeTabTicker === 'AINOTICE'" style="flex: 1; display: flex; flex-direction: column; overflow: hidden; min-height: 0">
          <AiNoticePanel />
        </div>

        <div v-show="activeTabTicker === 'COLLECTOR'" style="flex: 1; overflow-y: auto">
          <CollectorPanel />
        </div>

        <div v-show="activeTabTicker === 'JOURNAL'" style="flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden">
          <TradingJournal :account="data.account" />
        </div>

        <div v-show="activeTabTicker === 'CLI'" style="flex: 1; display: flex; flex-direction: column; overflow: hidden; min-height: 0">
          <CliTasksPanel />
        </div>

        <div v-show="activeTabTicker === 'SETTINGS'" style="flex: 1; display: flex; flex-direction: column; overflow: hidden; min-height: 0">
          <SettingsPanel />
        </div>

        <!-- Ticker Analysis Tabs Content -->
        <div v-for="tab in analysisTabs.filter(t => !['MAIN', 'LOG', 'HOLDINGS', 'MONITORING', 'DATA', 'STRATEGY', 'AIPICKS', 'AITRADES', 'AICALENDAR', 'AINOTICE', 'COLLECTOR', 'JOURNAL', 'CLI', 'SETTINGS'].includes(t.ticker))" :key="tab.ticker" v-show="activeTabTicker === tab.ticker" style="flex: 1; overflow-y: auto">
          <AnalysisPanel
            :ticker="tab.ticker"
            :name="tab.name"
            :analysis="data.tickers[tab.ticker]?.analysis"
          />
        </div>

      </div>
    </main>

    <EditRuleModal
      v-if="editingTicker"
      :ticker="editingTicker"
      :current-rule="editingRule"
      @close="editingTicker = null"
    />

    <HelperMascot />

    <!-- 
    <VirtualSimulationModal
      v-if="showSimModal"
      :initial-ticker="simTicker"
      :tickers="data.tickers"
      @close="showSimModal = false"
    />
    -->
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import './App.css';
import Sidebar from './components/Sidebar.vue';
import Header from './components/Header.vue';
import TickerList from './components/TickerList.vue';
import LogViewer from './components/LogViewer.vue';
import HoldingsList from './components/HoldingsList.vue';
import AnalysisPanel from './components/AnalysisPanel.vue';
import EditRuleModal from './components/EditRuleModal.vue';
import VirtualSimulationModal from './components/VirtualSimulationModal.vue';
import DataPanel from './components/DataPanel.vue';
import StrategyPanel from './components/StrategyPanel.vue';
import AiPicksPanel from './components/AiPicksPanel.vue';
import AiTradesPanel from './components/AiTradesPanel.vue';
import AiCalendarPanel from './components/AiCalendarPanel.vue';
import AiNoticePanel from './components/AiNoticePanel.vue';
import CollectorPanel from './components/CollectorPanel.vue';
import TradingJournal from './components/TradingJournal.vue';
import SettingsPanel from './components/SettingsPanel.vue';
import CliTasksPanel from './components/CliTasksPanel.vue';
import HelperMascot from './components/HelperMascot.vue';
import JBLogo from './components/JBLogo.vue';
import { fetchStatus } from './api';

const data = ref({
  status: 'OFFLINE',
  tickers: {},
  logs: [],
  account: { acc_no: '', name: '', balance: 0 }
});

const dataHandover = ref(null);
const editingTicker = ref(null);
const editingRule = ref('');
const showSimModal = ref(false);
const simTicker = ref('005930');
const analysisTabs = ref([
  { ticker: 'MAIN', name: '계정' },
  { ticker: 'LOG', name: '로그' },
  { ticker: 'HOLDINGS', name: '보유종목' },
  { ticker: 'MONITORING', name: '관심종목' },
  { ticker: 'DATA', name: '데이터' },
  { ticker: 'STRATEGY', name: '전략' },
  { ticker: 'AIPICKS', name: 'AI 종목' },
  { ticker: 'AITRADES', name: 'AI 매매' },
  { ticker: 'AICALENDAR', name: 'AI캘린더' },
  { ticker: 'AINOTICE', name: 'AI Notice' },
  { ticker: 'COLLECTOR', name: '수집기' },
  { ticker: 'JOURNAL', name: '매매일지' },
  { ticker: 'CLI', name: 'CLI 작업' },
  { ticker: 'SETTINGS', name: '환경 설정' }
]);


const activeTabTicker = ref('MAIN');

let intervalId = null;

const updateStatus = async () => {
  const res = await fetchStatus();
  data.value = res;
};

onMounted(() => {
  updateStatus();
  intervalId = setInterval(updateStatus, 5000);
});

onUnmounted(() => {
  if (intervalId) clearInterval(intervalId);
});

const handleOpenSim = () => {
  const tickerList = Object.keys(data.value.tickers);
  simTicker.value = tickerList.length > 0 ? tickerList[0] : '005930';
  showSimModal.value = true;
};

const handleSelectTab = (tabTicker) => {
  activeTabTicker.value = tabTicker;
};

const handleEditRule = (ticker, rule) => {
  editingTicker.value = ticker;
  editingRule.value = rule;
};

const handleStartSim = ({ ticker, type }) => {
  dataHandover.value = { ticker, type };
  activeTabTicker.value = 'DATA';
};

const handleAnalyze = (ticker) => {
  const tickerData = data.value.tickers[ticker];
  if (!tickerData) return;

  const existingTab = analysisTabs.value.find(t => t.ticker === ticker);
  if (!existingTab) {
    analysisTabs.value.push({
      ticker: ticker,
      name: tickerData.name
    });
  }
  activeTabTicker.value = ticker;
};

const handleCloseTab = (ticker) => {
  const index = analysisTabs.value.findIndex(t => t.ticker === ticker);
  if (index !== -1) {
    analysisTabs.value.splice(index, 1);
    if (activeTabTicker.value === ticker) {
      if (analysisTabs.value.length > 0) {
        // Switch to adjacent tab
        activeTabTicker.value = analysisTabs.value[Math.min(index, analysisTabs.value.length - 1)].ticker;
      } else {
        activeTabTicker.value = null;
      }
    }
  }
};
</script>
