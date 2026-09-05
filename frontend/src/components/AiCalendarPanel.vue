<template>
  <div class="ai-cal">
    <!-- Left: 프로파일 목록 -->
    <div class="side glass">
      <div class="side-head">
        <h3>📅 캘린더 프로파일</h3>
        <button class="new-btn" @click="handleNew">+ 새 프로파일</button>
      </div>
      <ul class="profile-list">
        <li
          v-for="p in profiles"
          :key="p.id"
          :class="{ on: selected?.id === p.id }"
          @click="handleSelect(p)"
        >
          <div class="p-name">{{ p.name }}</div>
          <div class="p-meta">
            <span class="status" :class="`st-${p.last_status || 'none'}`">
              {{ statusLabel(p.last_status) }}
            </span>
            <span v-if="p.last_finished_at" class="muted">{{ p.last_finished_at }}</span>
          </div>
        </li>
        <li v-if="profiles.length === 0" class="empty">프로파일이 없습니다.</li>
      </ul>
    </div>

    <!-- Right: 편집 + 결과 -->
    <div class="main glass">
      <div v-if="!isEditing" class="result-empty">왼쪽에서 프로파일을 선택하세요.</div>

      <template v-else>
        <div class="edit-box">
          <div class="row">
            <input v-model="name" class="in" placeholder="프로파일 이름" />
            <select v-model="model" class="in sel">
              <option v-for="m in models" :key="m.id" :value="m.id">{{ m.label }}</option>
            </select>
          </div>
          <textarea v-model="prompt" class="in ta" rows="5"
                    placeholder="어떤 일정을 정리할지 지시를 적으세요."></textarea>
          <div class="row btns">
            <button class="btn" @click="handleSave">💾 저장</button>
            <button class="btn danger" v-if="selected?.id" @click="handleDelete">🗑 삭제</button>
            <button class="btn run" :disabled="running" @click="handleRun">
              <span v-if="running" class="spinner-sm"></span>
              {{ running ? '일정 분석 중... (최대 15분)' : '▶ 캘린더 생성' }}
            </button>
          </div>
        </div>

        <div v-if="result" class="result-box">
          <div class="result-header">
            <h3 style="margin: 0; color: var(--primary); font-size: 1rem">🗓 주요 일정</h3>
            <span v-if="result.finished_at" class="muted small">
              {{ result.finished_at }} · {{ result.model }}
            </span>
          </div>

          <div v-if="result.status === 'running'" class="result-empty">
            <span class="mini-spinner"></span> 일정과 관련 종목을 조사하는 중입니다... (최대 15분)
          </div>
          <div v-else-if="result.status === 'error'" class="result-error">
            ⚠️ {{ result.error }}
            <pre v-if="result.raw_text" class="raw-text">{{ result.raw_text }}</pre>
          </div>

          <template v-else-if="result.status === 'done'">
            <!-- 월 이동 -->
            <div class="cal-nav">
              <div class="month-nav">
                <button class="nav-btn" title="이전 달" @click="shiftMonth(-1)">&#10094;</button>
                <span class="cal-title">{{ viewYear }}년 {{ viewMonth + 1 }}월</span>
                <button class="nav-btn" title="다음 달" @click="shiftMonth(1)">&#10095;</button>
              </div>
              <button v-if="!isCurrentMonth" class="today-btn" @click="goToday">오늘</button>
              <span class="muted small">일정 {{ result.events.length }}건 · 관심 종목 {{ result.watchlist.length }}건</span>
            </div>

            <!-- 캘린더 -->
            <div class="cal-grid">
              <div v-for="d in ['일','월','화','수','목','금','토']" :key="d" class="cal-dow">{{ d }}</div>
              <div
                v-for="(cell, i) in monthCells"
                :key="i"
                class="cal-cell"
                :class="{ blank: !cell.date, today: cell.date === todayStr,
                          on: cell.date === selectedDate, has: cell.events.length > 0 }"
                @click="cell.date && (selectedDate = cell.date)"
              >
                <template v-if="cell.date">
                  <span class="d-num">{{ cell.day }}</span>
                  <div class="d-events">
                    <span
                      v-for="(e, j) in cell.events.slice(0, 3)"
                      :key="j"
                      class="d-dot"
                      :class="`imp-${impClass(e.importance)}`"
                      :title="e.title"
                    >{{ e.title }}</span>
                    <span v-if="cell.events.length > 3" class="d-more">+{{ cell.events.length - 3 }}</span>
                  </div>
                </template>
              </div>
            </div>

            <!-- 선택한 날짜의 일정 -->
            <div class="day-detail">
              <h4>{{ selectedDate || '날짜를 선택하세요' }}</h4>
              <div v-if="selectedEvents.length === 0" class="muted small">이 날짜에는 등록된 일정이 없습니다.</div>
              <div v-for="(e, i) in selectedEvents" :key="i" class="event-card">
                <div class="e-head">
                  <span class="cat">{{ e.category }}</span>
                  <strong>{{ e.title }}</strong>
                  <span class="imp" :class="`imp-${impClass(e.importance)}`">{{ e.importance }}</span>
                </div>
                <p v-if="e.description" class="e-desc">{{ e.description }}</p>
                <div v-if="e.stocks.length" class="e-stocks">
                  <span v-for="(s, k) in e.stocks" :key="k" class="stock-chip"
                        :class="`impact-${impactClass(s.impact)}`" :title="s.reason">
                    {{ s.name }} <em>{{ s.ticker }}</em> · {{ s.impact }}
                  </span>
                </div>
              </div>
            </div>

            <!-- 일정 영향으로 오를 수 있는 종목 -->
            <div class="watch-section">
              <h3 class="sec-title">📈 상승 기대 종목 <span class="muted small">
                (앞으로의 일정에서 긍정 영향을 받는 종목)</span></h3>
              <div v-if="(result.upside_stocks || []).length === 0" class="muted small">
                남은 일정 중 긍정 영향으로 지목된 종목이 없습니다.
              </div>
              <div class="upside-grid">
                <div v-for="(u, i) in result.upside_stocks || []" :key="u.ticker || i" class="upside-card">
                  <div class="u-head">
                    <span class="u-rank">{{ i + 1 }}</span>
                    <strong>{{ u.name }}</strong>
                    <span class="muted small">{{ u.ticker }}</span>
                    <span class="u-score" :title="'일정 중요도를 합산한 점수'">{{ u.score }}점</span>
                  </div>
                  <div class="u-meta">
                    관련 일정 {{ u.event_count }}건 · 가장 가까운 일정 {{ u.nearest_date }}
                    <span v-if="isSoon(u.nearest_date)" class="soon-tag">임박</span>
                  </div>
                  <ul class="u-events">
                    <li v-for="(e, j) in u.events.slice(0, 3)" :key="j">
                      <span class="u-date">{{ e.date.slice(5) }}</span>
                      <span class="u-title">{{ e.title }}</span>
                      <span class="imp" :class="`imp-${impClass(e.importance)}`">{{ e.importance }}</span>
                      <div v-if="e.reason" class="u-reason">{{ e.reason }}</div>
                    </li>
                    <li v-if="u.events.length > 3" class="muted small">
                      외 {{ u.events.length - 3 }}건
                    </li>
                  </ul>
                </div>
              </div>
            </div>

            <!-- 일정 기반 관심 종목 -->
            <div class="watch-section">
              <h3 class="sec-title">🎯 일정 기반 관심 종목 · 매매 타이밍</h3>
              <table class="watch-table">
                <thead>
                  <tr>
                    <th>종목</th><th>일정</th><th>매수 타이밍</th><th>매도 타이밍</th>
                    <th class="tr">목표가</th><th class="tr">손절가</th><th class="tr">기대수익</th><th>신뢰도</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(w, i) in result.watchlist" :key="i"
                      :class="{ soon: isSoon(w.event_date) }">
                    <td>
                      <div class="w-name">{{ w.name }}</div>
                      <div class="muted small">{{ w.ticker }}</div>
                    </td>
                    <td>
                      <div>{{ w.event }}</div>
                      <div class="muted small">{{ w.event_date }}</div>
                    </td>
                    <td class="w-timing buy">{{ w.buy_timing }}</td>
                    <td class="w-timing sell">{{ w.sell_timing }}</td>
                    <td class="tr up">{{ won(w.target_price) }}</td>
                    <td class="tr down">{{ won(w.stop_loss) }}</td>
                    <td class="tr">{{ w.expected_return || '-' }}</td>
                    <td><span class="conf" :class="`imp-${impClass(w.confidence)}`">{{ w.confidence }}</span></td>
                  </tr>
                  <tr v-if="result.watchlist.length === 0">
                    <td colspan="8" class="muted" style="text-align:center;padding:1rem">
                      관심 종목이 없습니다.
                    </td>
                  </tr>
                </tbody>
              </table>
              <p class="disclaimer">
                ※ AI가 생성한 참고용 정보입니다. 일정은 변경될 수 있으니 반드시 원문 공시를 확인하세요.
                투자 판단과 책임은 본인에게 있습니다.
              </p>
            </div>
          </template>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import {
  fetchAiCalendars, createAiCalendar, updateAiCalendar, deleteAiCalendar,
  runAiCalendar, fetchAiCalendarResult, fetchAiPickModels,
} from '../api';

