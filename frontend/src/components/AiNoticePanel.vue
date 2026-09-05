<template>
  <div class="main-tab-content glass" style="flex: 1; overflow: hidden; display: flex; flex-direction: column; gap: 1.2rem; padding: 2.5rem">
    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid var(--primary); padding-bottom: 1rem">
      <h2 style="color: var(--primary); margin: 0; display: flex; align-items: center; gap: 12px">
        <span style="font-size: 1.8rem">🔔</span> AI Notice
      </h2>
      <div style="display: flex; align-items: center; gap: 14px">
        <button class="refresh-btn" @click="load" title="알림을 다시 불러옵니다">🔄 새로고침</button>
        <div style="text-align: right">
          <div style="font-size: 0.9rem; color: var(--text-main); font-weight: 600">메신저 발송 알림</div>
          <div style="font-size: 0.8rem; color: var(--primary)">{{ notices.length }}건</div>
        </div>
      </div>
    </div>

    <!-- 카테고리 필터 -->
    <div style="display: flex; gap: 8px; flex-wrap: wrap">
      <button
        v-for="c in categories"
        :key="c.value"
        class="filter-btn"
        :class="{ active: filter === c.value }"
        @click="filter = c.value"
      >
        {{ c.label }}
        <span v-if="countOf(c.value)" class="filter-count">{{ countOf(c.value) }}</span>
      </button>
    </div>

    <!-- 알림 목록 -->
    <div style="flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; min-height: 0">
      <div v-if="filtered.length === 0" style="color: var(--text-muted); text-align: center; padding: 3rem 0">
        표시할 알림이 없습니다. 전략 이탈 감시·아침 브리핑·매매일지 복기가 발송되면 여기에 쌓입니다.
      </div>

      <div v-for="n in filtered" :key="n.id" class="notice-card" :class="'lv-' + n.level">
        <div class="notice-head" @click="toggle(n.id)">
          <span class="notice-badge" :class="'cat-' + n.category">{{ n.category }}</span>
          <span class="notice-title">{{ n.title }}</span>
          <span class="notice-time">{{ n.created_at }}</span>
          <span class="notice-arrow">{{ expanded.has(n.id) ? '▲' : '▼' }}</span>
        </div>
        <div v-if="!expanded.has(n.id)" class="notice-preview">{{ preview(n.message) }}</div>
        <pre v-else class="notice-body">{{ clean(n.message) }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { fetchAiNotices } from '../api';

const notices = ref([]);
const filter = ref('');
const expanded = ref(new Set());
let intervalId = null;

const categories = [
  { value: '', label: '전체' },
  { value: '전략감시', label: '⚡ 전략감시' },
  { value: '브리핑', label: '☀️ 브리핑' },
  { value: '복기', label: '📋 복기' },
];

const filtered = computed(() =>
  filter.value ? notices.value.filter((n) => n.category === filter.value) : notices.value
);

const countOf = (cat) =>
  cat ? notices.value.filter((n) => n.category === cat).length : notices.value.length;

// 디스코드용 마크다운 볼드 제거
const clean = (msg) => String(msg || '').replace(/\*\*/g, '');
const preview = (msg) => {
  const t = clean(msg).split('\n').filter((l) => l.trim());
  return t.slice(0, 2).join(' · ').slice(0, 160);
};

const toggle = (id) => {
  const s = new Set(expanded.value);
  s.has(id) ? s.delete(id) : s.add(id);
  expanded.value = s;
};

const load = async () => {
  notices.value = await fetchAiNotices();
};

onMounted(() => {
  load();
  intervalId = setInterval(load, 30000);
});
onUnmounted(() => {
  if (intervalId) clearInterval(intervalId);
});
</script>

<style scoped>
.filter-btn {
  padding: 6px 14px;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-muted);
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.15s;
}
.filter-btn.active {
  border-color: var(--primary);
  color: var(--primary);
  background: rgba(0, 208, 132, 0.08);
  font-weight: 600;
}
.filter-count {
  margin-left: 6px;
  font-size: 0.75rem;
  opacity: 0.8;
}

.notice-card {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-left: 4px solid var(--text-muted);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.02);
  padding: 12px 16px;
}
.notice-card.lv-critical { border-left-color: #ff5252; }
.notice-card.lv-warning { border-left-color: #ffb300; }
.notice-card.lv-good { border-left-color: var(--primary); }
.notice-card.lv-info { border-left-color: #4fc3f7; }

.notice-head {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}
.notice-badge {
  font-size: 0.72rem;
  padding: 2px 8px;
  border-radius: 10px;
  white-space: nowrap;
  font-weight: 600;
}
.notice-badge.cat-전략감시 { background: rgba(255, 179, 0, 0.15); color: #ffb300; }
.notice-badge.cat-브리핑 { background: rgba(79, 195, 247, 0.15); color: #4fc3f7; }
.notice-badge.cat-복기 { background: rgba(0, 208, 132, 0.15); color: var(--primary); }

.notice-title {
  flex: 1;
  font-weight: 600;
  color: var(--text-main);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.notice-time {
  font-size: 0.78rem;
  color: var(--text-muted);
  white-space: nowrap;
}
.notice-arrow {
  font-size: 0.7rem;
  color: var(--text-muted);
}
.notice-preview {
  margin-top: 6px;
  font-size: 0.85rem;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.notice-body {
  margin-top: 10px;
  font-size: 0.88rem;
  line-height: 1.55;
  color: var(--text-main);
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  padding: 12px 14px;
  max-height: 480px;
  overflow-y: auto;
}
</style>
