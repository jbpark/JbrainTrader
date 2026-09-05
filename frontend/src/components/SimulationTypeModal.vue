<template>
  <Teleport to="body">
    <div class="glass confirm-popup" :style="{
      position: 'fixed',
      top: `${top}px`,
      left: `${left}px`,
      transform: 'translate(-100%, -50%)',
      width: '280px',
      background: '#1a1d23',
      zIndex: 10002,
      display: 'flex',
      flexDirection: 'column',
      padding: '1.2rem',
      boxShadow: '0 15px 35px rgba(0,0,0,0.8), 0 0 15px rgba(0, 212, 255, 0.1)',
      border: '1px solid var(--primary)',
      borderRadius: '12px',
      textAlign: 'center',
      animation: 'popupFadeIn 0.2s ease-out'
    }">
      <h3 style="margin-bottom: 1rem; color: var(--primary); display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 1rem">
        <span>▶️</span> 시뮬레이션 방식 선택
      </h3>

      <div style="background: rgba(255,255,255,0.03); padding: 0.8rem; border-radius: 8px; margin-bottom: 1.2rem; text-align: left; border: 1px solid var(--border-color); font-size: 0.85rem">
        <div style="display: flex; justify-content: space-between">
          <span style="color: var(--text-muted)">대상 종목:</span>
          <span style="font-weight: bold; color: #fff">{{ name }}</span>
        </div>
      </div>

      <div style="display: flex; flex-direction: column; gap: 0.8rem">
        <button
          class="primary"
          style="padding: 0.8rem; font-size: 0.9rem; font-weight: bold; display: flex; align-items: center; justify-content: center; gap: 10px"
          @click="emit('select', '기존 데이터 기반')"
        >
          <span style="font-size: 1.1rem">📈</span> 기존 데이터 기반
        </button>
        <button
          class="primary"
          style="padding: 0.8rem; font-size: 0.9rem; font-weight: bold; background: var(--secondary) !important; border-color: var(--secondary) !important; display: flex; align-items: center; justify-content: center; gap: 10px"
          @click="emit('select', '랜덤 데이터')"
        >
          <span style="font-size: 1.1rem">🎲</span> 랜덤 데이터
        </button>
        <button
          style="padding: 0.6rem; font-size: 0.85rem; background: transparent; border: 1px solid var(--border-color); color: var(--text-muted); border-radius: 6px; cursor: pointer; margin-top: 4px"
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

const emit = defineEmits(['select', 'cancel']);
</script>

<style scoped>
@keyframes popupFadeIn {
  from { opacity: 0; transform: translate(calc(-100% + 10px), -50%); }
  to { opacity: 1; transform: translate(-100%, -50%); }
}

button.primary:hover {
  transform: translateY(-2px);
  filter: brightness(1.1);
}
</style>