const FALLBACK_MODELS = [
  { id: 'claude-fable-5', label: 'Fable 5 (최고 성능)' },
  { id: 'claude-opus-5', label: 'Opus 5' },
  { id: 'claude-sonnet-5', label: 'Sonnet 5' },
  { id: 'claude-haiku-4-5', label: 'Haiku 4.5 (빠름/저비용)' },
];

const profiles = ref([]);
const models = ref(FALLBACK_MODELS);
const defaultModel = ref('claude-opus-5');
const selected = ref(null);
const isEditing = ref(false);
const name = ref('');
const prompt = ref('');
const model = ref('claude-opus-5');
const result = ref(null);
const running = ref(false);
const selectedDate = ref(null);

const todayStr = new Date().toISOString().split('T')[0];
const viewYear = ref(new Date().getFullYear());
const viewMonth = ref(new Date().getMonth());

let pollId = null;

const statusLabel = (s) => ({ done: '완료', running: '실행 중', error: '오류' }[s] || '미실행');
const impClass = (v) => ({ '높음': 'high', '중간': 'mid', '낮음': 'low' }[v] || 'mid');
const impactClass = (v) => ({ '긍정': 'pos', '부정': 'neg' }[v] || 'neu');
const won = (v) => (typeof v === 'number' ? v.toLocaleString() : '-');

