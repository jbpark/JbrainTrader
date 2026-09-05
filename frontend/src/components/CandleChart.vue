<template>
  <div class="candle-chart-container" ref="container">
    <canvas ref="canvas"></canvas>
    <div v-if="tooltip" class="candle-tooltip" :style="{ left: tooltip.x + 15 + 'px', top: tooltip.y - 120 + 'px' }">
      <div class="tooltip-time">{{ formatTimeWithTZ(tooltip.data) }}</div>
      <div class="tooltip-grid">
        <span>시가:</span> <span>{{ formatPrice(tooltip.data.open) }}</span>
        <span>고가:</span> <span class="high">{{ formatPrice(tooltip.data.high) }}</span>
        <span>저가:</span> <span class="low">{{ formatPrice(tooltip.data.low) }}</span>
        <span>종가:</span> <span :class="getPriceClass(tooltip.data)">{{ formatPrice(tooltip.data.close) }}</span>
        <span>거래량:</span> <span class="vol">{{ tooltip.data.volume.toLocaleString() }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue';

const props = defineProps({
  data: {
    type: Array,
    required: true
  },
  ticker: String,
  timezone: String
});

const container = ref(null);
const canvas = ref(null);
const tooltip = ref(null);
let animationFrameId = null;

const THEME = {
  bg: '#1e1e2d',
  grid: 'rgba(255, 255, 255, 0.05)',
  text: '#94a3b8',
  upBody: '#ff4d4d',
  upWick: '#ff4d4d',
  downBody: '#4dabf7',
  downWick: '#4dabf7',
  neutral: '#94a3b8'
};

const PADDING = { top: 30, right: 50, bottom: 30, left: 60 };

const draw = () => {
  if (!canvas.value || !container.value || props.data.length < 2) return;

  const ctx = canvas.value.getContext('2d');
  const width = container.value.clientWidth;
  const height = container.value.clientHeight;

  const dpr = window.devicePixelRatio || 1;
  canvas.value.width = width * dpr;
  canvas.value.height = height * dpr;
  canvas.value.style.width = `${width}px`;
  canvas.value.style.height = `${height}px`;
  ctx.scale(dpr, dpr);

  ctx.fillStyle = THEME.bg;
  ctx.fillRect(0, 0, width, height);

  const chartWidth = width - PADDING.left - PADDING.right;
  const totalChartHeight = height - PADDING.top - PADDING.bottom;
  
  // Split height: 75% Price, 5% gap, 20% Volume
  const priceChartHeight = totalChartHeight * 0.75;
  const volumeChartHeight = totalChartHeight * 0.20;
  const volumeTop = PADDING.top + priceChartHeight + (totalChartHeight * 0.05);

  // Price Scale calculations
  const prices = props.data.flatMap(d => [d.high, d.low]);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const priceRange = (maxPrice - minPrice) || 1;
  const yPadding = priceRange * 0.1;

  const yMin = minPrice - yPadding;
  const yMax = maxPrice + yPadding;
  const yRange = yMax - yMin;

  // Volume Scale calculations
  const maxVolume = Math.max(...props.data.map(d => d.volume)) || 1;

  const getX = (i) => PADDING.left + (i / (props.data.length - 1)) * chartWidth;
  const getY = (price) => PADDING.top + priceChartHeight - ((price - yMin) / yRange) * priceChartHeight;
  const getVolY = (vol) => volumeTop + volumeChartHeight - (vol / maxVolume) * volumeChartHeight;

  // Grid & Labels (Price)
  ctx.strokeStyle = THEME.grid;
  ctx.lineWidth = 1;
  ctx.font = '10px sans-serif';
  ctx.fillStyle = THEME.text;
  ctx.textAlign = 'right';

  const gridSteps = 5;
  for (let i = 0; i <= gridSteps; i++) {
    const p = yMin + (yRange * i) / gridSteps;
    const y = getY(p);
    ctx.beginPath();
    ctx.moveTo(PADDING.left, y);
    ctx.lineTo(width - PADDING.right, y);
    ctx.stroke();
    ctx.fillText(Math.round(p).toLocaleString(), PADDING.left - 10, y + 4);
  }

  // Volume Grid (Top line of volume section)
  ctx.beginPath();
  ctx.moveTo(PADDING.left, volumeTop);
  ctx.lineTo(width - PADDING.right, volumeTop);
  ctx.stroke();
  ctx.fillText(maxVolume.toLocaleString(), PADDING.left - 10, volumeTop + 10);

  // Time Labels (X-axis)
  if (props.data.length > 1) {
    ctx.fillStyle = THEME.text;
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'center';
    
    const labelCount = 5;
    for (let i = 0; i <= labelCount; i++) {
        const dataIdx = Math.floor((props.data.length - 1) * i / labelCount);
        const item = props.data[dataIdx];
        if (item && item.datetime) {
            const x = getX(dataIdx);
            const timeStr = item.datetime.includes(' ') ? item.datetime.split(' ')[1] : item.datetime;
            ctx.fillText(timeStr, x, volumeTop + volumeChartHeight + 20);
        }
    }
  }

  // Candles & Volume Bars
  const itemWidth = (chartWidth / props.data.length) * 0.8;

  props.data.forEach((d, i) => {
    const x = getX(i);
    const isUp = d.close >= d.open;
    const color = isUp ? THEME.upBody : THEME.downBody;

    // 1. Draw Volume Bar
    ctx.fillStyle = color;
    ctx.globalAlpha = 0.4; // Volume bars are slightly transparent
    const vY = getVolY(d.volume);
    ctx.fillRect(x - itemWidth / 2, vY, itemWidth, volumeTop + volumeChartHeight - vY);
    ctx.globalAlpha = 1.0;

    // 2. Draw Candle
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = 1;

    // Wick
    ctx.beginPath();
    ctx.moveTo(x, getY(d.high));
    ctx.lineTo(x, getY(d.low));
    ctx.stroke();

    // Body
    const bodyTop = getY(Math.max(d.open, d.close));
    const bodyBottom = getY(Math.min(d.open, d.close));
    const bodyHeight = Math.max(Math.abs(bodyTop - bodyBottom), 1);

    ctx.fillRect(x - itemWidth / 2, bodyTop, itemWidth, bodyHeight);
    
    // Store coords for interaction
    d._x = x;
    d._y = bodyTop; // For better tooltip placement
  });
};

const handleMouseMove = (e) => {
  if (!canvas.value || props.data.length === 0) return;
  const rect = canvas.value.getBoundingClientRect();
  const x = e.clientX - rect.left;
  
  const chartWidth = container.value.clientWidth - PADDING.left - PADDING.right;
  const relativeX = x - PADDING.left;
  const index = Math.round((relativeX / chartWidth) * (props.data.length - 1));

  if (index >= 0 && index < props.data.length) {
    const d = props.data[index];
    tooltip.value = {
      x: d._x,
      y: d._y,
      data: d
    };
  } else {
    tooltip.value = null;
  }
};

 const formatPrice = (p) => p.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 });
 
 const formatTimeWithTZ = (item) => {
   if (!item || !item.datetime) return '';
   const ts = new Date(item.datetime).getTime();
   const d = new Date(ts);
   
   const optionsBase = { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false };
   const isUS = props.timezone === 'America/New_York' || (props.ticker && !props.ticker.split('.')[0].match(/^[0-9]+$/));

   const seoulTime = d.toLocaleTimeString('ko-KR', { ...optionsBase, timeZone: 'Asia/Seoul' });
   
   if (isUS) {
     const nyTimeFull = d.toLocaleTimeString('en-US', { ...optionsBase, timeZone: 'America/New_York', timeZoneName: 'short' });
     const nyTime = nyTimeFull.replace(/\s?[AP]M\s?/i, '');
     return `NY: ${nyTime} / KR: ${seoulTime}`;
   }
   
   return `KR: ${seoulTime}`;
 };

