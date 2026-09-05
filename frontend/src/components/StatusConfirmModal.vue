<template>
  <Teleport to="body">
    <!-- Backdrop -->
    <div
      style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background-color: rgba(0,0,0,0.7); backdrop-filter: blur(4px); z-index: 20000"
      @click="emit('cancel')"
    ></div>

    <!-- Modal -->
    <div class="glass" :style="{
      position: 'fixed',
      top: '50%',
      left: '50%',
      transform: 'translate(-50%, -50%)',
      width: '400px',
      background: '#1a1d23',
      zIndex: 20001,
      display: 'flex',
      flexDirection: 'column',
      padding: '2rem',
      boxShadow: '0 20px 50px rgba(0,0,0,0.8)',
      border: `1px solid ${actionColor}`,
      borderRadius: '16px',
      textAlign: 'center'
    }">
      <h2 :style="{ marginBottom: '1.5rem', color: actionColor }">
        ⚠️ 매매 {{ action }} 확인
      </h2>

      <div style="background: rgba(255,255,255,0.03); padding: 1.5rem; border-radius: 12px; margin-bottom: 1.5rem; text-align: left; border: 1px solid var(--border-color)">
        <div style="margin-bottom: 0.8rem; display: flex; justify-content: space-between">
          <span style="color: var(--text-muted)">종목코드</span>
          <span style="font-weight: bold">{{ ticker.split('.')[0] }}</span>
        </div>
        <div style="display: flex; justify-content: space-between">
          <span style="color: var(--text-muted)">종목명</span>
          <span style="font-weight: bold">{{ name }}</span>
        </div>
      </div>

      <p style="margin-bottom: 2rem; line-height: 1.6; font-size: 1.1rem">
        위 종목의 실시간 매매를<br />
        <strong :style="{ color: actionColor }">{{ action }}</strong>하시겠습니까?
      </p>

      <div style="display: flex; gap: 1rem">
        <button
          class="primary"
          :style="{
            flex: 1,
            padding: '1rem',
            fontSize: '1rem',
            backgroundColor: actionColor,
            color: isPaused ? '#000' : '#fff'
          }"
          @click="emit('confirm')"
        >
          {{ action }}하기
        </button>
        <button
          style="flex: 1; padding: 1rem; font-size: 1rem; background: transparent; border: 1px solid var(--border-color)"
          @click="emit('cancel')"
        >
          취소
        </button>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  ticker: String,
  name: String,
  isPaused: Boolean
});

const emit = defineEmits(['confirm', 'cancel']);

const action = computed(() => props.isPaused ? "재개" : "중지");
const actionColor = computed(() => props.isPaused ? "var(--primary)" : "var(--danger)");
</script>