// 일정 날짜가 오늘부터 7일 이내면 강조
const isSoon = (d) => {
  if (!d) return false;
  const diff = (new Date(d) - new Date(todayStr)) / 86400000;
  return diff >= 0 && diff <= 7;
};

const eventsByDate = computed(() => {
  const map = {};
  for (const e of result.value?.events || []) {
    (map[e.date] ||= []).push(e);
  }
  return map;
});

const monthCells = computed(() => {
  const first = new Date(viewYear.value, viewMonth.value, 1);
  const daysInMonth = new Date(viewYear.value, viewMonth.value + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < first.getDay(); i++) cells.push({ date: null, events: [] });
  for (let d = 1; d <= daysInMonth; d++) {
    const date = `${viewYear.value}-${String(viewMonth.value + 1).padStart(2, '0')}`
               + `-${String(d).padStart(2, '0')}`;
    cells.push({ date, day: d, events: eventsByDate.value[date] || [] });
  }
  return cells;
});

const selectedEvents = computed(() => eventsByDate.value[selectedDate.value] || []);

const shiftMonth = (delta) => {
  const d = new Date(viewYear.value, viewMonth.value + delta, 1);
  viewYear.value = d.getFullYear();
  viewMonth.value = d.getMonth();
};

const isCurrentMonth = computed(() => {
  const now = new Date();
  return viewYear.value === now.getFullYear() && viewMonth.value === now.getMonth();
});

const goToday = () => {
  const now = new Date();
  viewYear.value = now.getFullYear();
  viewMonth.value = now.getMonth();
  selectedDate.value = todayStr;
};

const loadModels = async () => {
  const res = await fetchAiPickModels();
  if (res?.models?.length) {
    models.value = res.models;
    defaultModel.value = res.default || res.models[0].id;
  }
};

const loadProfiles = async () => {
  profiles.value = await fetchAiCalendars() || [];
  if (selected.value) {
    const cur = profiles.value.find(p => p.id === selected.value.id);
    if (cur) selected.value = cur;
  }
};

