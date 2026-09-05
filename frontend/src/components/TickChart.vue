<template>
  <div class="chart-container" ref="container">
    <canvas ref="canvas"></canvas>
    
    <!-- Tooltip -->
    <div v-if="tooltip" class="chart-tooltip" :style="{ left: tooltip._x + 15 + 'px', top: tooltip._y - 40 + 'px' }">
      <div v-if="tooltip.marker === 'B'">
        <div class="tooltip-title buy">매수 정보</div>
        <div class="tooltip-item"><span>시간:</span> <span>{{ formatTime(tooltip.time) }}</span></div>
        <div class="tooltip-item"><span>매수량:</span> <span>{{ tooltip.qty }}</span></div>
        <div class="tooltip-item"><span>매수금액:</span> <span>{{ formatPrice(tooltip.amount) }}원</span></div>
      </div>
      <div v-if="tooltip.marker === 'S'">
        <div class="tooltip-title sell">매도 정보</div>
        <div class="tooltip-item"><span>시간:</span> <span>{{ formatTime(tooltip.time) }}</span></div>
        <div class="tooltip-item"><span>매도량:</span> <span>{{ tooltip.qty }}</span></div>
        <div class="tooltip-item"><span>매도금액:</span> <span>{{ formatPrice(tooltip.amount) }}원</span></div>
        <div class="tooltip-item profit">
          <span>실현손익:</span> 
          <span :style="{ color: tooltip.profit >= 0 ? '#00ff88' : '#ff4d4d' }">
            {{ formatPrice(tooltip.profit) }}원
          </span>
        </div>
        <div class="tooltip-item">
          <span>누적 실현손익:</span> 
          <span :style="{ color: tooltip.cumulative_profit >= 0 ? '#00ff88' : '#ff4d4d' }">
            {{ formatPrice(tooltip.cumulative_profit) }}원
          </span>
        </div>
      </div>
    </div>

    <!-- Crosshair Tooltip (General point) -->
    <div v-if="crosshair && !tooltip" class="chart-tooltip crosshair-tooltip" :style="{ left: crosshair.x + 15 + 'px', top: crosshair.y - 60 + 'px' }">
      <div class="tooltip-item">
        <span>시간:</span> 
        <span>{{ formatTimeWithTZ(crosshair.item) }}</span>
      </div>
      <div class="tooltip-item">
        <span>가격:</span> 
        <span style="color: #00ff88; font-weight: bold">{{ formatPrice(crosshair.item.value) }}</span>
      </div>
      <div class="tooltip-item" v-if="crosshair.item.volume">
        <span>거래량:</span> 
        <span style="color: #fed330">{{ crosshair.item.volume.toLocaleString() }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue';

const props = defineProps({
  ticker: String,
  staticData: {
    type: Array,
    default: null
  },
  comparisonData: {
    type: Object, // { strategyName: pnlHistoryArray }
    default: null
  },
  baseData: {
    type: Array, // [ { time, value, ... } ]
    default: null
  },
  tradeData: {
    type: Object, // { strategyName: [ { time, marker, ... } ] }
    default: null
  },
  timezone: {
    type: String,
    default: ''
  }
});

const container = ref(null);
const canvas = ref(null);
const data = ref([]);
const crosshair = ref(null); // { x, y, item, index }
let ws = null;
let animationFrameId = null;

// Design Constants
const COLORS = {
  background: '#1e293b',
  line: '#ffffff',
  grid: '#334155',
  buy: '#10b981',
  sell: '#ef4444',
  text: '#94a3b8'
};

const PADDING = { top: 20, right: 30, bottom: 40, left: 60 };

const initWebSocket = () => {
  if (props.comparisonData && props.baseData) {
    // Comparison Mode: No Websocket
    requestDraw();
    return;
  }

  if (props.staticData) {
    data.value = [...props.staticData];
    requestDraw();
    return;
  }

  if (ws) {
    ws.close();
  }

  const host = window.location.hostname || 'localhost';
  ws = new WebSocket(`ws://${host}:8765`);
  ws.onopen = () => {
    console.log('[TickChart] WebSocket connected, subscribing ticker:', props.ticker);
    if (props.ticker) ws.send(JSON.stringify({ type: 'subscribe', ticker: props.ticker }));
    else console.warn('[TickChart] ticker prop is empty, skipping subscribe');
  };
  ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.type === 'history') {
      data.value = message.data || [];
      console.log('[TickChart] Received history, count:', data.value.length);
    }
    else if (message.type === 'update') {
      data.value.push(message.data);
      if (data.value.length > 2000) data.value.shift();
    }
    requestDraw();
  };
  ws.onerror = (err) => {
    console.error('[TickChart] WebSocket error:', err);
  };
  ws.onclose = (ev) => {
    console.warn('[TickChart] WebSocket closed, code:', ev.code, 'reason:', ev.reason);
  };
};

