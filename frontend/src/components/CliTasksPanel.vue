<template>
  <div class="cli-panel">
    <div class="cli-toolbar">
      <div class="cli-filters">
        <button
          v-for="f in filters"
          :key="f.value"
          class="filter-btn"
          :class="{ active: activeFilter === f.value }"
          @click="setFilter(f.value)"
        >
          {{ f.label }}
        </button>
      </div>
      <div class="cli-actions">
        <label class="select-all-label">
          <input type="checkbox" :checked="allSelected" @change="toggleSelectAll" :disabled="tasks.length === 0" />
          전체 선택
        </label>
        <button class="bulk-delete-btn" :disabled="selectedIds.length === 0" @click="removeSelected">
          🗑 선택 삭제<span v-if="selectedIds.length"> ({{ selectedIds.length }})</span>
        </button>
        <button class="refresh-btn" @click="loadTasks" :disabled="loading">
          {{ loading ? '갱신 중...' : '🔄 새로고침' }}
        </button>
      </div>
    </div>

    <p class="cli-hint">
      Claude CLI / Antigravity CLI에서 이 프로젝트에 입력한 프롬프트와 응답이 자동 기록됩니다.
      연동 설정은 <code>doc/cli_integration.md</code>를 참고하세요.
    </p>

    <div v-if="tasks.length === 0" class="cli-empty">
      아직 기록된 CLI 작업이 없습니다.
    </div>

    <div v-for="task in tasks" :key="task.id" class="task-card">
      <div class="task-row" @click="toggleDetail(task.id)">
        <input
          type="checkbox"
          class="task-check"
          :checked="selectedIds.includes(task.id)"
          @click.stop="toggleSelect(task.id)"
        />
        <span class="trigger-badge" :class="task.trigger_type">
          {{ task.trigger_type === 'antigravity_cli' ? '🚀 Antigravity' : '🤖 Claude' }}
        </span>
        <span class="task-title">{{ task.title }}</span>
        <span class="status-badge" :class="task.status">{{ statusLabel(task.status) }}</span>
        <span class="task-time">{{ task.created_at }}</span>
        <button class="delete-btn" @click.stop="removeTask(task.id)" title="삭제">×</button>
      </div>

      <div v-if="expandedId === task.id" class="task-detail">
        <template v-if="detail && detail.id === task.id">
          <div class="detail-meta">
            <span v-if="detail.model">모델: {{ detail.model }}</span>
            <span v-if="detail.duration_ms">소요: {{ (detail.duration_ms / 1000).toFixed(1) }}초</span>
            <span v-if="detail.cli_session_id">세션: {{ detail.cli_session_id.slice(0, 8) }}</span>
          </div>
          <div class="detail-section">
            <div class="detail-label">프롬프트</div>
            <pre class="detail-text">{{ detail.prompt }}</pre>
          </div>
          <div class="detail-section" v-if="detail.answer">
            <div class="detail-label">응답</div>
            <pre class="detail-text">{{ detail.answer }}</pre>
          </div>
          <div class="detail-section" v-if="detail.output && detail.output !== detail.answer">
            <div class="detail-label">실행 요약</div>
            <pre class="detail-text muted">{{ detail.output }}</pre>
          </div>
        </template>
        <div v-else class="detail-loading">불러오는 중...</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { fetchCliTasks, fetchCliTaskDetail, deleteCliTask, deleteCliTasksBulk } from '../api';

const tasks = ref([]);
const detail = ref(null);
const expandedId = ref(null);
const activeFilter = ref(null);
const loading = ref(false);
const selectedIds = ref([]);

const allSelected = computed(() =>
  tasks.value.length > 0 && selectedIds.value.length === tasks.value.length
);

const filters = [
  { label: '전체', value: null },
  { label: '🤖 Claude', value: 'claude_cli' },
  { label: '🚀 Antigravity', value: 'antigravity_cli' },
];

const statusLabel = (s) => ({ running: '진행 중', done: '완료', error: '오류' }[s] || s);

const loadTasks = async () => {
  loading.value = true;
  try {
    const res = await fetchCliTasks(100, activeFilter.value);
    if (Array.isArray(res)) {
      tasks.value = res;
      // 목록에서 사라진 작업은 선택 해제
      selectedIds.value = selectedIds.value.filter(id => res.some(t => t.id === id));
    }
  } finally {
    loading.value = false;
  }
};

const toggleSelect = (id) => {
  selectedIds.value = selectedIds.value.includes(id)
    ? selectedIds.value.filter(x => x !== id)
    : [...selectedIds.value, id];
};

const toggleSelectAll = () => {
  selectedIds.value = allSelected.value ? [] : tasks.value.map(t => t.id);
};

