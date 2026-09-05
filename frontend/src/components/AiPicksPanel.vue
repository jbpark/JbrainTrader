<template>
  <div class="main-tab-content glass" style="flex: 1; overflow: hidden; display: flex; flex-direction: column; gap: 1.5rem; padding: 2.5rem">
    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid var(--primary); padding-bottom: 1rem">
      <h2 style="color: var(--primary); margin: 0; display: flex; align-items: center; gap: 12px">
        <span style="font-size: 1.8rem">✨</span> AI 종목
      </h2>
      <div style="display: flex; align-items: center; gap: 14px">
        <button class="refresh-btn" @click="loadProfiles" title="모바일 등 다른 기기에서 변경된 내용을 다시 불러옵니다">🔄 새로고침</button>
        <div style="text-align: right">
          <div style="font-size: 0.9rem; color: var(--text-main); font-weight: 600">종목 선별 프로파일</div>
          <div style="font-size: 0.8rem; color: var(--primary)">{{ profiles.length }}개</div>
        </div>
      </div>
    </div>

    <div style="display: flex; gap: 20px; flex: 1; min-height: 0">
      <!-- List -->
      <div style="width: 280px; border-right: 1px solid rgba(255,255,255,0.1); overflow-y: auto; padding-right: 10px; display: flex; flex-direction: column; gap: 1rem">
        <button class="primary" style="width: 100%" @click="handleNew">+ 새 프로파일 생성</button>

        <div style="display: flex; flex-direction: column; gap: 8px">
          <div
            v-for="p in profiles"
            :key="p.id"
            class="pick-item-card"
            :class="{ active: selected?.id === p.id }"
            @click="handleSelect(p)"
          >
            <div style="display: flex; justify-content: space-between; align-items: center; width: 100%">
              <span class="pick-name">{{ p.name }}</span>
              <button class="danger-btn" @click.stop="handleDelete(p)">삭제</button>
            </div>
            <div class="pick-model">{{ modelLabel(p.model) }}</div>
            <div class="pick-status" v-if="p.last_status">
              <span :class="'st-' + p.last_status">{{ statusLabel(p.last_status) }}</span>
              <span v-if="p.last_finished_at" class="pick-time">{{ p.last_finished_at }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Editor + Result -->
      <div style="flex: 1; display: flex; flex-direction: column; gap: 1rem; min-width: 0; overflow-y: auto">
        <template v-if="isEditing">
          <div style="display: flex; flex-direction: column; gap: 8px">
            <label style="font-size: 0.85rem; color: var(--text-muted)">프로파일 명칭</label>
            <input
              type="text"
              placeholder="프로파일 이름을 입력하세요 (예: 주가_재무기반)"
              v-model="name"
              style="padding: 12px; font-size: 1.1rem; font-weight: bold; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1); color: white; border-radius: 8px"
            />
          </div>
          <div style="display: flex; flex-direction: column; gap: 8px">
            <label style="font-size: 0.85rem; color: var(--text-muted)">실행 AI 모델</label>
            <select v-model="model" class="model-select">
              <option v-for="m in models" :key="m.id" :value="m.id">{{ m.label }}</option>
            </select>
          </div>
          <div style="display: flex; flex-direction: column; gap: 8px">
            <label style="font-size: 0.85rem; color: var(--text-muted)">종목 선별 프롬프트</label>
            <textarea
              placeholder="AI에게 요청할 종목 선별 조건을 입력하세요"
              style="min-height: 140px; font-size: 0.95rem; padding: 15px; background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.1); color: #00f2fe; border-radius: 8px; resize: vertical; line-height: 1.6"
              v-model="prompt"
            ></textarea>
          </div>
          <div style="display: flex; gap: 12px; justify-content: flex-end">
            <button class="secondary" @click="cancelEdit" style="padding: 10px 20px">편집 취소</button>
            <button class="primary" @click="handleSave" style="padding: 10px 25px">저장하기</button>
            <button
              class="run-btn"
              @click="handleRun"
              :disabled="running || !selected?.id"
              title="프롬프트를 Claude CLI로 실행해 종목을 선별합니다"
            >
              <span v-if="running" class="mini-spinner"></span>
              {{ running ? '실행 중... (수 분 소요)' : '▶ 실행' }}
            </button>
          </div>

          <!-- Result -->
          <div v-if="result" class="result-box">
            <div class="result-header">
              <h3 style="margin: 0; color: var(--primary); font-size: 1rem">📋 선별 결과</h3>
              <div style="display: flex; align-items: center; gap: 12px">
                <button
                  v-if="result.status === 'done' && result.stocks.length > 0"
                  class="compare-btn"
                  :disabled="comparing"
                  @click="handleCompare"
                  title="선별된 종목들의 재무제표·투자지표를 비교 분석합니다"
                >
                  <span v-if="comparing" class="mini-spinner"></span>
                  {{ comparing ? '비교 분석 중...' : '📊 상세 비교' }}
                </button>
                <span v-if="result.finished_at" style="font-size: 0.78rem; color: var(--text-muted)">
                  {{ result.finished_at }} · {{ result.model }}
                </span>
              </div>
            </div>

            <div v-if="result.status === 'running'" class="result-empty">
              <span class="mini-spinner"></span> AI가 종목을 선별하는 중입니다... (최대 7분)
            </div>

            <div v-else-if="result.status === 'error'" class="result-error">
              ⚠️ {{ result.error }}
              <pre v-if="result.raw_text" class="raw-text">{{ result.raw_text }}</pre>
            </div>

            <template v-else-if="result.status === 'done' && result.stocks.length > 0">
              <table class="picks-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th class="sortable" @click="sortPicks('market')">시장{{ sortArrow(pickSort, 'market') }}</th>
                    <th class="sortable" @click="sortPicks('name')">종목명{{ sortArrow(pickSort, 'name') }}</th>
                    <th class="sortable" @click="sortPicks('ticker')">종목코드{{ sortArrow(pickSort, 'ticker') }}</th>
                    <th class="text-right sortable" @click="sortPicks('price')">현재 주가{{ sortArrow(pickSort, 'price') }}</th>
                    <th class="text-right sortable" @click="sortPicks('upside')">상승 여력{{ sortArrow(pickSort, 'upside') }}</th>
                    <th>선정 근거</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(s, i) in sortedStocks" :key="s.ticker || i">
                    <td class="muted">{{ i + 1 }}</td>
                    <td>
                      <span class="market-badge" :class="s.market === '코스피' ? 'kospi' : 'kosdaq'">{{ s.market }}</span>
                    </td>
                    <td class="stock-name">{{ s.name }}</td>
                    <td class="muted">{{ s.ticker }}</td>
                    <td class="text-right">{{ Number(s.price || 0).toLocaleString() }}원</td>
                    <td class="text-right upside">{{ s.upside }}</td>
                    <td class="reason">{{ s.reason }}</td>
                  </tr>
                </tbody>
              </table>
              <p class="disclaimer">※ AI가 생성한 참고용 정보입니다. 투자 판단과 책임은 본인에게 있습니다.</p>
            </template>
          </div>

          <!-- 상세 비교 (재무제표 / 투자지표) -->
          <div v-if="comparison" class="result-box">
            <div class="result-header">
              <h3 style="margin: 0; color: var(--secondary); font-size: 1rem">📊 상세 비교 (재무·투자지표)</h3>
              <div style="display: flex; align-items: center; gap: 12px">
                <button
                  v-if="comparison.status === 'done' && comparison.comparison.length > 0"
                  class="gsheet-btn"
                  :disabled="exportingSheet"
                  @click="handleExportComparison"
                  :title="`구글 시트의 '${selected?.name}' 탭에 업로드합니다`"
                >
                  <span v-if="exportingSheet" class="mini-spinner"></span>
                  {{ exportingSheet ? '업로드 중...' : '📗 구글 시트 업로드' }}
                </button>
                <a v-if="gsheetUrl" :href="gsheetUrl" target="_blank" class="gsheet-link">시트 열기 ↗</a>
                <span v-if="comparison.finished_at" style="font-size: 0.78rem; color: var(--text-muted)">
                  {{ comparison.finished_at }} · {{ comparison.model }}
                </span>
              </div>
            </div>

            <div v-if="comparison.status === 'running'" class="result-empty">
              <span class="mini-spinner"></span> 재무제표와 투자지표를 비교 분석하는 중입니다... (최대 15분)
            </div>

            <div v-else-if="comparison.status === 'error'" class="result-error">
              ⚠️ {{ comparison.error }}
              <pre v-if="comparison.raw_text" class="raw-text">{{ comparison.raw_text }}</pre>
            </div>

            <template v-else-if="comparison.status === 'done' && comparison.comparison.length > 0">
              <div class="table-scroll">
                <table class="picks-table compare-table">
                  <thead>
                    <tr>
                      <th class="sortable" @click="sortCompare('name')">종목명{{ sortArrow(compareSort, 'name') }}</th>
                      <th class="text-right sortable" @click="sortCompare('price')">주가{{ sortArrow(compareSort, 'price') }}</th>
                      <th class="text-right sortable" @click="sortCompare('market_cap')">시가총액(억){{ sortArrow(compareSort, 'market_cap') }}</th>
                      <th class="text-right sortable" @click="sortCompare('per')">PER{{ sortArrow(compareSort, 'per') }}</th>
                      <th class="text-right sortable" @click="sortCompare('pbr')">PBR{{ sortArrow(compareSort, 'pbr') }}</th>
                      <th class="text-right sortable" @click="sortCompare('roe')">ROE(%){{ sortArrow(compareSort, 'roe') }}</th>
                      <th class="text-right sortable" @click="sortCompare('revenue')">매출(억){{ sortArrow(compareSort, 'revenue') }}</th>
                      <th class="text-right sortable" @click="sortCompare('operating_profit')">영업이익(억){{ sortArrow(compareSort, 'operating_profit') }}</th>
                      <th class="text-right sortable" @click="sortCompare('net_income')">순이익(억){{ sortArrow(compareSort, 'net_income') }}</th>
                      <th class="text-right sortable" @click="sortCompare('operating_margin')">영업이익률(%){{ sortArrow(compareSort, 'operating_margin') }}</th>
                      <th class="text-right sortable" @click="sortCompare('debt_ratio')">부채비율(%){{ sortArrow(compareSort, 'debt_ratio') }}</th>
                      <th class="text-right sortable" @click="sortCompare('revenue_growth')">매출성장(%){{ sortArrow(compareSort, 'revenue_growth') }}</th>
                      <th class="text-right sortable" @click="sortCompare('dividend_yield')">배당(%){{ sortArrow(compareSort, 'dividend_yield') }}</th>
                      <th class="text-right sortable" @click="sortCompare('foreign_ownership')">외국인(%){{ sortArrow(compareSort, 'foreign_ownership') }}</th>
                      <th class="text-right sortable" @click="sortCompare('week52_high')">52주 최고{{ sortArrow(compareSort, 'week52_high') }}</th>
                      <th class="text-right sortable" @click="sortCompare('week52_low')">52주 최저{{ sortArrow(compareSort, 'week52_low') }}</th>
                      <th>총평</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(c, i) in sortedComparison" :key="c.ticker || i">
                      <td class="stock-name">
                        {{ c.name }}<br /><span class="muted" style="font-size: 0.72rem">{{ c.ticker }}</span>
                      </td>
                      <td class="text-right">{{ num(c.price) }}</td>
                      <td class="text-right">{{ num(c.market_cap) }}</td>
                      <td class="text-right">{{ num(c.per) }}</td>
                      <td class="text-right">{{ num(c.pbr) }}</td>
                      <td class="text-right" :class="posNeg(c.roe)">{{ num(c.roe) }}</td>
                      <td class="text-right">{{ num(c.revenue) }}</td>
                      <td class="text-right" :class="posNeg(c.operating_profit)">{{ num(c.operating_profit) }}</td>
                      <td class="text-right" :class="posNeg(c.net_income)">{{ num(c.net_income) }}</td>
                      <td class="text-right" :class="posNeg(c.operating_margin)">{{ num(c.operating_margin) }}</td>
                      <td class="text-right">{{ num(c.debt_ratio) }}</td>
                      <td class="text-right" :class="posNeg(c.revenue_growth)">{{ num(c.revenue_growth) }}</td>
                      <td class="text-right">{{ num(c.dividend_yield) }}</td>
                      <td class="text-right">{{ num(c.foreign_ownership) }}</td>
                      <td class="text-right">{{ num(c.week52_high) }}</td>
                      <td class="text-right">{{ num(c.week52_low) }}</td>
                      <td class="reason">{{ c.comment }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p class="disclaimer">
                ※ 헤더를 클릭하면 정렬됩니다. 값이 '-'인 항목은 AI가 확인하지 못한 데이터입니다.
                투자 판단과 책임은 본인에게 있습니다.
              </p>
            </template>
          </div>
        </template>

        <div v-else style="flex: 1; display: flex; align-items: center; justify-content: center; color: var(--text-muted); border: 1px dashed rgba(255,255,255,0.1); border-radius: 12px">
          <div style="text-align: center">
            <div style="font-size: 3rem; margin-bottom: 1rem">✨</div>
            <h3>프로파일을 선택하거나 새로 만들어주세요</h3>
            <p>프롬프트를 실행하면 AI가 선별한 종목이 테이블로 표시됩니다.</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import {
  fetchAiPicks, createAiPick, updateAiPick, deleteAiPick,
  runAiPick, fetchAiPickResult, fetchAiPickModels,
  runAiPickCompare, fetchAiPickComparison, exportAiPickComparisonToGSheet,
} from '../api';

// 성능 순 모델 목록 (서버에서 갱신됨)
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
const comparison = ref(null);
const comparing = ref(false);
const exportingSheet = ref(false);
const gsheetUrl = ref(null);

// 정렬 상태 { key, dir } — dir: 1 오름차순, -1 내림차순
// 기본 정렬: 상승여력 높은 순 (서버도 동일 순서로 반환)
const DEFAULT_PICK_SORT = { key: 'upside', dir: -1 };
const pickSort = ref({ ...DEFAULT_PICK_SORT });
const compareSort = ref({ key: null, dir: 1 });

// 값에서 숫자만 추출 ("+15%" -> 15, "1,200원" -> 1200). 없으면 null
const toNum = (v) => {
  if (v === null || v === undefined || v === '') return null;
  if (typeof v === 'number') return v;
  const m = String(v).replace(/,/g, '').match(/-?\d+(\.\d+)?/);
  return m ? parseFloat(m[0]) : null;
};

const num = (v) => {
  const n = toNum(v);
  return n === null ? '-' : n.toLocaleString();
};

const posNeg = (v) => {
  const n = toNum(v);
  if (n === null) return '';
  return n > 0 ? 'val-pos' : n < 0 ? 'val-neg' : '';
};

const TEXT_KEYS = ['name', 'ticker', 'market'];

const sortArrow = (state, key) => (state.key !== key ? '' : state.dir === 1 ? ' ▲' : ' ▼');

const toggleSort = (state, key) => {
  if (state.value.key === key) {
    state.value = { key, dir: state.value.dir === 1 ? -1 : 1 };
  } else {
    // 숫자 컬럼은 큰 값이 위로 오도록 내림차순부터 시작
    state.value = { key, dir: TEXT_KEYS.includes(key) ? 1 : -1 };
  }
};

const sortPicks = (key) => toggleSort(pickSort, key);
const sortCompare = (key) => toggleSort(compareSort, key);

// 공통 정렬: 숫자면 숫자로, 아니면 문자열로 비교. 값 없는 행은 항상 뒤로
const applySort = (rows, state) => {
  if (!state.key) return rows;
  const isText = TEXT_KEYS.includes(state.key);
  return [...rows].sort((a, b) => {
    const av = a[state.key], bv = b[state.key];
    const aEmpty = av === null || av === undefined || av === '';
    const bEmpty = bv === null || bv === undefined || bv === '';
    if (aEmpty && bEmpty) return 0;
    if (aEmpty) return 1;
    if (bEmpty) return -1;
    if (isText) return String(av).localeCompare(String(bv)) * state.dir;
    const an = toNum(av), bn = toNum(bv);
    if (an === null && bn === null) return 0;
    if (an === null) return 1;
    if (bn === null) return -1;
    return (an - bn) * state.dir;
  });
};

const sortedStocks = computed(() => applySort(result.value?.stocks || [], pickSort.value));
const sortedComparison = computed(() => applySort(comparison.value?.comparison || [], compareSort.value));

const modelLabel = (id) => models.value.find(m => m.id === id)?.label || id || '';

const loadModels = async () => {
  const res = await fetchAiPickModels();
  if (res && Array.isArray(res.models) && res.models.length > 0) {
    models.value = res.models;
    defaultModel.value = res.default || res.models[0].id;
  }
};

let pollId = null;
let comparePollId = null;

const statusLabel = (s) => ({ running: '실행 중', done: '완료', error: '오류' }[s] || s);

const loadProfiles = async () => {
  const res = await fetchAiPicks();
  if (Array.isArray(res)) profiles.value = res;
};

const loadResult = async (id) => {
  const res = await fetchAiPickResult(id);
  if (!res || res.status === 'NONE') {
    result.value = null;
    running.value = false;
    return;
  }
  result.value = res;
  running.value = res.status === 'running';
  if (!running.value) stopPolling();
};

const startPolling = (id) => {
  stopPolling();
  pollId = setInterval(async () => {
    await loadResult(id);
    if (!running.value) loadProfiles();
  }, 3000);
};

const stopPolling = () => {
  if (pollId) { clearInterval(pollId); pollId = null; }
};

// ── 상세 비교 ──
const loadComparison = async (id) => {
  const res = await fetchAiPickComparison(id);
  if (!res || res.status === 'NONE') {
    comparison.value = null;
    comparing.value = false;
    return;
  }
  comparison.value = res;
  comparing.value = res.status === 'running';
  if (!comparing.value) stopComparePolling();
};

const startComparePolling = (id) => {
  stopComparePolling();
  comparePollId = setInterval(() => loadComparison(id), 3000);
};

const stopComparePolling = () => {
  if (comparePollId) { clearInterval(comparePollId); comparePollId = null; }
};

const handleCompare = async () => {
  if (!selected.value?.id) return;
  const res = await runAiPickCompare(selected.value.id);
  if (res.status === 'ERROR') {
    alert('비교 분석 실패: ' + res.message);
    return;
  }
  comparing.value = true;
  comparison.value = { status: 'running', comparison: [] };
  compareSort.value = { key: null, dir: 1 };
  startComparePolling(selected.value.id);
};

const handleExportComparison = async () => {
  if (!selected.value?.id) return;
  exportingSheet.value = true;
  try {
    const res = await exportAiPickComparisonToGSheet(selected.value.id);
    if (res.status === 'SUCCESS') {
      gsheetUrl.value = res.url || null;
      alert(`구글 시트 업로드 완료\n탭: ${res.sheet} (${res.rows}종목)`);
    } else {
      alert('구글 시트 업로드 실패: ' + res.message);
    }
  } catch (e) {
    alert('업로드 중 오류: ' + e.message);
  } finally {
    exportingSheet.value = false;
  }
};

const handleSelect = async (p) => {
  selected.value = p;
  gsheetUrl.value = null;
  name.value = p.name;
  prompt.value = p.prompt;
  model.value = p.model || defaultModel.value;
  isEditing.value = true;
  pickSort.value = { ...DEFAULT_PICK_SORT };
  compareSort.value = { key: null, dir: 1 };
  await loadResult(p.id);
  if (running.value) startPolling(p.id);
  await loadComparison(p.id);
  if (comparing.value) startComparePolling(p.id);
};

const handleNew = () => {
  selected.value = null;
  name.value = '';
  prompt.value = '';
  model.value = defaultModel.value;
  result.value = null;
  running.value = false;
  comparison.value = null;
  comparing.value = false;
  pickSort.value = { ...DEFAULT_PICK_SORT };
  compareSort.value = { key: null, dir: 1 };
  stopPolling();
  stopComparePolling();
  isEditing.value = true;
};

const cancelEdit = () => {
  isEditing.value = false;
  selected.value = null;
  result.value = null;
  comparison.value = null;
  comparing.value = false;
  stopPolling();
  stopComparePolling();
};

const handleSave = async () => {
  if (!name.value.trim() || !prompt.value.trim()) {
    alert('이름과 프롬프트를 모두 입력하세요.');
    return;
  }
  const res = selected.value?.id
    ? await updateAiPick(selected.value.id, name.value, prompt.value, model.value)
    : await createAiPick(name.value, prompt.value, model.value);
  if (res.status !== 'SUCCESS') {
    alert('저장 실패: ' + res.message);
    return;
  }
  if (!selected.value?.id) selected.value = { id: res.id, name: name.value, prompt: prompt.value, model: model.value };
  await loadProfiles();
  alert('저장되었습니다.');
};

const handleDelete = async (p) => {
  if (!confirm(`'${p.name}' 프로파일을 삭제할까요?`)) return;
  await deleteAiPick(p.id);
  if (selected.value?.id === p.id) cancelEdit();
  loadProfiles();
};

const handleRun = async () => {
  if (!selected.value?.id) {
    alert('먼저 프로파일을 저장한 뒤 실행하세요.');
    return;
  }
  // 편집 중 변경 사항이 있으면 저장 후 실행
  if (name.value !== selected.value.name || prompt.value !== selected.value.prompt
      || model.value !== (selected.value.model || defaultModel.value)) {
    const res = await updateAiPick(selected.value.id, name.value, prompt.value, model.value);
    if (res.status !== 'SUCCESS') {
      alert('저장 실패: ' + res.message);
      return;
    }
    selected.value = { ...selected.value, name: name.value, prompt: prompt.value, model: model.value };
  }
  const res = await runAiPick(selected.value.id);
  if (res.status === 'ERROR') {
    alert('실행 실패: ' + res.message);
    return;
  }
  running.value = true;
  result.value = { status: 'running', stocks: [] };
  pickSort.value = { ...DEFAULT_PICK_SORT };
  // 새로 선별하면 이전 비교 결과는 무효 — 화면에서 내림
  comparison.value = null;
  comparing.value = false;
  stopComparePolling();
  startPolling(selected.value.id);
};

onMounted(() => {
  loadModels();
  loadProfiles();
});
onUnmounted(() => {
  stopPolling();
  stopComparePolling();
});
</script>

<style scoped>
.pick-item-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 12px 14px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.pick-item-card:hover {
  background: rgba(255, 255, 255, 0.07);
}
.pick-item-card.active {
  border-color: var(--primary);
  background: rgba(0, 255, 136, 0.06);
}
.pick-name {
  font-size: 0.92rem;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.danger-btn {
  background: rgba(255, 77, 77, 0.1);
  border: 1px solid rgba(255, 77, 77, 0.35);
  color: var(--danger);
  border-radius: 6px;
  padding: 2px 10px;
  font-size: 0.75rem;
  cursor: pointer;
  flex-shrink: 0;
}
.danger-btn:hover {
  background: rgba(255, 77, 77, 0.25);
}
.pick-model {
  font-size: 0.7rem;
  color: var(--secondary);
}

.refresh-btn {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: var(--text-muted);
  border-radius: 6px;
  padding: 5px 12px;
  cursor: pointer;
  font-size: 0.82rem;
  white-space: nowrap;
}
.refresh-btn:hover { background: rgba(255, 255, 255, 0.1); color: var(--text-main); }

.model-select {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: white;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 0.92rem;
  outline: none;
  cursor: pointer;
  max-width: 320px;
}

.model-select option {
  background: #161B22;
  color: white;
}

.pick-status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.72rem;
}
.st-done { color: var(--success); }
.st-running { color: var(--warning); }
.st-error { color: var(--danger); }
.pick-time { color: var(--text-muted); }

.run-btn {
  background: rgba(0, 212, 255, 0.12);
  border: 1px solid var(--secondary);
  color: var(--secondary);
  border-radius: 8px;
  padding: 10px 25px;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
}
.run-btn:hover:not(:disabled) {
  background: rgba(0, 212, 255, 0.25);
}
.run-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.mini-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-top-color: currentColor;
  border-radius: 50%;
  display: inline-block;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.result-box {
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 1.2rem;
  background: rgba(0, 0, 0, 0.2);
}
.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.result-empty {
  color: var(--text-muted);
  padding: 20px 0;
  display: flex;
  align-items: center;
  gap: 10px;
}
.result-error {
  color: var(--danger);
  font-size: 0.9rem;
}
.raw-text {
  margin-top: 10px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 10px;
  font-size: 0.78rem;
  color: var(--text-muted);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 260px;
  overflow-y: auto;
}
.picks-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}
.picks-table th {
  text-align: left;
  color: var(--text-muted);
  font-size: 0.78rem;
  padding: 8px 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  white-space: nowrap;
}
.picks-table td {
  padding: 9px 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  vertical-align: top;
}
.text-right { text-align: right; }
.muted { color: var(--text-muted); }

/* 정렬 가능한 헤더 */
.picks-table th.sortable {
  cursor: pointer;
  user-select: none;
  transition: color 0.15s;
}
.picks-table th.sortable:hover { color: var(--primary); }

/* 상세 비교 */
.compare-btn {
  background: rgba(0, 212, 255, 0.12);
  border: 1px solid var(--secondary);
  color: var(--secondary);
  border-radius: 6px;
  padding: 5px 12px;
  cursor: pointer;
  font-size: 0.82rem;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.compare-btn:hover:not(:disabled) { background: rgba(0, 212, 255, 0.25); }
.compare-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.gsheet-btn {
  background: rgba(15, 157, 88, 0.15);
  border: 1px solid rgba(15, 157, 88, 0.5);
  color: #34A853;
  border-radius: 6px;
  padding: 5px 12px;
  cursor: pointer;
  font-size: 0.82rem;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.gsheet-btn:hover:not(:disabled) { background: rgba(15, 157, 88, 0.3); }
.gsheet-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.gsheet-link {
  font-size: 0.75rem;
  color: #34A853;
  text-decoration: none;
}
.gsheet-link:hover { text-decoration: underline; }

.table-scroll {
  overflow-x: auto;
  max-width: 100%;
}
.compare-table {
  min-width: 1400px;
  font-size: 0.82rem;
}
.compare-table th { white-space: nowrap; }
.compare-table td { white-space: nowrap; }
.compare-table td.reason {
  white-space: normal;
  min-width: 220px;
}
.val-pos { color: var(--success); }
.val-neg { color: var(--danger); }
.stock-name { font-weight: 600; white-space: nowrap; }
.upside { color: var(--success); font-weight: 700; white-space: nowrap; }
.reason { color: var(--text-muted); font-size: 0.82rem; line-height: 1.5; }
.market-badge {
  font-size: 0.72rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 6px;
  white-space: nowrap;
}
.market-badge.kospi {
  background: rgba(0, 212, 255, 0.12);
  color: var(--secondary);
}
.market-badge.kosdaq {
  background: rgba(255, 204, 0, 0.12);
  color: var(--warning);
}
.disclaimer {
  margin: 10px 0 0;
  font-size: 0.75rem;
  color: var(--text-muted);
}
</style>