const loadResult = async (id) => {
  const res = await fetchAiCalendarResult(id);
  if (!res || res.status === 'NONE') {
    result.value = null;
    running.value = false;
    return;
  }
  result.value = res;
  running.value = res.status === 'running';
  if (res.status === 'done' && res.events?.length && !selectedDate.value) {
    // 오늘 이후 가장 가까운 일정 날짜를 기본 선택
    const next = res.events.find(e => e.date >= todayStr) || res.events[0];
    selectedDate.value = next.date;
    const d = new Date(next.date);
    viewYear.value = d.getFullYear();
    viewMonth.value = d.getMonth();
  }
  if (running.value) startPolling(id); else stopPolling();
};

const startPolling = (id) => {
  stopPolling();
  pollId = setInterval(() => loadResult(id), 5000);
};
const stopPolling = () => { clearInterval(pollId); pollId = null; };

const handleSelect = async (p) => {
  selected.value = p;
  name.value = p.name;
  prompt.value = p.prompt;
  model.value = p.model || defaultModel.value;
  selectedDate.value = null;
  isEditing.value = true;
  await loadResult(p.id);
};

const handleNew = () => {
  selected.value = null;
  name.value = '';
  prompt.value = '';
  model.value = defaultModel.value;
  result.value = null;
  running.value = false;
  selectedDate.value = null;
  stopPolling();
  isEditing.value = true;
};

const handleSave = async () => {
  if (!name.value.trim() || !prompt.value.trim()) {
    alert('이름과 프롬프트를 입력하세요.');
    return;
  }
  const res = selected.value?.id
    ? await updateAiCalendar(selected.value.id, name.value, prompt.value, model.value)
    : await createAiCalendar(name.value, prompt.value, model.value);
  if (res.status !== 'SUCCESS') {
    alert('저장 실패: ' + res.message);
    return;
  }
  await loadProfiles();
  if (res.id) {
    const created = profiles.value.find(p => p.id === res.id);
    if (created) await handleSelect(created);
  }
};

const handleDelete = async () => {
  if (!selected.value?.id) return;
  if (!confirm(`'${selected.value.name}' 프로파일을 삭제할까요?`)) return;
  await deleteAiCalendar(selected.value.id);
  selected.value = null;
  isEditing.value = false;
  result.value = null;
  await loadProfiles();
};

const handleRun = async () => {
  if (!selected.value?.id) {
    alert('먼저 프로파일을 저장한 뒤 실행하세요.');
    return;
  }
  if (name.value !== selected.value.name || prompt.value !== selected.value.prompt
      || model.value !== (selected.value.model || defaultModel.value)) {
    const r = await updateAiCalendar(selected.value.id, name.value, prompt.value, model.value);
    if (r.status !== 'SUCCESS') {
      alert('저장 실패: ' + r.message);
      return;
    }
    selected.value = { ...selected.value, name: name.value, prompt: prompt.value, model: model.value };
  }
  const res = await runAiCalendar(selected.value.id);
  if (res.status === 'ERROR') {
    alert('실행 실패: ' + res.message);
    return;
  }
  running.value = true;
  result.value = { status: 'running', events: [], watchlist: [] };
  startPolling(selected.value.id);
};

onMounted(async () => {
  await loadModels();
  await loadProfiles();
  if (profiles.value.length) await handleSelect(profiles.value[0]);
});
onUnmounted(stopPolling);
</script>

<style scoped>
.ai-cal { display: grid; grid-template-columns: 260px 1fr; gap: 1rem; align-items: start; }
.glass { background: rgba(255,255,255,0.03); border-radius: 16px; padding: 1rem 1.2rem; }

