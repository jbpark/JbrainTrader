<template>
  <div v-if="!ticker" style="padding: 2rem; text-align: center">종목을 선택하세요</div>
  <div v-else class="analysis-panel">
    <div class="panel-header">
      <h4 style="margin: 0">주식 틱 그래프 ({{ name }})</h4>
    </div>

    <div class="chart-wrapper">
      <TickChart :ticker="ticker" />
    </div>

  </div>
</template>

<script setup>
import TickChart from './TickChart.vue';

const props = defineProps({
  ticker: String,
  name: String,
  analysis: Object
});
</script>

<style scoped>
.analysis-panel {
  padding: 1.5rem;
  background: #0f172a; /* Body background color from requirements */
  border-radius: 0 0 12px 12px;
  min-height: 450px;
  color: #f8fafc;
  border: 1px solid rgba(255,255,255,0.05);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.chart-wrapper {
  background: #1e293b; /* Canvas background from requirements */
  border-radius: 8px;
  padding: 10px;
}

</style>

