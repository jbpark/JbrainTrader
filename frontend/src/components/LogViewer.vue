<template>
  <div class="log-viewer-container glass">
    <div class="log-header">
      <h3 style="margin: 0; font-size: 1rem; display: flex; align-items: center; gap: 8px">
        <span style="color: var(--primary)">●</span> 실시간 시스템 로그
      </h3>
      <div class="log-actions">
        <span class="log-count">Total: {{ logs.length }}</span>
      </div>
    </div>
    <div class="log-body" ref="logBody">
      <div v-for="(log, i) in logs" :key="i" class="log-line">
        <span class="log-index">[{{ i + 1 }}]</span>
        <span class="log-content">{{ log }}</span>
      </div>
      <div v-if="logs.length === 0" class="empty-log">대기 중... 로그 데이터가 없습니다.</div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue';

const props = defineProps({
  logs: {
    type: Array,
    default: () => []
  }
});

const logBody = ref(null);

watch(() => props.logs, () => {
  nextTick(() => {
    if (logBody.value) {
      logBody.value.scrollTop = logBody.value.scrollHeight;
    }
  });
}, { deep: true, immediate: true });
</script>

<style scoped>
.log-viewer-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin-top: 1rem;
  overflow: hidden;
  background: rgba(13, 17, 23, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.log-header {
  padding: 12px 20px;
  background: rgba(255, 255, 255, 0.02);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.log-count {
  font-size: 0.75rem;
  color: var(--text-muted);
  font-family: monospace;
}

.log-body {
  flex: 1;
  overflow-y: scroll; /* Force vertical scrollbar visibility */
  overflow-x: auto;
  padding: 15px 20px;
  font-family: 'Fira Code', 'Courier New', monospace;
  font-size: 0.85rem;
  line-height: 1.6;
  min-height: 0;
}

.log-line {
  display: flex;
  gap: 12px;
  padding: 2px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.01);
  width: max-content;
  min-width: 100%;
}

.log-line:hover {
  background: rgba(255, 255, 255, 0.02);
}

.log-index {
  color: var(--secondary);
  opacity: 0.6;
  min-width: 40px;
  user-select: none;
}

.log-content {
  color: var(--text-main);
  white-space: nowrap;
}

.empty-log {
  color: var(--text-muted);
  text-align: center;
  padding-top: 2rem;
  font-style: italic;
}

/* Custom Scrollbar - Enhanced Visibility */
.log-body::-webkit-scrollbar {
  width: 12px; /* Increased width */
  height: 10px;
}
.log-body::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.05); /* Slightly brighter track */
  border-left: 1px solid rgba(255, 255, 255, 0.05);
}
.log-body::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.5); /* Much brighter, more opaque thumb */
  border-radius: 6px;
  border: 3px solid transparent; 
  background-clip: content-box;
}
.log-body::-webkit-scrollbar-thumb:hover {
  background: var(--primary); /* Highlight with primary color on hover */
  border: 2px solid transparent;
  background-clip: content-box;
}
.log-body::-webkit-scrollbar-corner {
  background: transparent;
}
</style>
