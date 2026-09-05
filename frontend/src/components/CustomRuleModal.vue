<template>
  <Teleport to="body">
    <!-- Backdrop -->
    <div
      style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background-color: rgba(0,0,0,0.5); z-index: 9998"
      @click="emit('close')"
    ></div>

    <!-- Right Side Panel -->
    <div class="glass" style="position: fixed; top: 0; right: 0; width: 45vw; min-width: 700px; height: 100vh; background: #1a1d23; z-index: 9999; display: flex; flex-direction: column; padding: 2rem; box-shadow: -10px 0 30px rgba(0,0,0,0.5); border-left: 2px solid var(--primary)">
      <h2 style="margin-bottom: 0.5rem; display: flex; align-items: center; gap: 10px">
        📝 커스텀 전략 설정
      </h2>
      <p style="color: var(--text-muted); margin-bottom: 1.5rem; font-size: 0.9rem">
        상세한 실시간 매수 전략을 입력하세요. (Python 기반 문법 지원)
      </p>

      <div style="flex: 1; display: flex; flex-direction: column; gap: 1.5rem">
        <textarea
          style="flex: 1; width: 100%; font-size: 1.2rem; line-height: 1.6; padding: 1.5rem; font-family: Consolas, Monaco, monospace; background-color: #0d1117; color: #adbac7; border: 1px solid var(--border-color); border-radius: 8px; resize: none"
          v-model="rule"
          placeholder="예: EMA(20) > EMA(60) and RSI(14) < 30..."
        ></textarea>

        <div style="display: flex; gap: 1rem">
          <button class="primary" style="flex: 1; padding: 1rem; font-size: 1.1rem" @click="emit('save', rule)">확정 및 적용</button>
          <button style="flex: 1; padding: 1rem; font-size: 1.1rem" @click="emit('close')">취소</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref } from 'vue';

const props = defineProps({
  initialRule: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['save', 'close']);

const rule = ref(props.initialRule);
</script>
