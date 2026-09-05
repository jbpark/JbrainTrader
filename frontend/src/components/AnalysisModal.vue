<template>
  <Teleport to="body">
    <!-- Backdrop -->
    <div
      style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background-color: rgba(0,0,0,0.6); backdrop-filter: blur(3px); z-index: 10000"
      @click="emit('close')"
    ></div>

    <!-- Main Modal -->
    <div class="glass" style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 450px; background: #1a1d23; z-index: 10001; display: flex; flex-direction: column; padding: 2rem; box-shadow: 0 25px 60px rgba(0,0,0,0.8); border: 1px solid var(--primary); border-radius: 16px">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.5rem">
        <div>
          <h2 style="font-size: 1.4rem">🔍 실시간 지표 분석</h2>
          <p style="color: var(--text-muted); font-size: 0.9rem">{{ name }} ({{ ticker }})</p>
        </div>
        <button @click="emit('close')" style="background: transparent; border: none; color: #fff; font-size: 1.5rem; cursor: pointer; padding: 0">×</button>
      </div>

      <div v-if="!analysis" style="padding: 2rem; text-align: center">
        <div class="loader" style="margin-bottom: 1rem">⏳</div>
        <p>지표 데이터를 계산하는 중입니다...</p>
        <p style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.5rem">
          (충분한 분봉 데이터가 수집될 때까지 잠시만 기다려주세요)
        </p>
      </div>
      <div v-else style="display: flex; flex-direction: column; gap: 1rem">
        <!-- EMA Analysis -->
        <div style="background: rgba(255,255,255,0.03); padding: 1.2rem; border-radius: 12px; border: 1px solid var(--border-color)">
          <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem">
            <span style="color: var(--text-muted)">이동평균선 (EMA)</span>
            <span style="font-weight: bold" :style="{ color: analysis.ema_status === 'UP' ? 'var(--primary)' : 'var(--danger)' }">
              {{ analysis.ema_status === 'UP' ? 'EMA 정배열' : 'EMA 역배열' }}
            </span>
          </div>
          <div style="display: flex; align-items: center; justify-content: space-around; font-size: 1.1rem">
            <span>EMA(20): <strong style="color: var(--primary)">{{ analysis.ema20.toLocaleString() }}</strong></span>
            <span style="color: var(--text-muted)">{{ analysis.ema_status === 'UP' ? '＞' : '≤' }}</span>
            <span>EMA(60): <strong>{{ analysis.ema60.toLocaleString() }}</strong></span>
          </div>
        </div>

        <!-- MACD Analysis -->
        <div style="background: rgba(255,255,255,0.03); padding: 1.2rem; border-radius: 12px; border: 1px solid var(--border-color)">
          <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem">
            <span style="color: var(--text-muted)">추세지표 (MACD)</span>
            <span style="font-weight: bold" :style="{ color: analysis.macd_status === 'UP' ? 'var(--primary)' : 'var(--danger)' }">
              {{ analysis.macd_status === 'UP' ? 'MACD 상향' : 'MACD 하향' }}
            </span>
          </div>
          <div style="display: flex; align-items: center; justify-content: space-around; font-size: 1.1rem; margin-bottom: 0.8rem">
            <span>MACD: <strong style="color: var(--primary)">{{ analysis.macd.toFixed(3) }}</strong></span>
            <span style="color: var(--text-muted)">{{ analysis.macd_status === 'UP' ? '＞' : '≤' }}</span>
            <span>Signal: <strong>{{ analysis.signal.toFixed(3) }}</strong></span>
          </div>
          <div style="border-top: 1px solid rgba(255,255,255,0.05); padding-top: 0.8rem; display: flex; justify-content: space-between; align-items: center">
            <span style="color: var(--text-muted)">히스토그램</span>
            <div style="display: flex; align-items: center; gap: 8px">
              <span style="font-weight: bold" :style="{ color: analysis.hist_status === 'INCREASE' ? 'var(--primary)' : 'var(--danger)' }">
                {{ analysis.hist_status === 'INCREASE' ? '▲ 증가' : '▼ 감소' }}
              </span>
              <span style="font-size: 0.9rem">({{ analysis.hist.toFixed(3) }})</span>
            </div>
          </div>
        </div>

        <div style="margin-top: 0.5rem; text-align: center">
          <p style="font-size: 0.8rem; color: var(--text-muted)">
            * 데이터는 시스템 연동 주기에 따라 실시간 업데이트됩니다.
          </p>
        </div>
      </div>

      <button class="primary" style="margin-top: 1.5rem; padding: 0.8rem" @click="emit('close')">확인</button>
    </div>
  </Teleport>
</template>

<script setup>
defineProps({
  ticker: String,
  name: String,
  analysis: Object
});

const emit = defineEmits(['close']);
</script>
