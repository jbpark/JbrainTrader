<template>
  <Teleport to="body">
    <div class="glass confirm-popup" :style="{
      position: 'fixed',
      top: '50%',
      left: '50%',
      transform: 'translate(-50%, -50%)',
      width: '320px',
      background: '#1a1d23',
      zIndex: 10005,
      display: 'flex',
      flexDirection: 'column',
      padding: '1.5rem',
      boxShadow: '0 20px 45px rgba(0,0,0,0.9), 0 0 15px rgba(255, 171, 0, 0.1)',
      border: '1px solid #ffab00',
      borderRadius: '16px',
      textAlign: 'center',
      animation: 'alertFadeIn 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)'
    }">
      <h3 style="margin-bottom: 1.2rem; color: #ffab00; display: flex; align-items: center; justify-content: center; gap: 10px; font-size: 1.1rem">
        <span>⚠️</span> 시스템 알림
      </h3>

      <div style="background: rgba(255,255,255,0.03); padding: 1.2rem; border-radius: 12px; margin-bottom: 1.5rem; text-align: center; border: 1px solid rgba(255, 255, 255, 0.05); font-size: 0.95rem; white-space: pre-line; line-height: 1.6; color: var(--text-main)">
        {{ message }}
      </div>

      <div style="display: flex; gap: 0.6rem">
        <button
          class="primary"
          style="flex: 1; padding: 0.8rem; font-size: 0.95rem; font-weight: bold; background: #ffab00 !important; color: #000 !important; border: none !important"
          @click="emit('close')"
        >
          확인
        </button>
      </div>
    </div>

    <!-- Backdrop -->
    <div 
      style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.6); backdrop-filter: blur(4px); z-index: 10004"
      @click="emit('close')"
    ></div>
  </Teleport>
</template>

<script setup>
const props = defineProps({
  message: {
    type: String,
    required: true
  }
});

const emit = defineEmits(['close']);
</script>

<style scoped>
@keyframes alertFadeIn {
  from { opacity: 0; transform: translate(-50%, -40%) scale(0.9); }
  to { opacity: 1; transform: translate(-50%, -50%) scale(1); }
}

button.primary:hover {
  background: #ffc107 !important;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(255, 171, 0, 0.3);
}

button.primary:active {
  transform: translateY(0);
}
</style>