.side-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.8rem; }
.side-head h3 { margin: 0; font-size: 0.95rem; }
.new-btn {
  background: rgba(0,208,132,0.15); border: 1px solid rgba(0,208,132,0.5);
  color: var(--success); border-radius: 6px; padding: 4px 10px; cursor: pointer; font-size: 0.78rem;
}
.profile-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.profile-list li {
  padding: 8px 10px; border-radius: 8px; cursor: pointer;
  background: rgba(255,255,255,0.03); border: 1px solid transparent;
}
.profile-list li:hover { background: rgba(255,255,255,0.07); }
.profile-list li.on { border-color: var(--primary); background: rgba(79,195,247,0.1); }
.profile-list li.empty { cursor: default; color: var(--text-muted); font-size: 0.82rem; }
.p-name { font-weight: 600; font-size: 0.88rem; }
.p-meta { display: flex; gap: 8px; align-items: center; margin-top: 3px; }
.status { font-size: 0.72rem; }
.st-done { color: var(--success); }
.st-running { color: #FFC107; }
.st-error { color: var(--danger); }
.st-none { color: var(--text-muted); }

.in {
  background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.15);
  color: var(--text-main); border-radius: 8px; padding: 8px 12px; font-size: 0.88rem;
}
.row { display: flex; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.row .in:first-child { flex: 1; }
.sel { min-width: 180px; }
.ta { width: 100%; resize: vertical; font-family: inherit; line-height: 1.6; }
.btns { margin-top: 4px; }
.btn {
  background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.2);
  color: var(--text-main); border-radius: 8px; padding: 7px 16px; cursor: pointer; font-size: 0.85rem;
}
.btn:hover { background: rgba(255,255,255,0.15); }
.btn.danger { color: var(--danger); border-color: rgba(255,77,77,0.4); }
.btn.run {
  background: rgba(79,195,247,0.15); border-color: rgba(79,195,247,0.5); color: var(--primary);
  display: inline-flex; align-items: center; gap: 6px;
}
.btn.run:disabled { opacity: 0.6; cursor: not-allowed; }

.result-box { margin-top: 1.2rem; }
.result-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.8rem; }
.result-empty { color: var(--text-muted); padding: 1.5rem 0; text-align: center; font-size: 0.9rem; }
.result-error {
  color: var(--danger); background: rgba(255,77,77,0.08);
  border: 1px solid rgba(255,77,77,0.3); border-radius: 10px; padding: 0.9rem;
}
.raw-text {
  margin-top: 0.6rem; max-height: 220px; overflow: auto; white-space: pre-wrap;
  font-size: 0.75rem; color: var(--text-muted);
}

