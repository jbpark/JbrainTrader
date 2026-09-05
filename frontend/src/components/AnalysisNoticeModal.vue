<template>
  <Teleport to="body">
    <div class="glass notice-popup" :style="{
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
      boxShadow: '0 15px 35px rgba(0,0,0,0.8), 0 0 15px rgba(0, 255, 136, 0.1)',
      border: '1px solid var(--primary)',
      borderRadius: '12px',
      textAlign: 'center',
      animation: 'popupFadeIn 0.2s ease-out'
    }">
      <h3 style="margin-bottom: 1rem; color: var(--primary); display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 1rem">
        <span>⚠️</span> 분석 불가
      </h3>

      <div style="background: rgba(255,255,255,0.03); padding: 0.8rem; border-radius: 8px; margin-bottom: 1rem; text-align: left; border: 1px solid var(--border-color); font-size: 0.85rem">
        <div style="display: flex; justify-content: space-between">
          <span style="color: var(--text-muted)">대상 종목:</span>
          <span style="font-weight: bold; color: #fff">{{ name }}</span>
        </div>
      </div>

      <p style="margin-bottom: 1.2rem; line-height: 1.4; font-size: 0.85rem; color: var(--text-main)">
        매매가 시작되지 않았습니다.<br />
        먼저 매매를 시작해주세요.
      </p>

      <div style="display: flex; justify-content: center">
        <button
          class="primary"
          style="width: 100%; padding: 0.6rem; font-size: 0.85rem; font-weight: bold;"
          @click="emit('close')"
        >
          확인
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

const emit = defineEmits(['close']);
</script>

<style scoped>
@keyframes popupFadeIn {
  from { opacity: 0; transform: translate(calc(-100% + 10px), -50%); }
  to { opacity: 1; transform: translate(-100%, -50%); }
}
</style>
