<template>
  <div class="viewer-container">
    <div class="control-bar glass">
      <div class="control-group">
        <label>종목 검색 및 선택</label>
        <div class="searchable-select-wrapper">
          <input 
            type="text" 
            v-model="tickerSearchQuery" 
            placeholder="검색 (티커/이름)..." 
            class="ticker-search-input"
          >
          <select v-model="selectedTicker" @change="onTickerChange">
            <option value="" disabled>확인할 종목을 선택하세요</option>
            <option v-for="t in filteredTickers" :key="t.ticker" :value="t.ticker">
              {{ t.name }} ({{ t.ticker }})
            </option>
          </select>
        </div>
      </div>
      
      <div class="control-group">
        <label>주기</label>
        <div class="tabs">
          <button 
            v-for="opt in intervalOptions" 
            :key="opt" 
            :class="{ active: selectedInterval === opt }"
            @click="selectInterval(opt)"
          >
            {{ opt }}
          </button>
        </div>
      </div>

      <!-- Date Selection (Visible for 1m/5m/Tick) -->
      <div class="control-group animated" v-if="selectedInterval !== '일봉'">
        <label>날짜 선택</label>
        <select v-model="selectedDate" @change="fetchData" class="date-select">
          <option v-for="d in availableDates" :key="d" :value="d">{{ d }}</option>
          <option v-if="availableDates.length === 0" disabled>데이터 없음</option>
        </select>
      </div>

      <button class="export-btn" @click="exportToCSV" :disabled="loading || chartData.length === 0">
        <span>📥</span>
        데이터 내보내기
      </button>

      <button class="delete-btn" @click="showDeleteConfirm = true" :disabled="loading || !selectedTicker">
        <span>🗑️</span>
        {{ selectedDates.length > 0 ? `데이터 삭제 (${selectedDates.length})` : '데이터 삭제' }}
      </button>

      <button class="refresh-btn" @click="fetchData" :disabled="loading || !selectedTicker">
        <span v-if="loading">⏳</span>
        <span v-else>🔄</span>
        새로고침
      </button>
    </div>

    <!-- Chart Section -->
    <div class="chart-section glass" v-if="selectedTicker">
      <div class="section-header">
        <div style="display: flex; align-items: center; gap: 15px">
          <h3>📊 {{ selectedInterval === '일봉' || selectedInterval === '틱' ? '가격 차트' : '캔들 차트' }} ({{ selectedTickerName }})</h3>
          <div v-if="generationInfo" class="gen-badge">
            <span class="label">기준:</span> {{ generationInfo.baseInterval }}
            <span class="sep">|</span>
            <span class="label">알고리즘:</span> {{ generationInfo.algorithm }}
          </div>
        </div>
        <div class="chart-info" v-if="selectedInterval !== '일봉'">{{ selectedDate }} 데이터</div>
      </div>
      <div class="chart-wrapper">
        <TickChart 
          v-if="selectedInterval === '일봉' || selectedInterval === '틱'" 
          :static-data="chartData" 
          :ticker="selectedTicker"
          :timezone="tickerTimezone"
        />
        <CandleChart v-else :data="chartData" :ticker="selectedTicker" :timezone="tickerTimezone" />
      </div>
    </div>

    <!-- Table Section -->
    <div class="table-section glass" v-if="selectedTicker">
      <div class="section-header">
        <h3>📑 {{ selectedInterval === '틱' ? '실시간 틱 데이터' : `${selectedInterval} 데이터 날짜별 요약` }}</h3>
        <div class="header-actions" v-if="props.viewMode !== 'date' && tableData.length > 0">
          <span class="selection-count" v-if="selectedDates.length > 0">{{ selectedDates.length }}개 선택됨</span>
          <span class="count">총 {{ sortedTableData.length }}건</span>
        </div>
      </div>
      
      <!-- 날짜별 조회 모드: 달력 표시 -->
      <div v-if="props.viewMode === 'date'" class="calendar-wrapper-viewer">
        <DataCalendar 
          ticker="ALL"
          :interval="selectedInterval"
          source="Yahoo"
          :selected-date="selectedDate"
          @date-click="(res) => {
            selectedDate = res.date;
            fetchData();
          }"
        />
      </div>

      <!-- 기본 모드: 테이블 표시 -->
      <div v-else class="table-wrapper">
        <table v-if="tableData.length > 0">
          <thead>
            <tr v-if="selectedInterval === '틱'">
              <th class="checkbox-col">
                <input type="checkbox" :checked="isAllSelected" @change="toggleSelectAll" />
              </th>
              <th style="text-align: left">시작 시간</th>
              <th style="text-align: left">종료 시간</th>
              <th>시간대</th>
              <th>순번</th>
              <th>가격</th>
              <th>거래량</th>
              <th>알고리즘</th>
            </tr>
            <tr v-else>
              <th class="checkbox-col">
                <input type="checkbox" :checked="isAllSelected" @change="toggleSelectAll" />
              </th>
              <th style="text-align: left">날짜 / 시간 범위</th>
              <th>시간대</th>
              <th style="text-align: center">{{ selectedInterval !== '일봉' ? '건수' : '주기' }}</th>
              <th>시가</th>
              <th>고가</th>
              <th>저가</th>
              <th>종가</th>
              <th>거래량</th>
            </tr>
          </thead>
          <tbody>
            <template v-if="selectedInterval === '틱'">
              <tr 
                v-for="(row, idx) in tableData" 
                :key="idx"
                :class="{ 
                  'selected-row': selectedDate === row.datetime.split(' ')[0],
                  'checked-row': selectedDates.includes(row.datetime.split(' ')[0])
                }"
                @click="selectDateFromTable(row.datetime.split(' ')[0])"
              >
                <td class="checkbox-col" @click.stop>
                  <input 
                    type="checkbox" 
                    :checked="selectedDates.includes(row.datetime.split(' ')[0])"
                    @change="toggleSelectDate(row.datetime.split(' ')[0])"
                  />
                </td>
                <td class="date">
                  <div class="date-main">{{ row.datetime.split(' ')[0] }}</div>
                  <div class="time-sub">{{ row.datetime.split(' ')[1].split('.')[0] }}</div>
                </td>
                <td class="date">
                  <div class="time-sub" v-if="row.endTime">{{ row.endTime.split('.')[0] }}</div>
                  <div v-else>-</div>
                </td>
                <td class="timezone-col">
                  <span class="tz-badge">{{ formatTimezone(row.timezone, row.datetime) }}</span>
                </td>
                <td class="interval">#{{ tableData.length - idx }}</td>
                <td class="close">{{ formatPrice(row.value) }}</td>
                <td class="vol">{{ row.volume.toLocaleString() }}</td>
                <td class="scenario-col">{{ row.scenario }}</td>
              </tr>
            </template>
            <tr 
              v-else
              v-for="(row, idx) in sortedTableData" 
              :key="idx"
              :class="{ 
                'selected-row': selectedDate === row.datetime.split(' ')[0],
                'checked-row': selectedDates.includes(row.datetime.split(' ')[0])
              }"
              @click="selectDateFromTable(row.datetime.split(' ')[0])"
            >
              <td class="checkbox-col" @click.stop>
                <input 
                  type="checkbox" 
                  :checked="selectedDates.includes(row.datetime.split(' ')[0])"
                  @change="toggleSelectDate(row.datetime.split(' ')[0])"
                />
              </td>
              
              <!-- 일반 OHLCV 데이터 인 경우 -->
              <td class="date">
                <div class="date-main">{{ row.datetime.split(' ')[0] }}</div>
                <div class="time-range" v-if="row.endTime" style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 2px;">
                  {{ row.datetime.split(' ')[1].split('.')[0] }} ~ {{ row.endTime.split('.')[0] }}
                </div>
              </td>
              <td class="timezone-col">
                <span class="tz-badge">{{ formatTimezone(row.timezone, row.datetime) }}</span>
              </td>
              <td class="interval" style="text-align: center">
                 <span v-if="row.count" style="color: var(--primary); font-weight: 600; font-size: 0.9rem;">
                   {{ row.count.toLocaleString() }}{{ selectedInterval === '틱' ? '틱' : '봉' }}
                 </span>
                 <span v-else style="color: var(--text-muted);">{{ row.interval }}</span>
              </td>
              <td class="price">{{ formatPrice(row.open) }}</td>
              <td class="price high">{{ formatPrice(row.high) }}</td>
              <td class="price low">{{ formatPrice(row.low) }}</td>
              <td class="price bold">{{ formatPrice(row.close) }}</td>
              <td class="vol">{{ (row.volume || 0).toLocaleString() }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else-if="!loading" class="no-data">
          데이터가 없습니다. 수집기에서 먼저 데이터를 가져오세요.
        </div>
        <div v-if="loading" class="loading-overlay">
          <div class="spinner"></div>
          데이터 로드 중...
        </div>
      </div>
    </div>

    <div v-else class="welcome-screen">
      <div class="welcome-icon">📉</div>
      <h2>데이터 브라우저</h2>
      <p>좌측 상단에서 종목을 선택하여 수집된 데이터를 확인하세요.</p>
    </div>

    <!-- Deletion Confirmation Modal -->
    <Teleport to="body">
      <div v-if="showDeleteConfirm" class="modal-overlay" @click="showDeleteConfirm = false">
        <div class="modal-content glass" @click.stop>
          <div class="modal-header">
            <h3>⚠️ 데이터 삭제 확인</h3>
          </div>
          <div class="modal-body">
            <template v-if="selectedDates.length > 0">
              <p>
                '<strong>{{ selectedTickerName }}</strong>'의 선택된 
                <span style="color: #ff6b6b; font-weight: bold">{{ selectedDates.length }}개 날짜</span> 
                데이터를 삭제하시겠습니까?
              </p>
              <div class="selected-list-mini">
                {{ selectedDates.join(', ') }}
              </div>
              <p class="warning-text">선택된 날짜의 <span style="text-decoration: underline; font-weight: bold">{{ selectedInterval }}</span> 데이터만 영구적으로 삭제됩니다.</p>
            </template>
            <template v-else-if="selectedInterval !== '일봉' && selectedDate">
              <p>
                '<strong>{{ selectedTickerName }}</strong>'의 
                <span style="color: #ff6b6b; font-weight: bold">{{ selectedDate }}</span> 
                데이터를 삭제하시겠습니까?
              </p>
              <p class="warning-text">현재 선택된 <span style="text-decoration: underline; font-weight: bold">{{ selectedInterval }}</span> 데이터만 삭제됩니다.</p>
            </template>
            <template v-else>
              <p>'<strong>{{ selectedTickerName }}</strong>'의 모든 데이터(OHLCV 및 틱 데이터 포함)를 삭제하시겠습니까?</p>
              <p class="warning-text">이 작업은 취소할 수 없으며 데이터베이스에서 영구적으로 삭제됩니다.</p>
            </template>
          </div>
          <div class="modal-footer">
            <button class="modal-cancel-btn" @click="showDeleteConfirm = false">취소</button>
            <button class="modal-delete-btn" @click="handleDelete">지금 삭제</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue';
import { fetchCollectedTickers, fetchCollectorPreview, fetchCollectedDates, deleteCollectorData } from '../api';
import TickChart from './TickChart.vue';
import CandleChart from './CandleChart.vue';
import DataCalendar from './DataCalendar.vue';

const props = defineProps({
  viewMode: { type: String, default: 'ticker' }, // 'ticker' or 'date'
  initialTicker: String,
  initialDate: String
});


const emit = defineEmits(['mounted', 'data-deleted']);


const availableTickers = ref([]);
const selectedTicker = ref('');
const selectedInterval = ref('일봉');
const intervalOptions = ['틱', '1분', '5분', '일봉'];
const availableDates = ref([]);
const selectedDate = ref('');
const selectedDates = ref([]); // 다중 선택된 날짜들
const chartData = ref([]);
const tableData = ref([]);
const loading = ref(false);
const showDeleteConfirm = ref(false);
const tickerSearchQuery = ref('');

const filteredTickers = computed(() => {
  if (!tickerSearchQuery.value) return availableTickers.value;
  const q = tickerSearchQuery.value.toLowerCase();
  return availableTickers.value.filter(t => 
    t.ticker.toLowerCase().includes(q) || 
    t.name.toLowerCase().includes(q)
  );
});

const isAllSelected = computed(() => {
  const dataSource = selectedInterval.value === '틱' ? tableData.value : sortedTableData.value;
  if (dataSource.length === 0) return false;
  const allDateStrs = dataSource.map(row => row.datetime.split(' ')[0]);
  const uniqueDates = [...new Set(allDateStrs)];
  return uniqueDates.every(date => selectedDates.value.includes(date));
});

const toggleSelectAll = () => {
  const dataSource = selectedInterval.value === '틱' ? tableData.value : sortedTableData.value;
  if (isAllSelected.value) {
    selectedDates.value = [];
  } else {
    const allDateStrs = dataSource.map(row => row.datetime.split(' ')[0]);
    selectedDates.value = [...new Set(allDateStrs)];
  }
};

const toggleSelectDate = (date) => {
  const idx = selectedDates.value.indexOf(date);
  if (idx > -1) {
    selectedDates.value.splice(idx, 1);
  } else {
    selectedDates.value.push(date);
  }
};

const fetchData = async () => {
  if (!selectedTicker.value) return;
  
  loading.value = true;
  try {
    // 1. 차트 데이터 (현재 인터벌 + 선택 날짜)
    const cData = await fetchCollectorPreview(
      selectedTicker.value, 
      selectedInterval.value, 
      selectedInterval.value === '일봉' ? null : selectedDate.value
    );
    chartData.value = cData || [];

    // 2. 테이블 데이터
    if (selectedInterval.value === '틱' || selectedInterval.value === '1분' || selectedInterval.value === '5분') {
      // 틱, 1분, 5분 주기는 실제 데이터가 있는 요약 정보를 가져와서 테이블에 표시
      const summaries = await fetchCollectedDates(selectedTicker.value, selectedInterval.value);
      tableData.value = summaries.map(item => {
        // 백엔드에서 날짜 문자열만 온 경우 (예외 처리)
        if (typeof item === 'string') {
          return {
            datetime: `${item} 00:00:00`,
            interval: selectedInterval.value,
            open: 0, high: 0, low: 0, close: 0, volume: 0, count: 0
          }
        }
        // 백엔드 요약 객체 처리
        return {
          datetime: `${item.date} ${item.start_time || '00:00:00'}`,
          endTime: item.end_time || '',
          interval: selectedInterval.value,
          open: Number(item.open || 0),
          high: Number(item.high || 0),
          low: Number(item.low || 0),
          close: Number(item.close || 0),
          volume: Number(item.volume || 0),
          count: item.bar_count || item.tick_count || 0,
          scenario: item.scenario || 'COLLECTED',
          timezone: item.timezone || ''
        }
      });
    }
 else if (tableData.value.length === 0 || selectedInterval.value === '일봉' || (tableData.value[0] && tableData.value[0].datetime.includes(':'))) {
      // 일봉 데이터가 필요하거나 현재 테이블에 분 데이터가 차있는 경우 일봉 리스트로 리로드
      const tData = await fetchCollectorPreview(selectedTicker.value, '일봉');
      tableData.value = tData || [];
    }
  } catch (e) {
    console.error("Failed to fetch data", e);
  } finally {
    loading.value = false;
  }
};

const updateAvailableDates = async () => {
  if (selectedInterval.value === '일봉') {
    availableDates.value = [];
    selectedDate.value = '';
    return;
  }
  
  try {
    const response = await fetchCollectedDates(selectedTicker.value, selectedInterval.value);
    // 응답이 객체 배열인 경우 날짜만 추출, 문자열 배열인 경우 그대로 사용
    const dates = response.map(item => {
      if (typeof item === 'string') {
        return item;
      }
      return item.date || item.datetime?.split(' ')[0] || '';
    }).filter(d => d);
    
    availableDates.value = dates;
    if (dates.length > 0) {
      const savedDate = props.initialDate || localStorage.getItem('viewerDate');
      if (savedDate && dates.includes(savedDate)) {
        selectedDate.value = savedDate;
      } else {
        selectedDate.value = dates[0];
      }
    } else {
      selectedDate.value = '';
    }
  } catch (e) {
    console.error("Failed to fetch dates", e);
  }
};

const onTickerChange = () => {
  tableData.value = []; // 종목 변경 시 테이블 갱신 강제
  updateAvailableDates().then(() => fetchData());
};

const selectInterval = (opt) => {
  selectedInterval.value = opt;
  selectedDates.value = []; // 주기 변경 시 선택 초기화
  updateAvailableDates().then(() => fetchData());
};

const selectDateFromTable = (date) => {
  if (selectedInterval.value === '일봉') return;
  selectedDate.value = date;
  fetchData();
};

const formatPrice = (p) => {
  if (p === null || p === undefined) return '-';
  if (p >= 1000) return Math.round(p).toLocaleString();
  return p.toFixed(2);
};

const formatTimezone = (tz, datetime) => {
  if (!tz) return '-';
  if (tz === 'Asia/Seoul') return 'KST';
  if (tz === 'America/New_York') {
    if (!datetime) return 'EST/EDT';
    
    // Determine EST or EDT based on the date
    try {
      const d = new Date(datetime);
      const str = d.toLocaleTimeString('en-US', { timeZone: 'America/New_York', timeZoneName: 'short' });
      // str might be "9:30:00 AM EDT" or "EST"
      if (str.includes('EDT')) return 'EDT';
      if (str.includes('EST')) return 'EST';
    } catch(e) {}
    return 'EST/EDT';
  }
  return tz;
};

const downloadCSV = (data, dateLabel) => {
  if (!data || data.length === 0) return;
  
  const isTick = selectedInterval.value === '틱';
  let csvContent = "";
  
  // Header
  if (isTick) {
    csvContent = "datetime,price,volume,algorithm,base\n";
  } else {
    csvContent = "datetime,open,high,low,close,volume\n";
  }

  // Rows
  data.forEach(row => {
    let line = "";
    if (isTick) {
      let algo = 'NONE', base = 'NONE';
      if (row.scenario && row.scenario.startsWith('RECON:')) {
        const parts = row.scenario.split(':');
        algo = parts[1] || 'NONE';
        base = parts[2] || 'NONE';
      }
      line = `${row.datetime},${row.value},${row.volume},${algo},${base}`;
    } else {
      line = `${row.datetime},${row.open},${row.high},${row.low},${row.close},${row.volume}`;
    }
    csvContent += line + "\n";
  });

  // Download
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement("a");
  const url = URL.createObjectURL(blob);
  const tickerName = selectedTickerName.value.replace(/[^a-z0-9가-힣]/gi, '_');
  const fileName = `${tickerName}_${dateLabel}_${selectedInterval.value}.csv`;

  link.setAttribute("href", url);
  link.setAttribute("download", fileName);
  link.style.visibility = 'hidden';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

const exportToCSV = async () => {
  loading.value = true;
  try {
    if (selectedDates.value.length > 0) {
      // 다중 선택된 날짜들 처리: 각각 별도 파일로 내보내기
      for (const date of selectedDates.value) {
        const dData = await fetchCollectorPreview(selectedTicker.value, selectedInterval.value, date);
        if (dData && dData.length > 0) {
          downloadCSV(dData, date);
          // 브라우저가 다중 다운로드를 차단하거나 꼬이는 것을 방지하기 위해 짧은 지연
          await new Promise(resolve => setTimeout(resolve, 300));
        }
      }
    } else {
      // 현재 로드된 데이터 사용
      if (chartData.value.length === 0) {
        alert("내보낼 데이터가 없습니다.");
        return;
      }
      downloadCSV(chartData.value, selectedDate.value || 'current');
    }
  } catch (e) {
    console.error("Export failed", e);
    alert("데이터 내보내기에 실패했습니다.");
  } finally {
    loading.value = false;
  }
};

const handleDelete = async () => {
  if (!selectedTicker.value) return;
  
  loading.value = true;
  showDeleteConfirm.value = false;
  
  try {
    const datesToDelete = selectedDates.value.length > 0 ? [...selectedDates.value] : (selectedInterval.value !== '일봉' ? [selectedDate.value] : [null]);
    
    let successCount = 0;
    for (const deleteDate of datesToDelete) {
      const result = await deleteCollectorData(selectedTicker.value, deleteDate, selectedInterval.value);
      if (result.status === 'SUCCESS') {
        successCount++;
      }
    }

    if (successCount > 0) {
      if (datesToDelete[0] !== null) {
        // 특정 날짜들을 삭제한 경우
        selectedDates.value = [];
        await updateAvailableDates();
        fetchData();
        // 삭제 완료 이벤트 발생 (CollectorPanel 달력 새로고침용)
        emit('data-deleted', { ticker: selectedTicker.value, interval: selectedInterval.value });
      } else {
        // 전체 삭제한 경우
        selectedTicker.value = '';
        selectedDates.value = [];
        chartData.value = [];
        tableData.value = [];
        availableDates.value = [];
        const list = await fetchCollectedTickers();
        availableTickers.value = list;
        emit('data-deleted', { ticker: selectedTicker.value, interval: selectedInterval.value });
      }
    } else if (datesToDelete.length > 0) {
      alert("삭제 작업에 실패했습니다.");
    }
  } catch (e) {
    console.error("Delete failed", e);
    alert("서버 연결에 실패했습니다.");
  } finally {
    loading.value = false;
  }
};

const sortedTableData = computed(() => {
  let data = [...tableData.value];
  if (selectedInterval.value !== '일봉') {
    // 일봉이 아닐 때는 (1분, 5분, 틱 등) 해당 주기에 데이터가 존재하는 날짜만 필터링하여 보여줌
    data = data.filter(row => {
      const dateStr = row.datetime.split(' ')[0];
      return availableDates.value.includes(dateStr);
    });
  }
  return data.reverse();
});

const selectedTickerName = computed(() => {
  const found = availableTickers.value.find(t => t.ticker === selectedTicker.value);
  return found ? found.name : selectedTicker.value;
});

const tickerTimezone = computed(() => {
  if (!selectedTicker.value) return '';
  // Ticker starts with Alpha -> US, numbers -> KR
  const isUS = !selectedTicker.value.split('.')[0].match(/^[0-9]+$/);
  return isUS ? 'America/New_York' : 'Asia/Seoul';
});

const generationInfo = computed(() => {
  if (selectedInterval.value !== '틱' || chartData.value.length === 0) return null;
  
  // chartData rows have 'scenario' key
  const firstWithScenario = chartData.value.find(t => t.scenario && t.scenario !== 'NONE');
  if (!firstWithScenario) return null;
  
  const sc = firstWithScenario.scenario;
  if (sc.startsWith('RECON:')) {
    const parts = sc.split(':');
    return {
      algorithm: parts[1],
      baseInterval: parts[2]
    };
  } else if (sc.startsWith('RECON_')) {
    // Legacy format: RECON_REALISTIC
    return {
      algorithm: sc.split('_')[1],
      baseInterval: '알 수 없음'
    };
  }
  return null;
});

// 설정 저장
watch(selectedTicker, (val) => {
  localStorage.setItem('viewerTicker', val);
});

watch(selectedInterval, (val) => {
  localStorage.setItem('viewerInterval', val);
});

watch(selectedDate, (val) => {
  if (val) localStorage.setItem('viewerDate', val);
});

onMounted(async () => {
  try {
    const list = await fetchCollectedTickers();
    availableTickers.value = list;
    
    // 이전에 선택한 값 복원 (props가 있으면 우선 사용)
    const savedTicker = props.initialTicker || localStorage.getItem('viewerTicker');
    let savedInterval = localStorage.getItem('viewerInterval') || '일봉';
    
    // 만약 tick generation에서 넘어온 경우라면 강제로 '틱' 주기로 설정
    if (props.initialTicker) {
      savedInterval = '틱';
    }
    
    // 마지막 수집/가져오기 주기가 있으면 자동 선택
    const lastCollectedInterval = localStorage.getItem('lastCollectedInterval');
    const lastCollectedTicker = localStorage.getItem('lastCollectedTicker');
    if (lastCollectedInterval && intervalOptions.includes(lastCollectedInterval)) {
      console.log('[TickerDataViewer] 마지막 수집 주기 감지:', lastCollectedInterval);
      savedInterval = lastCollectedInterval;
      // 한 번 사용했으면 삭제 (다음 마운트 시 중복 적용 방지)
      localStorage.removeItem('lastCollectedInterval');
      
      // 마지막 수집 종목도 있으면 자동 선택
      if (lastCollectedTicker && list.some(t => t.ticker === lastCollectedTicker)) {
        console.log('[TickerDataViewer] 마지막 수집 종목 감지:', lastCollectedTicker);
        selectedTicker.value = lastCollectedTicker;
        localStorage.removeItem('lastCollectedTicker');
      }
    }
    
    selectedInterval.value = savedInterval;
    
    if (savedTicker && list.some(t => t.ticker === savedTicker)) {
      selectedTicker.value = selectedTicker.value || savedTicker; // 이미 설정되어 있으면 유지
      await updateAvailableDates();
      fetchData();
    }
  } catch (e) {
    console.error("Failed to fetch tickers", e);
  } finally {
    emit('mounted');
  }
  
  // 수집 완료 이벤트 리스너 등록
  window.addEventListener('collection-complete', handleCollectionComplete);
});

onUnmounted(() => {
  // 이벤트 리스너 정리
  window.removeEventListener('collection-complete', handleCollectionComplete);
});

// 수집 완료 시 자동으로 해당 주기 선택
const handleCollectionComplete = async (event) => {
  const collectedInterval = event.detail.interval;
  console.log('[TickerDataViewer] 수집 완료 이벤트 수신, 주기:', collectedInterval);
  
  // 새 종목이 추가되었을 수 있으므로 종목 리스트 갱신
  try {
    const list = await fetchCollectedTickers();
    availableTickers.value = list;
  } catch (e) {}

  if (collectedInterval && intervalOptions.includes(collectedInterval)) {
    console.log('[TickerDataViewer] 주기 자동 선택:', collectedInterval);
    selectedInterval.value = collectedInterval;
    // 주기 변경 시 자동으로 데이터 갱신
    if (selectedTicker.value) {
      updateAvailableDates().then(() => fetchData());
    }
  } else {
    console.warn('[TickerDataViewer] 유효하지 않은 주기:', collectedInterval);
  }
};
</script>

<script>
export default {
  name: 'TickerDataViewer'
}
</script>

<style scoped>
.viewer-container {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  height: 100%;
}

.control-bar {
  display: flex;
  align-items: center;
  gap: 2rem;
  padding: 1.25rem;
  border-radius: 12px;
}

.control-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.control-group label {
  font-size: 0.75rem;
  font-weight: bold;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

select {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: white;
  padding: 8px 12px;
  border-radius: 8px;
  min-width: 180px;
  outline: none;
}

.searchable-select-wrapper {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.ticker-search-input {
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #fff;
  padding: 5px 10px;
  border-radius: 4px;
  font-size: 0.8rem;
}

.ticker-search-input:focus {
  border-color: var(--primary);
  outline: none;
}

select option {
  background: #1e1e2d;
  color: white;
}

.tabs {
  display: flex;
  background: rgba(255, 255, 255, 0.05);
  padding: 4px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.tabs button {
  padding: 6px 16px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 0.85rem;
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.2s;
}

.tabs button.active {
  background: var(--primary);
  color: #1e1e2d;
  font-weight: bold;
  box-shadow: 0 4px 12px rgba(0, 255, 149, 0.3);
}

.export-btn {
  margin-left: auto;
  align-self: flex-end;
  padding: 10px 20px;
  background: rgba(0, 255, 149, 0.1);
  border: 1px solid rgba(0, 255, 149, 0.2);
  color: var(--primary);
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.2s;
}

.export-btn:hover:not(:disabled) {
  background: rgba(0, 255, 149, 0.2);
  border-color: var(--primary);
}

.export-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.delete-btn {
  margin-left: 12px;
  align-self: flex-end;
  padding: 10px 20px;
  background: rgba(255, 107, 107, 0.1);
  border: 1px solid rgba(255, 107, 107, 0.2);
  color: #ff6b6b;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.2s;
}

.delete-btn:hover:not(:disabled) {
  background: rgba(255, 107, 107, 0.2);
  border-color: #ff6b6b;
}

.delete-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.refresh-btn {
  margin-left: 12px;
  align-self: flex-end;
  padding: 10px 20px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: white;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.2s;
}

.refresh-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.1);
  border-color: var(--primary);
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.section-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: var(--primary);
}

.section-header .count {
  font-size: 0.85rem;
  color: var(--text-muted);
}

.chart-section {
  padding: 1.5rem;
  border-radius: 16px;
}

.chart-wrapper {
  height: 350px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 12px;
  overflow: hidden;
}

.table-section {
  padding: 1.5rem;
  border-radius: 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.table-wrapper {
  position: relative;
  flex: 1;
  overflow-y: auto;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.05);
  min-height: 300px;
}

table {
  width: 100%;
  border-collapse: collapse;
  text-align: right;
  font-size: 0.9rem;
}

thead {
  position: sticky;
  top: 0;
  background: #1e1e2d;
  z-index: 10;
}

th {
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-muted);
  font-weight: normal;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

th { text-align: right; }
th.checkbox-col { text-align: center; width: 40px; }
th:nth-child(2) { text-align: left; }
th:nth-child(3) { text-align: center; }

.checkbox-col {
  width: 40px;
  text-align: center;
  padding: 12px 8px !important;
}

.checkbox-col input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
  accent-color: var(--primary);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 15px;
}

.selection-count {
  font-size: 0.85rem;
  color: var(--primary);
  background: rgba(0, 255, 149, 0.1);
  padding: 2px 10px;
  border-radius: 12px;
  font-weight: bold;
}

.selected-list-mini {
  max-height: 100px;
  overflow-y: auto;
  background: rgba(0, 0, 0, 0.2);
  padding: 10px;
  border-radius: 8px;
  font-size: 0.85rem;
  color: var(--text-muted);
  margin: 10px 0;
  word-break: break-all;
}

.checked-row td {
  background: rgba(255, 255, 255, 0.05) !important;
}

td {
  padding: 10px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.02);
  color: var(--text-main);
  font-family: 'Fira Code', monospace;
}

.date { text-align: left; color: var(--text-muted); white-space: nowrap; }
.interval { text-align: center; color: var(--text-muted); opacity: 0.8; }
.high { color: #ff6b6b; }
.low { color: #4dabf7; }
.close { font-weight: bold; color: var(--primary); }
.vol { color: #fed330; }
.time-range { line-height: 1.2; }
.badge {
  padding: 3px 8px;
  border-radius: 4px;
  font-weight: 600;
}
.badge-tick { background: rgba(0, 168, 255, 0.2); color: #00a8ff; border: 1px solid rgba(0, 168, 255, 0.3); }
.badge-bar { background: rgba(156, 136, 255, 0.2); color: #9c88ff; border: 1px solid rgba(156, 136, 255, 0.3); }

tr:hover td {
  background: rgba(255, 255, 255, 0.02);
}

.no-data {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-style: italic;
}

.loading-overlay {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(2px);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  z-index: 20;
}

tr.selected-row td {
  background: rgba(0, 255, 149, 0.1) !important;
  color: var(--primary) !important;
  font-weight: bold;
}

.table-wrapper tr {
  cursor: pointer;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(0, 255, 149, 0.1);
  border-left-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.welcome-screen {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  background: rgba(255, 255, 255, 0.02);
  border: 2px dashed rgba(255, 255, 255, 0.05);
  border-radius: 24px;
  margin: 2rem;
  padding: 3rem;
}

.welcome-icon {
  font-size: 5rem;
  margin-bottom: 2rem;
  filter: drop-shadow(0 0 20px rgba(0, 255, 149, 0.2));
}

.welcome-screen h2 {
  color: var(--primary);
  margin: 0 0 1rem 0;
  font-size: 2rem;
}

.welcome-screen p {
  color: var(--text-muted);
  font-size: 1.1rem;
  max-width: 400px;
  line-height: 1.6;
}

.animated {
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-5px); }
  to { opacity: 1; transform: translateY(0); }
}

.date-select {
  min-width: 140px;
}

.chart-info {
  font-size: 0.85rem;
  color: var(--text-muted);
  background: rgba(255, 255, 255, 0.05);
  padding: 4px 12px;
  border-radius: 20px;
}

.gen-badge {
  font-size: 0.75rem;
  background: rgba(var(--primary-rgb, 0, 255, 149), 0.1);
  border: 1px solid rgba(var(--primary-rgb, 0, 255, 149), 0.2);
  color: var(--primary);
  padding: 4px 12px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.gen-badge .label {
  color: var(--text-muted);
  font-weight: normal;
}

.gen-badge .sep {
  opacity: 0.3;
}

/* Modal Styles */
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

.modal-content {
  width: 400px;
  padding: 2rem;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  animation: modalIn 0.3s ease-out;
}

@keyframes modalIn {
  from { transform: scale(0.9); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}

.modal-header h3 {
  margin: 0 0 1.5rem 0;
  color: #ff6b6b;
}

.modal-body p {
  margin: 0.5rem 0;
  line-height: 1.6;
}

.warning-text {
  color: #ff6b6b;
  font-size: 0.9rem;
  font-weight: bold;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 2rem;
}

.modal-cancel-btn {
  padding: 10px 20px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: white;
  border-radius: 8px;
  cursor: pointer;
}

.modal-delete-btn {
  padding: 10px 20px;
  background: #ff6b6b;
  color: white;
  border: none;
  border-radius: 8px;
  font-weight: bold;
  cursor: pointer;
}

.calendar-wrapper-viewer {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.05);
  padding: 10px;
  min-height: 400px;
}

.time-sub {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-top: 2px;
}

.tz-badge {
  display: inline-block;
  padding: 2px 6px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  font-size: 0.7rem;
  color: var(--text-muted);
  font-weight: bold;
}

.selected-row .tz-badge {
  background: rgba(0, 0, 0, 0.2);
  color: white;
}

.scenario-col {
  color: var(--text-muted);
  font-size: 0.8rem;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