const getPriceClass = (d) => d.close >= d.open ? 'up' : 'down';

const requestDraw = () => {
  if (animationFrameId) cancelAnimationFrame(animationFrameId);
  animationFrameId = requestAnimationFrame(draw);
};

const handleResize = () => requestDraw();

onMounted(() => {
  window.addEventListener('resize', handleResize);
  canvas.value.addEventListener('mousemove', handleMouseMove);
  canvas.value.addEventListener('mouseleave', () => tooltip.value = null);
  requestDraw();
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  if (animationFrameId) cancelAnimationFrame(animationFrameId);
});

watch(() => props.data, () => requestDraw(), { deep: true });
</script>

<style scoped>
.candle-chart-container {
  width: 100%;
  height: 100%;
  position: relative;
  background: v-bind('THEME.bg');
  cursor: crosshair;
}

canvas {
  display: block;
}

.candle-tooltip {
  position: absolute;
  background: rgba(30, 30, 45, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 12px;
  border-radius: 8px;
  pointer-events: none;
  z-index: 100;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
  min-width: 180px;
  backdrop-filter: blur(4px);
}

.tooltip-time {
  font-size: 0.8rem;
  color: #94a3b8;
  margin-bottom: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.tooltip-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 4px 12px;
  font-size: 0.85rem;
  color: #cbd5e1;
}

.tooltip-grid span:nth-child(even) {
  text-align: right;
  font-weight: bold;
  font-family: 'Fira Code', monospace;
}

.high { color: #ff4d4d; }
.low { color: #4dabf7; }
.up { color: #ff4d4d; }
.down { color: #4dabf7; }
.vol { color: #fed330; }
</style>
