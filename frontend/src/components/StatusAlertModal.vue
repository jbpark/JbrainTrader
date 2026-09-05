<template>
  <Teleport to="body">
    <div v-if="show" class="modal-overlay" @click="emit('close')">
      <div class="glass success-modal" @click.stop :style="modalStyle">
        <h3 class="modal-title">
          <span v-if="type === 'success'">✅</span>
          <span v-else>❌</span>
          {{ title }}
        </h3>

        <div class="modal-content">
          <p>{{ message }}</p>
          <div v-if="details" class="details-box">
            {{ details }}
          </div>
        </div>

        <div class="modal-footer">
          <button class="confirm-btn" @click="emit('close')">확인</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  show: Boolean,
  type: {
    type: String,
    default: 'success'
  },
  title: String,
  message: String,
  details: String
});

const emit = defineEmits(['close']);

const modalStyle = computed(() => ({
  position: 'fixed',
  top: '50%',
  left: '50%',
  transform: 'translate(-50%, -50%)',
  width: '260px',
  background: '#1a1d23',
  zIndex: 10005,
  display: 'flex',
  flexDirection: 'column',
  padding: '1.2rem',
  boxShadow: props.type === 'success' 
    ? '0 15px 35px rgba(0,0,0,0.8), 0 0 15px rgba(0, 255, 149, 0.1)'
    : '0 15px 35px rgba(0,0,0,0.8), 0 0 15px rgba(255, 78, 103, 0.1)',
  border: props.type === 'success' 
    ? '1px solid var(--primary)'
    : '1px solid #ff4e67',
  borderRadius: '12px',
  textAlign: 'center',
  animation: 'modalFadeIn 0.2s ease-out'
}));
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0,0,0,0.4);
  backdrop-filter: blur(2px);
  z-index: 10004;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-title {
  margin-bottom: 1rem;
  color: var(--primary);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 1rem;
}

.modal-content {
  background: rgba(255,255,255,0.03);
  padding: 0.8rem;
  border-radius: 8px;
  margin-bottom: 1.2rem;
  text-align: center;
  border: 1px solid rgba(255, 255, 255, 0.05);
  font-size: 0.85rem;
  line-height: 1.5;
  color: var(--text-main);
}

.details-box {
  margin-top: 8px;
  padding: 6px;
  background: rgba(0,0,0,0.2);
  border-radius: 4px;
  font-size: 0.8rem;
  color: var(--primary);
  font-weight: bold;
}

.modal-footer {
  display: flex;
}

.confirm-btn {
  flex: 1;
  padding: 0.7rem;
  font-size: 0.9rem;
  font-weight: bold;
  background: var(--primary) !important;
  color: #000 !important;
  border: none !important;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.confirm-btn:hover {
  filter: brightness(1.1);
  transform: translateY(-2px);
}

@keyframes modalFadeIn {
  from { opacity: 0; transform: translate(-50%, calc(-50% + 10px)); }
  to { opacity: 1; transform: translate(-50%, -50%); }
}
</style>
