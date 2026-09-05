<template>
  <div class="collector-panel">
    <div class="section header-section">
      <h2><i class="fas fa-download"></i> API 데이터 수집</h2>
      <div class="status-badge" :class="{ running: isRunning }">
        {{ isRunning ? '수집 중...' : '준비 완료' }}
      </div>
    </div>

    <div class="main-layout">
      <!-- 설정 사이드바 -->
      <div class="config-sidebar">
        <div class="form-group">
          <label>데이터 소스</label>
          <select v-model="config.source">
            <option value="Yahoo">Yahoo Finance</option>
            <option value="KRX">KRX (준비중)</option>
          </select>
        </div>

        <div class="form-group">
          <label>주기 선택</label>
          <div class="radio-group">
            <label v-for="opt in intervalOptions" :key="opt">
              <input type="radio" :value="opt" v-model="config.interval"> {{ opt }}
            </label>
          </div>
        </div>

        <div class="form-group">
          <label>기간 설정</label>
          <div class="date-inputs">
            <input type="date" v-model="config.startDate">
            <span>~</span>
            <input type="date" v-model="config.endDate">
          </div>
        </div>

        <div class="form-group">
          <label>종목 선택 (티커 및 종목명 검색 가능)</label>
          <div style="position: relative; flex: 1">
            <input 
              type="text" 
              v-model="tickerInput" 
              placeholder="예: AAPL, 삼성전자, 005930.KS"
              @keyup.enter="searchTicker"
              style="width: 100%"
            >
            <!-- Search Results Popup -->
            <div v-if="showSearchResults" class="search-results-popup glass">
              <div v-if="searchResults.length === 0" class="no-results-item">검색 결과가 없습니다.</div>
              <div 
                v-for="res in searchResults" 
                :key="res.ticker" 
                class="search-result-item" 
                @click="selectResult(res)"
              >
                <div class="res-ticker">{{ res.ticker.split('.')[0] }}</div>
                <div class="res-name">{{ res.name }}</div>
                <div class="res-market">{{ formatMarket(res.market) }}</div>
              </div>
              <div class="search-results-footer" @click="showSearchResults = false">닫기</div>
            </div>
          </div>
          <button @click="searchTicker" class="btn-search" :disabled="isSearching" style="white-space: nowrap">
            <span v-if="isSearching" class="mini-spinner"></span>
            검색
          </button>
          <div v-if="searchMessage" :class="['search-msg', { error: searchMessage.includes('없음') || searchMessage.includes('오류') }]">
            {{ searchMessage }}
          </div>
          <div class="selected-tickers">
            <span 
              v-for="t in selectedTickers" 
              :key="t.ticker" 
              class="ticker-tag"
              @contextmenu.prevent="openContextMenu($event, t)"
            >
              {{ t.name }} <i class="fas fa-times" @click="removeTicker(t.ticker)"></i>
            </span>
          </div>
          
          <!-- 종목 우클릭 확인 팝업 -->
          <Teleport to="body">
            <div 
              v-if="showContextMenu" 
              ref="contextMenuRef"
              class="custom-context-menu glass"
              :style="{ top: contextMenuPos.y + 'px', left: contextMenuPos.x + 'px' }"
              @mousedown.stop
            >
              <div class="popup-header">삭제 확인</div>
              <div class="popup-body">
                종목 '{{ selectedTickerForMenu?.name }}'을(를) 삭제할까요?
              </div>
              <div class="popup-footer">
                <button class="popup-btn cancel" @click="closeContextMenu">취소</button>
                <button class="popup-btn confirm" @click="removeSelectedTicker">삭제</button>
              </div>
            </div>
          </Teleport>
        </div>

        <div class="actions">
          <button v-if="!isRunning" @click="startCollection" class="btn-start" :disabled="selectedTickers.length === 0">
            <i class="fas fa-play"></i> 수집 시작
          </button>
          <button v-else @click="stopCollection" class="btn-stop">
            <i class="fas fa-stop"></i> 중지
          </button>
        </div>
      </div>

      <!-- 진행 상태 및 로그 -->
      <div class="display-area">
        <div class="progress-section">
          <h3>수집 진행률</h3>
          <div class="progress-list">
            <div v-for="(status, ticker) in progress" :key="ticker" class="progress-item">
              <span class="ticker-name">{{ getTickerDisplayName(ticker) }}</span>
              <span class="ticker-status" :class="status.includes('오류') ? 'error' : (status.includes('완료') ? 'done' : 'waiting')">
                {{ status }}
              </span>
            </div>
            <div v-if="Object.keys(progress).length === 0" class="empty-msg">선택된 종목이 없습니다.</div>
          </div>
        </div>

        <div class="log-section">
          <h3>수집 로그</h3>
          <div class="log-window" ref="logWindow">
            <div v-for="(log, idx) in logs" :key="idx" class="log-line">
              {{ log }}
            </div>
          </div>
        </div>
        </div>
      </div>

      <!-- 데이터 수집 현황 달력 (Yahoo 1분/5분용) -->
      <div v-if="config.source === 'Yahoo' && (config.interval === '1분' || config.interval === '5분' || config.interval === '일봉')" class="calendar-section">
        <div class="calendar-header-panel">
          <h3>
            <i class="fas fa-calendar-alt"></i> 수집 현황 미리보기
            <span v-if="calendarTicker" style="color: #3498db; margin-left: 10px; font-size: 0.9rem">
              - {{ getTickerDisplayName(calendarTicker) }}
            </span>
          </h3>
          <div style="display: flex; gap: 10px; align-items: center">
            <span style="font-size: 0.8rem; color: #888">대상 종목:</span>
            <select v-model="calendarTicker" class="mini-select">
              <option value="" disabled>종목 선택</option>
              <option value="ALL">전체 (모든 종목)</option>
              <option v-for="t in selectedTickers" :key="t.ticker" :value="t.ticker">
                {{ t.name }}
              </option>
            </select>
          </div>
        </div>
        <DataCalendar 
          v-if="calendarTicker"
          ref="calendarRef"
          :ticker="calendarTicker" 
          :ticker-name="getTickerPureName(calendarTicker)"
          :interval="config.interval" 
          :source="config.source" 
          :selected-date="config.startDate"
          @date-click="handleSelectDate"
        />
        <div v-else class="empty-calendar-msg">
          상단에서 종목을 추가하고 선택하여 수집 현황을 확인하세요.
        </div>
    </div>
  </div>