/* 캘린더 */
.cal-nav { display: flex; align-items: center; gap: 12px; margin-bottom: 0.8rem; flex-wrap: wrap; }
/* 화살표와 제목을 하나의 알약 형태로 묶어 자연스럽게 */
.month-nav {
  display: inline-flex; align-items: center; gap: 2px;
  background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);
  border-radius: 999px; padding: 3px;
}
.cal-title {
  font-weight: 700; font-size: 0.95rem; min-width: 108px;
  text-align: center; user-select: none;
}
.nav-btn {
  background: rgba(255,255,255,0.07); border: none; color: var(--text-main);
  border-radius: 50%; width: 28px; height: 28px; cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 0.7rem; line-height: 1; padding: 0;
  transition: background 0.15s, color 0.15s;
}
.nav-btn:hover { background: rgba(79,195,247,0.15); color: var(--primary); }
.nav-btn:active { transform: scale(0.92); }
.today-btn {
  background: rgba(0,208,132,0.12); border: 1px solid rgba(0,208,132,0.4);
  color: var(--success); border-radius: 999px; padding: 4px 14px;
  cursor: pointer; font-size: 0.78rem;
}
.today-btn:hover { background: rgba(0,208,132,0.25); }
.cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
.cal-dow { text-align: center; font-size: 0.75rem; color: var(--text-muted); padding: 4px 0; }
.cal-cell {
  min-height: 78px; border-radius: 8px; padding: 4px 5px; cursor: pointer;
  background: rgba(255,255,255,0.03); border: 1px solid transparent; overflow: hidden;
}
.cal-cell.blank { background: transparent; cursor: default; }
.cal-cell:not(.blank):hover { background: rgba(255,255,255,0.08); }
.cal-cell.has { background: rgba(79,195,247,0.07); }
.cal-cell.today { border-color: rgba(0,208,132,0.6); }
.cal-cell.on { border-color: var(--primary); background: rgba(79,195,247,0.16); }
.d-num { font-size: 0.78rem; color: var(--text-muted); }
.d-events { display: flex; flex-direction: column; gap: 2px; margin-top: 3px; }
.d-dot {
  font-size: 0.66rem; line-height: 1.25; padding: 1px 4px; border-radius: 4px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.d-more { font-size: 0.64rem; color: var(--text-muted); }
.imp-high { background: rgba(255,77,77,0.18); color: #FF6B6B; }
.imp-mid { background: rgba(255,193,7,0.16); color: #FFC107; }
.imp-low { background: rgba(255,255,255,0.08); color: var(--text-muted); }

/* 선택 날짜 상세 */
.day-detail { margin-top: 1rem; }
.day-detail h4 { margin: 0 0 0.6rem; font-size: 0.92rem; color: var(--primary); }
.event-card {
  border: 1px solid rgba(255,255,255,0.1); border-radius: 10px;
  padding: 0.8rem 1rem; margin-bottom: 0.6rem; background: rgba(255,255,255,0.02);
}
.e-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.cat {
  font-size: 0.72rem; padding: 2px 8px; border-radius: 999px;
  background: rgba(79,195,247,0.15); color: var(--primary);
}
.imp { font-size: 0.72rem; padding: 2px 8px; border-radius: 999px; }
.e-desc { margin: 0.5rem 0 0.6rem; font-size: 0.85rem; line-height: 1.6; color: var(--text-main); }
.e-stocks { display: flex; gap: 6px; flex-wrap: wrap; }
.stock-chip {
  font-size: 0.76rem; padding: 3px 10px; border-radius: 999px; cursor: help;
  border: 1px solid rgba(255,255,255,0.15);
}
.stock-chip em { color: var(--text-muted); font-style: normal; font-size: 0.7rem; }
.impact-pos { background: rgba(0,208,132,0.12); border-color: rgba(0,208,132,0.4); }
.impact-neg { background: rgba(255,77,77,0.12); border-color: rgba(255,77,77,0.4); }
.impact-neu { background: rgba(255,255,255,0.05); }

/* 상승 기대 종목 */
.upside-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 10px;
}
.upside-card {
  border: 1px solid rgba(0,208,132,0.25); border-radius: 10px;
  padding: 0.7rem 0.9rem; background: rgba(0,208,132,0.05);
}
.u-head { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }
.u-rank {
  width: 20px; height: 20px; border-radius: 50%; font-size: 0.7rem;
  display: inline-flex; align-items: center; justify-content: center;
  background: rgba(0,208,132,0.2); color: var(--success); font-weight: 700;
}
.u-score {
  margin-left: auto; font-size: 0.74rem; padding: 2px 8px; border-radius: 999px;
  background: rgba(0,208,132,0.15); color: var(--success); cursor: help;
}
.u-meta { font-size: 0.74rem; color: var(--text-muted); margin: 5px 0 6px; }
.soon-tag {
  margin-left: 6px; font-size: 0.68rem; padding: 1px 6px; border-radius: 4px;
  background: rgba(255,193,7,0.2); color: #FFC107;
}
.u-events { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 5px; }
.u-events li { font-size: 0.76rem; line-height: 1.4; }
.u-date { color: var(--primary); margin-right: 6px; }
.u-title { color: var(--text-main); }
.u-reason { color: var(--text-muted); font-size: 0.72rem; margin-top: 2px; line-height: 1.45; }

/* 관심 종목 */
.watch-section { margin-top: 1.4rem; }
.sec-title { font-size: 0.98rem; color: var(--secondary); margin: 0 0 0.7rem; }
.watch-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
.watch-table th {
  text-align: left; padding: 8px 10px; color: var(--primary);
  border-bottom: 1px solid rgba(255,255,255,0.15); font-size: 0.78rem; white-space: nowrap;
}
.watch-table td { padding: 9px 10px; border-bottom: 1px solid rgba(255,255,255,0.06); vertical-align: top; }
.watch-table tr.soon { background: rgba(255,193,7,0.06); }
.w-name { font-weight: 700; }
.w-timing { line-height: 1.5; max-width: 240px; }
.w-timing.buy { color: #7ee0b8; }
.w-timing.sell { color: #9ecbff; }
.tr { text-align: right; }
.up { color: var(--success); }
.down { color: var(--danger); }
.conf { font-size: 0.72rem; padding: 2px 8px; border-radius: 999px; }
.muted { color: var(--text-muted); }
.small { font-size: 0.75rem; }
.disclaimer { margin-top: 0.8rem; font-size: 0.75rem; color: var(--text-muted); line-height: 1.5; }

.spinner-sm, .mini-spinner {
  display: inline-block; width: 12px; height: 12px;
  border: 2px solid rgba(79,195,247,0.3); border-top-color: var(--primary);
  border-radius: 50%; animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 900px) {
  .ai-cal { grid-template-columns: 1fr; }
}
</style>
