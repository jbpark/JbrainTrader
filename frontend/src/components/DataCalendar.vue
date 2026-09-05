<template>
  <div class="data-calendar">
    <div class="calendar-header">
      <button @click="changeMonth(-1)">&lt;</button>
      <h3>{{ year }}년 {{ month }}월</h3>
      <button @click="changeMonth(1)">&gt;</button>
    </div>
    
    <div class="calendar-grid">
      <div v-for="day in weekDays" :key="day" class="day-name">{{ day }}</div>
      <div v-for="empty in emptyDays" :key="'empty-'+empty" class="day-cell empty"></div>
      <div 
        v-for="date in monthDates" 
        :key="date.fullDate" 
        class="day-cell"
        :class="getStatusClass(date.fullDate)"
        :title="getStatusTitle(date.fullDate)"
        @click="onDateClick(date.fullDate, getStatus(date.fullDate))"
      >
        <span class="day-num">{{ date.day }}</span>
        
        <!-- 단일 또는 다중 종목 표시 -->
        <template v-if="props.ticker !== 'ALL' && (getStatus(date.fullDate) === 'COLLECTED' || getStatus(date.fullDate) === 'TICK_GENERATED')">
          <div v-if="props.tickerNames && props.tickerNames.length > 0" class="cell-tickers-wrapper">
            <div v-for="name in props.tickerNames" :key="name" class="cell-ticker-name miniature">
              {{ name }}
            </div>
          </div>
          <div v-else class="cell-ticker-name">
            {{ tickerName || ticker.split('.')[0] }}
          </div>
        </template>
        
        <!-- 전체 종목 표시 (ALL) -->
        <div v-else-if="props.ticker === 'ALL' && getStatusObj(date.fullDate).tickers?.length > 0" class="cell-tickers-wrapper">
          <div 
            v-for="t in getStatusObj(date.fullDate).tickers" 
            :key="t" 
            class="cell-ticker-name miniature"
            :title="resolveTickerName(t)"
          >
            {{ resolveTickerName(t) }}
          </div>
        </div>
      </div>
    </div>

    <div class="calendar-legend">
      <div class="legend-item"><span class="dot grey"></span> 데이터 없음</div>
      <div class="legend-item"><span class="dot white"></span> 수집 가능</div>
      <div class="legend-item"><span class="dot green"></span> 수집 완료</div>
      <div class="legend-item"><span class="dot blue"></span> 틱 생성</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { fetchDateStatus } from '../api';

const props = defineProps({
  ticker: String,
  tickerName: String,
  interval: String,
  source: String,
  selectedDate: String,
  tickerNames: Array // 여러 종목명 지원
});

const emit = defineEmits(['date-click']);

const year = ref(new Date().getFullYear());
const month = ref(new Date().getMonth() + 1);
const dateStatuses = ref({});
const weekDays = ['일', '월', '화', '수', '목', '금', '토'];