</template>

<script>
import { startCollector, stopCollector, fetchCollectorStatus, searchCollectorTicker } from '../api';
import DataCalendar from './DataCalendar.vue';

export default {
  name: 'CollectorPanel',
  components: {
    DataCalendar
  },
  data() {
    return {
      isRunning: false,
      tickerInput: '',
      isSearching: false,
      searchMessage: '',
      selectedTickers: [],
      intervalOptions: ['1분', '5분', '일봉'],
      config: {
        source: 'Yahoo',
        interval: '일봉',
        startDate: new Date(new Date().setFullYear(new Date().getFullYear() - 1)).toISOString().split('T')[0],
        endDate: new Date().toISOString().split('T')[0]
      },
      progress: {},
      logs: [],
      statusInterval: null,
      // 컨텍스트 메뉴 관련
      showContextMenu: false,
      contextMenuPos: { x: 0, y: 0 },
      selectedTickerForMenu: null,
      contextMenuRef: null,
      calendarTicker: '',
      searchResults: [],
      showSearchResults: false
    };
  },
  methods: {
    addTickers() {
      if (!this.tickerInput) return;
      const inputs = this.tickerInput.split(',').map(t => t.trim().toUpperCase()).filter(t => t);
      let changed = false;
      
      inputs.forEach(t => {
        let tickerStr = t;
        const pureTicker = t.split('.')[0];
        // 한국 종목(6자리 숫자)인 경우 .KS 자동 추가
        if (/^\d{6}$/.test(tickerStr)) {
          tickerStr += '.KS';
        }

        if (!this.selectedTickers.some(item => item.ticker === tickerStr)) {
          let name = tickerStr;
          try {
            const nameMap = JSON.parse(localStorage.getItem('tickerNameMap') || '{}');
            name = nameMap[tickerStr] || nameMap[pureTicker] || tickerStr;
          } catch (e) {}

          this.selectedTickers.push({ ticker: tickerStr, name: name });
          changed = true;
        }
      });

      if (changed) {
        this.tickerInput = '';
        this.searchMessage = '';
        this.saveSelectedTickers();
      }
    },
    async searchTicker() {
      const query = this.tickerInput.trim();
      if (!query) return;

      this.showSearchResults = false;
      this.searchResults = [];

      // 6자리 숫자 입력 시에도 검색을 거치도록 변경하여 종목명을 가져올 수 있게 함
      /*
      if (/^\d{6}$/.test(query)) {
        const ticker = query + '.KS';
        this.selectResult({ ticker: ticker, name: ticker });
        return;
      }
      */

      this.isSearching = true;
      this.searchMessage = '검색 중...';
      try {
        const results = await searchCollectorTicker(query, this.config.source);
        if (results && results.length > 0) {
          if (results.length === 1) {
            this.selectResult(results[0]);
          } else {
            this.searchResults = results;
            this.showSearchResults = true;
            this.searchMessage = `${results.length}개의 종목을 찾았습니다.`;
          }
        } else {
          this.searchMessage = '해당 종목을 찾을 수 없습니다.';
        }
      } catch (e) {
        this.searchMessage = '검색 중 오류가 발생했습니다.';
      } finally {
        this.isSearching = false;
        // 새로 추가된 종목이 있다면 달력 종목으로 설정 (기존에 선택된 게 없을 때만)
        if (this.selectedTickers.length > 0 && !this.calendarTicker) {
          this.calendarTicker = this.selectedTickers[0].ticker;
        }
      }
    },
    selectResult(found) {
      if (!this.selectedTickers.some(item => item.ticker === found.ticker)) {
        this.selectedTickers.push({ ticker: found.ticker, name: found.name });
        this.searchMessage = `성공: ${found.name} (${found.ticker}) 추가됨`;
        this.tickerInput = '';
        this.saveSelectedTickers();

        // 글로벌 티커 이름 캐시에도 저장 (다른 화면에서 공유 사용)
        try {
          const nameMap = JSON.parse(localStorage.getItem('tickerNameMap') || '{}');
          nameMap[found.ticker] = found.name;
          nameMap[found.ticker.split('.')[0]] = found.name;
          localStorage.setItem('tickerNameMap', JSON.stringify(nameMap));
        } catch (e) {}
      } else {
        this.searchMessage = `이미 추가된 종목입니다: ${found.name}`;
      }
      this.showSearchResults = false;
    },
    // 컨텍스트 메뉴 열기
    openContextMenu(event, item) {
      this.selectedTickerForMenu = item;
      
      const menuWidth = 200;
      const menuHeight = 140;
      
      let x = event.clientX;
      let y = event.clientY;

      // Boundary checks
      if (x + menuWidth > window.innerWidth) {
        x = x - menuWidth;
      }
      if (y + menuHeight > window.innerHeight) {
        y = y - menuHeight;
      }

      this.contextMenuPos = { x, y };
      this.showContextMenu = true;
    },
    // 컨텍스트 메뉴 닫기
    closeContextMenu() {
      this.showContextMenu = false;
      this.selectedTickerForMenu = null;
    },
    // 외부 클릭 시 닫기
    handleOutsideClick(event) {
      if (this.showContextMenu && this.$refs.contextMenuRef) {
        if (!this.$refs.contextMenuRef.contains(event.target)) {
          this.closeContextMenu();
        }
      }
      if (this.showSearchResults) {
        const searchContainer = this.$el.querySelector('.form-group div[style*="relative"]');
        if (searchContainer && !searchContainer.contains(event.target)) {
          this.showSearchResults = false;
        }
      }
    },
    // 메뉴에서 종목 삭제
    removeSelectedTicker() {
      if (this.selectedTickerForMenu) {
        this.removeTicker(this.selectedTickerForMenu.ticker);
      }
      this.closeContextMenu();
    },
    formatMarket(market) {
      if (!market) return '-';
      const m = market.toUpperCase();
      // 한국 시장 식별 (ETF 포함)
      if (['KSC', 'KRX', 'KOSPI', 'KRT', 'ETF'].includes(m)) return '코스피';
      if (['KOE', 'KOSDAQ', 'KOS', 'KOD'].includes(m)) return '코스닥';
      
      const usExchanges = ['NYQ', 'NMS', 'NGM', 'PCX', 'BTS', 'PNK', 'ASE'];
      if (usExchanges.includes(m)) return '미국';
      return '해외';
    },
    handleSelectDate({ date }) {
      this.config.startDate = date;
      this.config.endDate = date;
      this.searchMessage = `${date}가 기간 설정에 선택되었습니다.`;
      setTimeout(() => {
        if (this.searchMessage && this.searchMessage.includes('선택되었습니다')) {
          this.searchMessage = '';
        }
      }, 2000);
    },
    getTickerDisplayName(ticker) {
      if (ticker === 'ALL') return '전체 종목';
      const pureTicker = ticker.split('.')[0];
      
      // 1. 현재 선택된 종목 리스트에서 검색
      let found = this.selectedTickers.find(t => t.ticker === ticker || t.ticker.split('.')[0] === pureTicker);
      if (found && found.name && found.name !== found.ticker) {
        return found.name;
      }
      
      // 2. tickerNameMap 캐시 확인
      try {
        const nameMap = JSON.parse(localStorage.getItem('tickerNameMap') || '{}');
        if (nameMap[ticker]) return nameMap[ticker];
        if (nameMap[pureTicker]) return nameMap[pureTicker];
      } catch (e) {}

      return pureTicker;
    },
    getTickerPureName(ticker) {
      const found = this.selectedTickers.find(t => t.ticker === ticker);
      return found ? found.name : ticker.split('.')[0];
    },
    removeTicker(ticker) {
      this.selectedTickers = this.selectedTickers.filter(item => item.ticker !== ticker);
      this.saveSelectedTickers();
    },
    saveSelectedTickers() {
      localStorage.setItem('collectorSelectedTickers', JSON.stringify(this.selectedTickers));
    },
    async startCollection() {
      try {
        const tickers = this.selectedTickers.map(item => item.ticker);
        const res = await startCollector({
          tickers: tickers,
          interval: this.config.interval,
          start_date: this.config.startDate,
          end_date: this.config.endDate,
          source: this.config.source
        });
        if (res && res.status === 'SUCCESS') {
          this.isRunning = true;
          this.progress = {}; // 이전 진행 상태 초기화
          this.startStatusPolling();
          this.searchMessage = '데이터 수집이 시작되었습니다.';
        } else {
          alert('수집 시작 실패: ' + (res?.message || '알 수 없는 오류'));
        }
      } catch (e) {
        alert('서버 연결 오류: ' + e.message);
      }
    },
    async stopCollection() {
      await stopCollector();
    },
    async fetchStatus() {
      try {
        const data = await fetchCollectorStatus();
        this.isRunning = data.is_running;
        this.progress = data.progress;
        this.logs = data.logs;
        this.scrollToBottom();
        
        if (!this.isRunning && this.statusInterval) {
          clearInterval(this.statusInterval);
          this.statusInterval = null;
          // 수집 완료 후 달력 갱신
          if (this.$refs.calendarRef) {
            this.$refs.calendarRef.refresh();
          }
          // localStorage에 마지막 수집 주기 저장 (조회 탭이 아직 열리지 않은 경우를 대비)
          localStorage.setItem('lastCollectedInterval', this.config.interval);
          // 수집 완료 이벤트 발행 (수집한 주기 정보 포함)
          console.log('[CollectorPanel] 수집 완료, 주기:', this.config.interval);
          window.dispatchEvent(new CustomEvent('collection-complete', { 
            detail: { interval: this.config.interval } 
          }));
        }
      } catch (e) {
        console.error('Status fetch failed', e);
      }
    },
    startStatusPolling() {
      if (this.statusInterval) clearInterval(this.statusInterval);
      this.statusInterval = setInterval(this.fetchStatus, 1000);
    },
    scrollToBottom() {
      this.$nextTick(() => {
        const container = this.$refs.logWindow;
        if (container) container.scrollTop = container.scrollHeight;
      });
    },
    refreshCalendar() {
      // 달력 데이터를 강제로 새로고침
      if (this.calendarTicker) {
        const currentTicker = this.calendarTicker;
        this.calendarTicker = null;
        this.$nextTick(() => {
          this.calendarTicker = currentTicker;
        });
      }
    }
  },
  watch: {
    config: {
      handler(newVal) {
        localStorage.setItem('collectorConfig', JSON.stringify(newVal));
      },
      deep: true
    },
    calendarTicker: {
      handler(newVal) {
        localStorage.setItem('collectorCalendarTicker', newVal);
      }
    },
    selectedTickers: {
      handler(newVal) {
        if (newVal.length > 0) {
          // calendarTicker가 없거나, 'ALL'이 아니면서 선택된 종목 리스트에도 없는 경우에만 초기화
          if (!this.calendarTicker || (this.calendarTicker !== 'ALL' && !newVal.some(t => t.ticker === this.calendarTicker))) {
            this.calendarTicker = 'ALL'; // 기본값을 'ALL'로 설정
          }
        }
      },
      deep: true
    }
  },
  mounted() {
    this.fetchStatus();
    // 로컬 스토리지에서 종목 로드
    const savedTickers = localStorage.getItem('collectorSelectedTickers');
    if (savedTickers) {
      try {
        const parsed = JSON.parse(savedTickers);
        // 마이그레이션: 문자열 배열인 경우 객체 배열로 변환
        if (parsed.length > 0 && typeof parsed[0] === 'string') {
          this.selectedTickers = parsed.map(t => ({ ticker: t, name: t }));
        } else {
          this.selectedTickers = parsed;
        }
      } catch (e) {
        console.error('Failed to parse saved tickers', e);
      }
    }

    // 로컬 스토리지에서 마지막 선택된 캘린더 티커 로드
    const savedCalendarTicker = localStorage.getItem('collectorCalendarTicker');
    if (savedCalendarTicker) {
      this.calendarTicker = savedCalendarTicker;
    } else if (this.selectedTickers.length > 0) {
      this.calendarTicker = 'ALL';
    }

    // 로컬 스토리지에서 설정 로드
    const savedConfig = localStorage.getItem('collectorConfig');
    if (savedConfig) {
      try {
        const parsed = JSON.parse(savedConfig);
        this.config = { ...this.config, ...parsed };
      } catch (e) {
        console.error("Failed to parse saved config", e);
      }
    }

    // 전역 클릭 시 메뉴 닫기
    window.addEventListener('mousedown', this.handleOutsideClick);
  },
  beforeUnmount() {
    if (this.statusInterval) clearInterval(this.statusInterval);
    window.removeEventListener('mousedown', this.handleOutsideClick);
  }
};
</script>

