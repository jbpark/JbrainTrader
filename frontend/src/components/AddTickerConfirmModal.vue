<template>
  <div class="glass confirm-popup" :style="{
    position: 'absolute',
    top: 'calc(100% + 10px)',
    right: '0',
    width: '300px',
    background: '#1a1d23',
    zIndex: 10000,
    display: 'flex',
    flexDirection: 'column',
    padding: '1.2rem',
    boxShadow: '0 15px 35px rgba(0,0,0,0.8), 0 0 15px rgba(0, 255, 136, 0.1)',
    border: '1px solid var(--primary)',
    borderRadius: '12px',
    textAlign: 'center',
    animation: 'popupFadeIn 0.2s ease-out'
  }">
    <h3 style="margin-bottom: 1rem; color: var(--primary); display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 1.05rem">
      <span>➕</span> 종목 추가 확인
    </h3>

    <div style="background: rgba(255,255,255,0.03); padding: 0.8rem; border-radius: 8px; margin-bottom: 1rem; text-align: left; border: 1px solid var(--border-color); font-size: 0.8rem">
      <div style="margin-bottom: 0.4rem; display: flex; justify-content: space-between">
        <span style="color: var(--text-muted)">종목</span>
        <span style="font-weight: bold; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 150px">{{ name }}</span>
      </div>
      <div style="margin-bottom: 0.4rem; display: flex; justify-content: space-between">
        <span style="color: var(--text-muted)">코드</span>
        <span style="font-family: monospace; color: var(--primary)">{{ formatTicker(ticker) }}</span>
      </div>
      <div style="display: flex; justify-content: space-between">
        <span style="color: var(--text-muted)">전략</span>
        <span style="font-weight: bold; color: var(--secondary)">{{ strategy === 'NONE' ? '없음 (모니터링만)' : strategy }}</span>
      </div>
    </div>

    <p style="margin-bottom: 1.2rem; line-height: 1.4; font-size: 0.8rem; color: var(--text-main)">
      위 종목을 추가하시겠습니까?
    </p>

    <div style="display: flex; gap: 0.6rem">
      <button
        class="primary"
        style="flex: 1.2; padding: 0.6rem; font-size: 0.85rem; font-weight: bold"
        @click="emit('confirm')"
      >
        추가
      </button>
      <button
        style="flex: 1; padding: 0.6rem; font-size: 0.85rem; background: transparent; border: 1px solid var(--border-color); color: var(--text-muted); border-radius: 6px; cursor: pointer"
        @click="emit('cancel')"
      >
        취소
      </button>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  ticker: String,
  name: String,
  strategy: String
});

const emit = defineEmits(['confirm', 'cancel']);

const formatTicker = (ticker) => {
  if (!ticker) return '';
  return ticker.split('.')[0];
};
</script>

<style scoped>
@keyframes popupFadeIn {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