const removeSelected = async () => {
  if (selectedIds.value.length === 0) return;
  if (!confirm(`선택한 ${selectedIds.value.length}개 작업을 삭제할까요?`)) return;
  await deleteCliTasksBulk(selectedIds.value);
  selectedIds.value = [];
  expandedId.value = null;
  loadTasks();
};

const setFilter = (value) => {
  activeFilter.value = value;
  loadTasks();
};

const toggleDetail = async (taskId) => {
  if (expandedId.value === taskId) {
    expandedId.value = null;
    return;
  }
  expandedId.value = taskId;
  detail.value = null;
  const res = await fetchCliTaskDetail(taskId);
  if (res && res.id === expandedId.value) detail.value = res;
};

const removeTask = async (taskId) => {
  await deleteCliTask(taskId);
  if (expandedId.value === taskId) expandedId.value = null;
  loadTasks();
};

let intervalId = null;
onMounted(() => {
  loadTasks();
  intervalId = setInterval(loadTasks, 10000);
});
onUnmounted(() => {
  if (intervalId) clearInterval(intervalId);
});
</script>

<style scoped>
.cli-panel {
  flex: 1;
  overflow-y: auto;
  padding-right: 6px;
}
.cli-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.cli-filters {
  display: flex;
  gap: 6px;
}
.filter-btn {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  color: var(--text-muted);
  border-radius: 6px;
  padding: 4px 12px;
  cursor: pointer;
  font-size: 0.85rem;
}
.filter-btn.active {
  color: var(--primary);
  border-color: var(--primary);
}
.refresh-btn {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  color: var(--text-main);
  border-radius: 6px;
  padding: 4px 12px;
  cursor: pointer;
  font-size: 0.85rem;
}
.cli-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.select-all-label {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--text-muted);
  font-size: 0.85rem;
  cursor: pointer;
  white-space: nowrap;
}
.bulk-delete-btn {
  background: rgba(255, 77, 77, 0.1);
  border: 1px solid rgba(255, 77, 77, 0.4);
  color: var(--danger);
  border-radius: 6px;
  padding: 4px 12px;
  cursor: pointer;
  font-size: 0.85rem;
  white-space: nowrap;
}
.bulk-delete-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.task-check {
  cursor: pointer;
  accent-color: var(--primary);
}
.cli-hint {
  color: var(--text-muted);
  font-size: 0.82rem;
  margin: 0 0 14px;
}
.cli-hint code {
  color: var(--secondary);
}
.cli-empty {
  color: var(--text-muted);
  text-align: center;
  padding: 40px 0;
  border: 1px dashed var(--border-color);
  border-radius: 8px;
}
.task-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  margin-bottom: 8px;
}
.task-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  cursor: pointer;
}
.task-row:hover {
  background: rgba(255, 255, 255, 0.04);
}
.trigger-badge {
  font-size: 0.75rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 6px;
  white-space: nowrap;
}
.trigger-badge.claude_cli {
  background: rgba(0, 212, 255, 0.12);
  color: var(--secondary);
}
.trigger-badge.antigravity_cli {
  background: rgba(112, 0, 255, 0.18);
  color: #b98aff;
}
.task-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.9rem;
}
.status-badge {
  font-size: 0.72rem;
  padding: 2px 8px;
  border-radius: 6px;
  white-space: nowrap;
}
.status-badge.running {
  background: rgba(255, 204, 0, 0.12);
  color: var(--warning);
}
.status-badge.done {
  background: rgba(0, 255, 136, 0.1);
  color: var(--success);
}
.status-badge.error {
  background: rgba(255, 77, 77, 0.12);
  color: var(--danger);
}
.task-time {
  color: var(--text-muted);
  font-size: 0.75rem;
  white-space: nowrap;
}
.delete-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 1rem;
  cursor: pointer;
  padding: 0 4px;
}
.delete-btn:hover {
  color: var(--danger);
}
.task-detail {
  border-top: 1px solid var(--border-color);
  padding: 12px 14px;
}
.detail-meta {
  display: flex;
  gap: 16px;
  color: var(--text-muted);
  font-size: 0.78rem;
  margin-bottom: 10px;
}
.detail-section {
  margin-bottom: 10px;
}
.detail-label {
  color: var(--secondary);
  font-size: 0.78rem;
  font-weight: 700;
  margin-bottom: 4px;
}
.detail-text {
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 10px 12px;
  font-size: 0.82rem;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 320px;
  overflow-y: auto;
  margin: 0;
}
.detail-text.muted {
  color: var(--text-muted);
}
.detail-loading {
  color: var(--text-muted);
  font-size: 0.85rem;
}
</style>