const emptyDays = computed(() => {
  const firstDay = new Date(year.value, month.value - 1, 1).getDay();
  return firstDay;
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

const loadStatus = async () => {
  if (!props.ticker) return;
  
  // 이전 상태 초기화 (종목 변경 시 잔상 제거)
  dateStatuses.value = {};
  
  try {
    const res = await fetchDateStatus(props.ticker, props.interval, year.value, month.value, props.source);
    if (res && res.month_status) {
      dateStatuses.value = res.month_status;
      
      // 선택된 날짜가 있으면 해당 날짜의 status를 자동으로 emit (localStorage 복원 시 대응)
      if (props.selectedDate && dateStatuses.value[props.selectedDate]) {
        const status = getStatus(props.selectedDate);
        emit('date-click', { date: props.selectedDate, status });
      }
    }
  } catch (err) {
    console.error("Failed to load date status:", err);
  }
};

const changeMonth = (delta) => {
  month.value += delta;
  if (month.value > 12) {
    month.value = 1;
    year.value += 1;
  } else if (month.value < 1) {
    month.value = 12;
    year.value -= 1;
  }
  // loadStatus()는 이제 watch(year/month)에서 처리됨
};

const getStatusClass = (date) => {
  const classes = [];
  if (date === props.selectedDate) classes.push('selected');
  
  const status = getStatus(date);
  if (status === 'TICK_GENERATED') classes.push('status-tick-generated');
  else if (status === 'COLLECTED') classes.push('status-collected');
  else if (status === 'AVAILABLE') classes.push('status-available');
  else classes.push('status-none');
  
  return classes.join(' ');
};

const getStatusTitle = (date) => {
  const data = dateStatuses.value[date];
  const status = typeof data === 'object' ? data.status : data;
  const tickers = typeof data === 'object' ? data.tickers : [];

  if (status === 'TICK_GENERATED') return `틱 데이터 생성됨 ${tickers.length > 0 ? '(' + tickers.join(', ') + ')' : ''}`;
  if (status === 'COLLECTED') return `원본 데이터 수집 완료됨 ${tickers.length > 0 ? '(' + tickers.join(', ') + ')' : ''}`;
  if (status === 'AVAILABLE') return '수집 가능일 (클릭하여 선택)';
  return '데이터 없음 (기간 만료 또는 휴장)';
};

const getStatus = (date) => {
  const data = dateStatuses.value[date];
  if (typeof data === 'object') return data.status || 'NO_DATA';
  return data || 'NO_DATA';
};

const getStatusObj = (date) => {
  const data = dateStatuses.value[date];
  if (typeof data === 'object') return data;
  return { status: data || 'NO_DATA', tickers: [] };
};

const onDateClick = (date, status) => {
  emit('date-click', { date, status });
};

// 티커 코드를 이름으로 변환하는 보조 함수
const resolveTickerName = (ticker) => {
  if (!ticker) return '';
  const pureTicker = ticker.split('.')[0];
  
  // 이미 이름이 온 경우(백엔드에서 변환 성공) 그대로 반환
  if (isNaN(ticker.charAt(0)) && ticker.charAt(0) !== '0') return ticker;

  // 1. localStorage의 tickerNameMap 확인 (가장 포괄적)
  try {
    const nameMap = JSON.parse(localStorage.getItem('tickerNameMap') || '{}');
    if (nameMap[ticker]) return nameMap[ticker];
    if (nameMap[pureTicker]) return nameMap[pureTicker];
  } catch (e) {}

  // 2. localStorage의 수집기 종목 리스트 확인
  try {
    const saved = localStorage.getItem('collectorSelectedTickers');
    if (saved) {
      const tickers = JSON.parse(saved);
      const found = tickers.find(item => 
        item.ticker === ticker || 
        item.ticker.split('.')[0] === pureTicker
      );
      if (found && found.name && found.name !== found.ticker) return found.name;
    }
  } catch (e) {}
  
  // 3. 일치하는 게 없으면 백엔드에서 받은 값 그대로(티커) 표시
  return pureTicker;
};

// 모든 관련 상태 변화 시 로드
watch([() => props.ticker, () => props.interval, () => props.source, year, month], loadStatus);

defineExpose({ refresh: loadStatus });

onMounted(loadStatus);
</script>

<style scoped>
.data-calendar {
  background: #252525;
  padding: 15px;
  border-radius: 8px;
  border: 1px solid #333;
  margin-top: 15px;
}

.calendar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.calendar-header h3 {
  margin: 0;
  font-size: 0.95rem;
  color: #3498db;
}

.calendar-header button {
  background: transparent;
  border: 1px solid #444;
  color: white;
  padding: 2px 8px;
  cursor: pointer;
  border-radius: 4px;
}

.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 4px;
  text-align: center;
}

.day-name {
  font-size: 0.75rem;
  color: #888;
  padding-bottom: 5px;
}

.day-cell {
  min-height: 70px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  font-size: 0.8rem;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.05);
  cursor: pointer;
  transition: transform 0.1s;
  position: relative;
  padding: 5px 3px;
  overflow: hidden;
}

.day-num {
  font-weight: bold;
  flex-shrink: 0;
  line-height: 1.4;
}

.cell-ticker-name {
  font-size: 0.65rem;
  margin-top: 3px;
  text-align: center;
  word-break: keep-all;
  line-height: 1.2;
  opacity: 0.9;
  width: 100%;
}

.cell-tickers-wrapper {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 100%;
  flex: 1;
  overflow: hidden;
  margin-top: 3px;
  justify-content: center;
}

.cell-ticker-name.miniature {
  font-size: 0.6rem;
  margin-top: 0;
  background: rgba(0, 0, 0, 0.25);
  padding: 2px 3px;
  border-radius: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  width: 100%;
  box-sizing: border-box;
  text-align: center;
  line-height: 1.3;
}

.day-cell:hover {
  transform: scale(1.1);
  z-index: 1;
}

.day-cell.status-none {
  background: #333;
  color: #666;
}

.day-cell.status-available {
  background: #fff;
  color: #000;
  font-weight: bold;
}

.day-cell.status-collected {
  background: #27ae60;
  color: white;
  font-weight: bold;
}

.day-cell.status-tick-generated {
  background: #3498db;
  color: white;
  font-weight: bold;
}

.day-cell.selected {
  outline: 3px solid #f1c40f; /* 선택된 날짜는 노란색 테두리로 강조 */
  outline-offset: -3px;
  box-shadow: 0 0 15px rgba(241, 196, 15, 0.8);
  z-index: 2;
  transform: scale(1.05); /* 선택 시 살짝 확대 */
}

.day-cell.selected::after {
  content: '✓';
  position: absolute;
  top: 2px;
  right: 5px;
  color: #f1c40f;
  font-weight: bold;
  font-size: 0.8rem;
  text-shadow: 0 0 5px rgba(0,0,0,0.5);
}

.calendar-legend {
  margin-top: 15px;
  display: flex;
  gap: 15px;
  font-size: 0.75rem;
  justify-content: center;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
  color: #bbb;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.dot.grey { background: #333; }
.dot.white { background: #fff; }
.dot.green { background: #27ae60; }
.dot.blue { background: #3498db; }
</style>
