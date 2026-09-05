<template>
  <Teleport to="body">
    <div class="modal-overlay" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.7); display: flex; justify-content: center; align-items: center; z-index: 1000">
      <div class="glass" style="padding: 2rem; width: 450px; display: flex; flex-direction: column; gap: 1rem">
        <h2 style="color: var(--primary); margin-top: 0">DEBUG-MODAL 가상 시뮬레이션</h2>
        <SimulationSettings 
          :initial-ticker="initialTicker"
          :tickers="tickers"
          :is-modal="true"
          @start="handleStart"
          @close="emit('close')"
        />
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { startSimulation } from '../api';
import SimulationSettings from './SimulationSettings.vue';

const props = defineProps({
  initialTicker: String,
  tickers: {
    type: Object,
    default: () => ({})
  }
});

const emit = defineEmits(['close']);

const handleStart = async ({ ticker, ohlcv }) => {
  await startSimulation(ticker, ohlcv);
  emit('close');
};
</script>