const draw = () => {
  if (!canvas.value || !container.value) return;

  const ctx = canvas.value.getContext('2d');
  const width = container.value.clientWidth;
  const height = container.value.clientHeight;

  // Handle High DPI displays
  const dpr = window.devicePixelRatio || 1;
  canvas.value.width = width * dpr;
  canvas.value.height = height * dpr;
  canvas.value.style.width = `${width}px`;
  canvas.value.style.height = `${height}px`;
  ctx.scale(dpr, dpr);

  // Clear
  ctx.fillStyle = COLORS.background;
  ctx.fillRect(0, 0, width, height);

  const isComparison = props.comparisonData && props.baseData;
  const chartData = isComparison ? props.baseData : data.value;

  if (chartData.length < 2) {
    ctx.fillStyle = COLORS.text;
    ctx.font = '14px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('데이터를 기다리는 중...', width / 2, height / 2);
    return;
  }

  const chartWidth = width - PADDING.left - PADDING.right;
  const totalChartHeight = height - PADDING.top - PADDING.bottom;

  // Split height: 75% Price, 5% gap, 20% Volume
  const priceChartHeight = totalChartHeight * 0.75;
  const volumeChartHeight = totalChartHeight * 0.20;
  const volumeTop = PADDING.top + priceChartHeight + (totalChartHeight * 0.05);

  // Calculate scales
  let yMin, yMax, yRange;
  
  if (isComparison) {
    // Determine Y range from all comparison lines
    let allPnlValues = [];
    Object.values(props.comparisonData).forEach(arr => {
      allPnlValues.push(...arr.map(d => d.value).filter(v => !isNaN(v)));
    });
    const minPnl = Math.min(...allPnlValues);
    const maxPnl = Math.max(...allPnlValues);
    const pnlRange = (maxPnl - minPnl) || (minPnl ? Math.abs(minPnl) * 0.01 : 1);
    yMin = minPnl - pnlRange * 0.1;
    yMax = maxPnl + pnlRange * 0.1;
    yRange = yMax - yMin;
  } else {
    const values = chartData.map(d => d.value).filter(v => v !== null && v !== undefined && !isNaN(v));
    const minVal = Math.min(...values);
    const maxVal = Math.max(...values);
    const range = (maxVal - minVal) || (minVal ? Math.abs(minVal) * 0.01 : 1);
    yMin = minVal - range * 0.1;
    yMax = maxVal + range * 0.1;
    yRange = yMax - yMin;
  }

  // Time Scale
  let tMin = chartData[0].time || (chartData[0].datetime ? new Date(chartData[0].datetime).getTime() : 0);
  let tMax = chartData[chartData.length - 1].time || (chartData[chartData.length - 1].datetime ? new Date(chartData[chartData.length - 1].datetime).getTime() : 1);

  // 한국 주식 시장(KST) 기준 X축 범위 보정 (백테스트 시 가시성 확보)
  const dMin = new Date(tMin);
  // 만약 08:00 ~ 10:00 사이 시작한다면 09:00로 고정 (장 시작 시점부터 보기 위해)
  if (dMin.getHours() >= 8 && dMin.getHours() < 10) {
      dMin.setHours(9, 0, 0, 0);
      tMin = dMin.getTime();
  }
  
  // 만약 15:00 ~ 16:00 사이 끝난다면 15:30으로 고정 (장 마감 시점까지 보기 위해)
  const dMax = new Date(tMax);
  if (dMax.getHours() >= 15 && dMax.getHours() < 17) {
      dMax.setHours(15, 30, 0, 0);
      tMax = dMax.getTime();
  }

  const tRange = tMax - tMin || 1;

  const getX = (item) => {
    const ts = item.time || (item.datetime ? new Date(item.datetime).getTime() : 0);
    // tMin 이전 데이터(예: 08:59)는 왼쪽 끝에 고정, tMax 이후는 오른쪽 끝에 고정
    const xRatio = Math.max(0, Math.min(1, (ts - tMin) / tRange));
    return PADDING.left + xRatio * chartWidth;
  };
  const getY = (val) => PADDING.top + priceChartHeight - ((val - yMin) / yRange) * priceChartHeight;

  // Volume Scale
  const maxVolume = Math.max(...chartData.map(d => d.volume || 0)) || 1;
  const getVolY = (vol) => volumeTop + volumeChartHeight - (vol / maxVolume) * volumeChartHeight;

  // Draw Grid & Labels
  ctx.strokeStyle = COLORS.grid;
  ctx.setLineDash([5, 5]);
  const steps = 5;
  for (let i = 0; i <= steps; i++) {
    const val = yMin + (yRange * i) / steps;
    const y = getY(val);
    ctx.beginPath();
    ctx.moveTo(PADDING.left, y);
    ctx.lineTo(width - PADDING.right, y);
    ctx.stroke();

    ctx.setLineDash([]);
    ctx.fillStyle = COLORS.text;
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(Math.round(val).toLocaleString(), PADDING.left - 10, y + 4);
    ctx.setLineDash([5, 5]);
  }
  
  // Volume Grid
  ctx.beginPath();
  ctx.moveTo(PADDING.left, volumeTop);
  ctx.lineTo(width - PADDING.right, volumeTop);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillText(maxVolume.toLocaleString(), PADDING.left - 10, volumeTop + 10);

  // Time Labels (X-axis)
  if (chartData.length > 1) {
    ctx.fillStyle = COLORS.text;
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'center';
    
    const labelCount = 5;
    for (let i = 0; i <= labelCount; i++) {
        // 데이터 인덱스 대신 전체 시간 범위를 등분하여 라벨 배치
        const currentTs = tMin + (tRange * i) / labelCount;
        const x = PADDING.left + (i / labelCount) * chartWidth;
        const timeStr = formatTime(currentTs);
        ctx.fillText(timeStr, x, volumeTop + volumeChartHeight + 20);
    }
  }

  // Draw Volume Bars First (Behind Lines)
  const barWidth = Math.max(1, (chartWidth / chartData.length) * 0.6);
  chartData.forEach((d, i) => {
    if (!d.volume) return;
    const x = getX(d);
    const vY = getVolY(d.volume);
    
    // Color based on price change if available, otherwise neutral
    let color = 'rgba(255, 255, 255, 0.2)';
    if (i > 0) {
      if (d.value > chartData[i-1].value) color = 'rgba(239, 68, 68, 0.4)'; // Red
      else if (d.value < chartData[i-1].value) color = 'rgba(59, 130, 246, 0.4)'; // Blue
    }
    
    ctx.fillStyle = color;
    ctx.fillRect(x - barWidth/2, vY, barWidth, volumeTop + volumeChartHeight - vY);
  });

  // Comparison Mode Rendering
  if (isComparison) {
    // 1. Draw Base Price (More Visible now)
    const priceValues = props.baseData.map(d => d.value);
    const pMin = Math.min(...priceValues);
    const pMax = Math.max(...priceValues);
    const pRange = pMax - pMin || 1;
    const getPriceY = (val) => PADDING.top + priceChartHeight - ((val - pMin) / pRange) * priceChartHeight * 0.4 - priceChartHeight * 0.6; 
    
    ctx.strokeStyle = 'rgba(255,255,255,0.3)'; // Increased opacity
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    props.baseData.forEach((d, i) => {
      if (i === 0) ctx.moveTo(getX(d), getPriceY(d.value));
      else ctx.lineTo(getX(d), getPriceY(d.value));
    });
    ctx.stroke();

    // 2. Draw Equity Curves for each strategy
    const STRAT_COLORS = ['#3b82f6', '#ec4899', '#f59e0b', '#10b981', '#8b5cf6'];
    Object.entries(props.comparisonData).forEach(([name, points], idx) => {
      const color = STRAT_COLORS[idx % STRAT_COLORS.length];
      ctx.strokeStyle = color;
      ctx.lineWidth = 3; // Thicker lines
      ctx.beginPath();
      points.forEach((p, i) => {
        const x = getX(p);
        const y = getY(p.value);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();

      // Label at end (Improved)
      if (points.length > 0) {
        const last = points[points.length - 1];
        ctx.fillStyle = color;
        ctx.font = 'bold 11px sans-serif';
        ctx.textAlign = 'left';
        ctx.shadowBlur = 4;
        ctx.shadowColor = 'rgba(0,0,0,0.5)';
        ctx.fillText(name, getX(last) + 8, getY(last.value) + 4);
        ctx.shadowBlur = 0;
      }
    });

    // 3. Draw Trade Markers for each strategy if available
    if (props.tradeData) {
      Object.entries(props.tradeData).forEach(([name, trades], idx) => {
        // Use same color sequence as equity curves
        const STRAT_COLORS = ['#3b82f6', '#ec4899', '#f59e0b', '#10b981', '#8b5cf6'];
        const color = STRAT_COLORS[idx % STRAT_COLORS.length];
        const pnlPoints = props.comparisonData[name] || [];
        
        trades.forEach(trade => {
          // Find corresponding point in pnlPoints by time
          const pnlPointIdx = pnlPoints.findIndex(p => Math.abs(p.time - trade.time) < 1000); // 1s tolerance
          if (pnlPointIdx !== -1) {
            const pnlPoint = pnlPoints[pnlPointIdx];
            const x = getX(pnlPoint);
            const y = getY(pnlPoint.value);
            
            // Draw Marker (Simple Circle with B/S)
            const isBuy = trade.marker === 'B';
            const markerBg = isBuy ? '#10b981' : '#ef4444';
            
            ctx.beginPath();
            ctx.arc(x, y, 8, 0, Math.PI * 2);
            ctx.fillStyle = markerBg;
            ctx.fill();
            
            // White border for pop
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 1;
            ctx.stroke();
            
            ctx.fillStyle = '#ffffff';
            ctx.font = 'bold 9px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(trade.marker, x, y);
          }
        });
      });
    }

  } else {
    // Regular Mode Rendering (Price Line + Fill)
    const grad = ctx.createLinearGradient(0, PADDING.top, 0, PADDING.top + priceChartHeight);
    grad.addColorStop(0, `${COLORS.line}33`);
    grad.addColorStop(1, `${COLORS.line}00`);
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.moveTo(getX(chartData[0]), getY(chartData[0].value));
    chartData.forEach((d, i) => ctx.lineTo(getX(d), getY(d.value)));
    ctx.lineTo(getX(chartData[chartData.length - 1]), PADDING.top + priceChartHeight);
    ctx.lineTo(getX(chartData[0]), PADDING.top + priceChartHeight);
    ctx.fill();

    // Draw Line
    let isHolding = false;
    for (let i = 0; i < chartData.length - 1; i++) {
        const current = chartData[i];
        if (current.marker === 'B') isHolding = true;
        else if (current.marker === 'S') isHolding = false;
        
        ctx.beginPath();
        ctx.strokeStyle = COLORS.line;
        ctx.lineWidth = isHolding ? 3 : 1;
        ctx.moveTo(getX(current), getY(current.value));
        ctx.lineTo(getX(chartData[i + 1]), getY(chartData[i + 1].value));
        ctx.stroke();
    }

    // Draw Markers
    chartData.forEach((item, index) => {
      if (item.marker) {
        const x = getX(item), y = getY(item.value);
        const color = item.marker === 'B' ? '#00ff88' : '#ff4d4d';
        item._x = x; item._y = item.marker === 'B' ? y + 30 : y - 30;
        ctx.beginPath(); ctx.arc(x, item._y, 10, 0, Math.PI * 2);
        ctx.fillStyle = color; ctx.fill();
        ctx.fillStyle = '#1e293b'; ctx.font = 'bold 10px sans-serif'; ctx.textAlign = 'center';
        ctx.textBaseline = 'middle'; ctx.fillText(item.marker, x, item._y);
      }
    });
  }

  // Draw crosshair if active
  if (crosshair.value && !tooltip.value) {
    const item = crosshair.value.item;
    const x = getX(item);
    const y = getY(item.value);

    // Vertical line
    ctx.beginPath();
    ctx.strokeStyle = COLORS.text;
    ctx.setLineDash([2, 2]);
    ctx.moveTo(x, PADDING.top);
    ctx.lineTo(x, height - PADDING.bottom);
    ctx.stroke();

    // Horizontal line
    ctx.beginPath();
    ctx.moveTo(PADDING.left, y);
    ctx.lineTo(width - PADDING.right, y);
    ctx.stroke();
    ctx.setLineDash([]);

    // Price label on Y-axis
    ctx.fillStyle = COLORS.background;
    ctx.fillRect(width - PADDING.right, y - 8, PADDING.right, 16);
    ctx.fillStyle = COLORS.line;
    ctx.textAlign = 'left';
    ctx.fillText(formatPrice(item.value), width - PADDING.right + 5, y + 4);

    // Time label on X-axis
    ctx.fillStyle = COLORS.background;
    ctx.fillRect(x - 35, height - PADDING.bottom, 70, PADDING.bottom);
    ctx.fillStyle = COLORS.line;
    ctx.textAlign = 'center';
    ctx.fillText(formatTime(item.time || new Date(item.datetime).getTime()), x, height - PADDING.bottom + 15);
  }
};

const requestDraw = () => {
  if (animationFrameId) return;
  animationFrameId = requestAnimationFrame(() => {
    draw();
    animationFrameId = null;
  });
};

const handleResize = () => {
  requestDraw();
};

const tooltip = ref(null);
const highlightedRange = ref(null);

const handleMouseMove = (e) => {
  if (!canvas.value || !container.value) return;
  const rect = canvas.value.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;

  const isComparison = props.comparisonData && props.baseData;
  const chartData = isComparison ? props.baseData : data.value;

  let found = null;
  let foundIndex = -1;
  chartData.forEach((item, idx) => {
    if (item.marker && item._x !== undefined) {
      const dx = x - item._x;
      const dy = y - item._y;
      if (Math.sqrt(dx * dx + dy * dy) < 15) { // detection radius
        found = item;
        foundIndex = idx;
      }
    }
  });

  tooltip.value = found;
  
  if (foundIndex !== -1) {
    const item = chartData[foundIndex];
    let start = -1;
    let end = -1;

    if (item.marker === 'B') {
      start = foundIndex;
      // find next S
      for (let i = start + 1; i < chartData.length; i++) {
        if (chartData[i].marker === 'S') {
          end = i;
          break;
        }
      }
      if (end === -1) end = chartData.length - 1;
    } else if (item.marker === 'S') {
      end = foundIndex;
      // find previous B
      for (let i = end - 1; i >= 0; i--) {
        if (chartData[i].marker === 'B') {
          start = i;
          break;
        }
      }
    }

    if (start !== -1 && end !== -1) {
      highlightedRange.value = { start, end };
    } else {
      highlightedRange.value = null;
    }
    crosshair.value = null; // Hide crosshair if a marker tooltip is active
  } else {
    highlightedRange.value = null;
    
    // General point detection for crosshair (find closest by Time)
    const chartWidth = container.value.clientWidth - PADDING.left - PADDING.right;
    const relativeX = x - PADDING.left;
    
    if (relativeX >= 0 && relativeX <= chartWidth && chartData.length > 0) {
      // Calculate the timestamp at this X position
      // Using exactly the same scale logic as in draw()
      let tMin = chartData[0].time || (chartData[0].datetime ? new Date(chartData[0].datetime).getTime() : 0);
      let tMax = chartData[chartData.length - 1].time || (chartData[chartData.length - 1].datetime ? new Date(chartData[chartData.length - 1].datetime).getTime() : 1);
      
      const dMin = new Date(tMin);
      if (dMin.getHours() >= 8 && dMin.getHours() < 10) { dMin.setHours(9, 0, 0, 0); tMin = dMin.getTime(); }
      const dMax = new Date(tMax);
      if (dMax.getHours() >= 15 && dMax.getHours() < 17) { dMax.setHours(15, 30, 0, 0); tMax = dMax.getTime(); }
      
      const tRange = tMax - tMin || 1;
      const targetTs = tMin + (relativeX / chartWidth) * tRange;
      
      // Find the closest point in chartData (Binary Search or iteration)
      // Since it's usually < 2000 points, simple iteration or binary search is fine.
      let closest = chartData[0];
      let minDiff = Math.abs((closest.time || new Date(closest.datetime).getTime()) - targetTs);
      
      // Simplified search (assuming data is sorted by time)
      for (let i = 1; i < chartData.length; i++) {
        const item = chartData[i];
        const ts = item.time || new Date(item.datetime).getTime();
        const diff = Math.abs(ts - targetTs);
        if (diff < minDiff) {
          minDiff = diff;
          closest = item;
        } else {
          // Since data is sorted, once diff starts increasing, we found the closest
          break;
        }
      }

      if (closest) {
        crosshair.value = { 
          x: x, 
          y: y,
          item: closest,
          index: chartData.indexOf(closest)
        };
      }
    } else {
      crosshair.value = null;
    }
  }
  
  if (found || highlightedRange.value || crosshair.value) {
    requestDraw();
  }
};

const handleMouseLeave = () => {
  tooltip.value = null;
  crosshair.value = null;
  highlightedRange.value = null;
  requestDraw();
};

const formatPrice = (val) => val?.toLocaleString() || '0';
const formatTime = (ts) => {
  if (!ts) return '';
  const d = new Date(ts);
  
  const isUS = props.timezone === 'America/New_York' || (props.ticker && !props.ticker.split('.')[0].match(/^[0-9]+$/));
  const tz = isUS ? 'America/New_York' : 'Asia/Seoul';
  
  return d.toLocaleTimeString('en-US', { 
    hour: '2-digit', minute: '2-digit', second: '2-digit', 
    hour12: false, 
    timeZone: tz 
  });
};

const formatTimeWithTZ = (item) => {
  if (!item) return '';
  const ts = item.time || (item.datetime ? new Date(item.datetime).getTime() : 0);
  const d = new Date(ts);
  
  const optionsBase = { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false };
  const isUS = props.timezone === 'America/New_York' || (props.ticker && !props.ticker.split('.')[0].match(/^[0-9]+$/));

  // Seoul(KR) Time always useful for Korean users
  const seoulTime = d.toLocaleTimeString('ko-KR', { ...optionsBase, timeZone: 'Asia/Seoul' });
  
  if (isUS) {
    // New York(NY) Time for US Market with dynamic EST/EDT
    const nyTimeFull = d.toLocaleTimeString('en-US', { ...optionsBase, timeZone: 'America/New_York', timeZoneName: 'short' });
    // Remove AM/PM if present and ensure clean string
    const nyTime = nyTimeFull.replace(/\s?[AP]M\s?/i, '');
    return `NY: ${nyTime} / KR: ${seoulTime}`;
  }
  
  return `KR: ${seoulTime}`;
};

onMounted(() => {
  initWebSocket();
  window.addEventListener('resize', handleResize);
  canvas.value.addEventListener('mousemove', handleMouseMove);
  canvas.value.addEventListener('mouseleave', handleMouseLeave);
  requestDraw();
});

onUnmounted(() => {
  if (ws) ws.close();
  window.removeEventListener('resize', handleResize);
  if (canvas.value) {
    canvas.value.removeEventListener('mousemove', handleMouseMove);
    canvas.value.removeEventListener('mouseleave', handleMouseLeave);
  }
  if (animationFrameId) cancelAnimationFrame(animationFrameId);
});

watch([() => props.ticker, () => props.staticData, () => props.comparisonData, () => props.baseData, () => props.tradeData], () => {
  data.value = []; // Reset real-time data when any static/comparison prop changes
  initWebSocket();
  requestDraw();
}, { deep: true });
</script>

<style scoped>
.chart-container {
  width: 100%;
  height: 350px;
  position: relative;
  background-color: v-bind('COLORS.background');
  border-radius: 8px;
  overflow: hidden;
}

.chart-tooltip {
  position: absolute;
  background: rgba(15, 23, 42, 0.95);
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 10px;
  pointer-events: none;
  z-index: 100;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
  min-width: 150px;
  backdrop-filter: blur(4px);
}

.tooltip-title {
  font-weight: bold;
  font-size: 0.9rem;
  margin-bottom: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid #334155;
}

.tooltip-title.buy { color: #00ff88; }
.tooltip-title.sell { color: #ff4d4d; }

.tooltip-item {
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
  line-height: 1.6;
  color: #94a3b8;
  gap: 15px;
}

.tooltip-item span:last-child {
  color: #f8fafc;
  font-weight: 500;
}

.tooltip-item.profit {
  margin-top: 4px;
  padding-top: 4px;
  border-top: 1px dashed #334155;
}
</style>