<style scoped>
.collector-panel {
  padding: 20px;
  background: #1a1a1a;
  color: #e0e0e0;
  height: 100%;
  border-radius: 8px;
}

.header-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  border-bottom: 1px solid #333;
  padding-bottom: 10px;
}

.status-badge {
  padding: 4px 12px;
  border-radius: 20px;
  background: #444;
  font-size: 0.8rem;
}

.status-badge.running {
  background: #27ae60;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.6; }
  100% { opacity: 1; }
}

.main-layout {
  display: grid;
  grid-template-columns: 350px 1fr;
  gap: 20px;
}

.calendar-section {
  grid-column: span 2;
  background: #252525;
  padding: 20px;
  border-radius: 8px;
  margin-top: 20px;
}

.calendar-header-panel {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.mini-select {
  width: auto !important;
  padding: 4px 8px !important;
  font-size: 0.85rem;
}

.empty-calendar-msg {
  text-align: center;
  padding: 40px;
  color: #666;
  background: #1a1a1a;
  border-radius: 8px;
  border: 1px dashed #333;
}

.config-sidebar {
  background: #252525;
  padding: 20px;
  border-radius: 8px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: bold;
  font-size: 0.9rem;
  color: #bbb;
}

select, input[type="text"], input[type="date"] {
  width: 100%;
  background: #333;
  border: 1px solid #444;
  color: white;
  padding: 8px;
  border-radius: 4px;
}

.radio-group {
  display: flex;
  gap: 15px;
}

.date-inputs {
  display: flex;
  align-items: center;
  gap: 5px;
}

.selected-tickers {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.ticker-tag {
  background: #3498db;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
  display: flex;
  align-items: center;
  gap: 5px;
}

.actions button {
  width: 100%;
  padding: 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
  margin-top: 10px;
}

.btn-start { background: #2980b9; color: white; }
.btn-stop { background: #c0392b; color: white; }

.btn-search {
  width: auto !important;
  background: var(--secondary, #8e44ad);
  color: white;
  border: none;
  padding: 0 15px !important;
  cursor: pointer;
  border-radius: 4px;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 0 !important;
}

.btn-search:hover {
  filter: brightness(1.2);
}

.display-area {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.progress-section, .log-section {
  background: #252525;
  padding: 15px;
  border-radius: 8px;
  flex: 1;
}

h3 { margin-top: 0; font-size: 1rem; color: #3498db; }

.progress-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 10px;
}

.progress-item {
  background: #333;
  padding: 10px;
  border-radius: 4px;
  display: flex;
  flex-direction: column;
}

.ticker-status { font-size: 0.8rem; margin-top: 5px; }
.ticker-status.done { color: #2ecc71; }
.ticker-status.error { color: #e74c3c; }
.ticker-status.waiting { color: #f1c40f; }

.log-window {
  height: 250px;
  overflow-y: auto;
  background: #000;
  padding: 10px;
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.85rem;
  border-radius: 4px;
  border: 1px solid #333;
}

.log-line { margin-bottom: 2px; border-bottom: 1px solid #111; }
.search-msg {
  font-size: 0.8rem;
  margin-bottom: 8px;
  color: var(--primary);
}

.search-msg.error {
  color: #ff6b6b;
}

.mini-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  display: inline-block;
  animation: spin 1s linear infinite;
  margin-right: 5px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.custom-context-menu {
  position: fixed;
  z-index: 10000;
  width: 200px;
  background: rgba(30, 30, 45, 0.98);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 12px;
  padding: 0;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
  animation: popupFadeIn 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  user-select: none;
}

@keyframes popupFadeIn {
  from { opacity: 0; transform: scale(0.95) translateY(-5px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

.popup-header {
  padding: 8px 12px;
  font-size: 0.75rem;
  font-weight: bold;
  color: #8b949e;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  background: rgba(255, 255, 255, 0.02);
}

.popup-body {
  padding: 12px;
  font-size: 0.85rem;
  line-height: 1.4;
  color: #e6edf3;
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
  color: #8b949e;
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

.search-results-popup {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 1000;
  max-height: 300px;
  overflow-y: auto;
  background: rgba(30, 30, 45, 0.98);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 8px;
  margin-top: 5px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
}

.search-result-item {
  padding: 10px 15px;
  cursor: pointer;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-result-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.search-result-item .res-ticker {
  flex: 0 0 80px;
  font-size: 0.85rem;
  color: #8b949e;
  font-family: monospace;
}

.search-result-item .res-name {
  flex: 1;
  font-size: 0.9rem;
  font-weight: bold;
  color: var(--primary);
  margin-left: 10px;
}

.search-result-item .res-market {
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
  color: var(--primary);
  background: rgba(255, 255, 255, 0.02);
  cursor: pointer;
}
</style>
