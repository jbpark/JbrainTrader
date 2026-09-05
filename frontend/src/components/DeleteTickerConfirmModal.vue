<template>
  <Teleport to="body">
    <div class="glass confirm-popup" :style="{
      position: 'fixed',
      top: `${top}px`,
      left: `${left}px`,
      transform: 'translate(-100%, -50%)',
      width: '260px',
      background: '#1a1d23',
      zIndex: 10002,
      display: 'flex',
      flexDirection: 'column',
      padding: '1.2rem',
      boxShadow: '0 15px 35px rgba(0,0,0,0.8), 0 0 15px rgba(255, 78, 103, 0.1)',
      border: '1px solid #ff4e67',
      borderRadius: '12px',
      textAlign: 'center',
      animation: 'popupFadeIn 0.2s ease-out'
    }">
      <h3 style="margin-bottom: 1rem; color: #ff4e67; display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 1rem">
        <span>🗑️</span> 종목 삭제 확인
      </h3>

      <div style="background: rgba(255,255,255,0.03); padding: 0.8rem; border-radius: 8px; margin-bottom: 1rem; text-align: left; border: 1px solid var(--border-color); font-size: 0.85rem">
        <div style="display: flex; justify-content: space-between; margin-bottom: 4px">
          <span style="color: var(--text-muted)">종목명:</span>
          <span style="font-weight: bold; color: var(--primary)">{{ name }}</span>
        </div>
        <div style="display: flex; justify-content: space-between">
          <span style="color: var(--text-muted)">코드:</span>
          <span style="font-family: monospace; color: #fff">{{ ticker.split('.')[0] }}</span>
        </div>
      </div>

      <p style="margin-bottom: 1.2rem; line-height: 1.4; font-size: 0.85rem; color: var(--text-main)">
        이 종목의 모니터링을<br />삭제하시겠습니까?
      </p>

      <div style="display: flex; gap: 0.6rem">
        <button
          class="primary"
          style="flex: 1.2; padding: 0.6rem; font-size: 0.85rem; font-weight: bold; background: #ff4e67 !important; border-color: #ff4e67 !important"
          @click="emit('confirm')"
        >
          삭제
        </button>
        <button
          style="flex: 1; padding: 0.6rem; font-size: 0.85rem; background: transparent; border: 1px solid var(--border-color); color: var(--text-muted); border-radius: 6px; cursor: pointer"
          @click="emit('cancel')"
        >
          취소
        </button>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
const props = defineProps({
  ticker: String,
  name: String,
  top: Number,
  left: Number
});

const emit = defineEmits(['confirm', 'cancel']);
</script>

<style scoped>
@keyframes popupFadeIn {
  from { opacity: 0; transform: translate(calc(-100% + 10px), -50%); }
  to { opacity: 1; transform: translate(-100%, -50%); }
}
</style>
