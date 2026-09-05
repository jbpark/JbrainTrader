<template>
  <Teleport to="body">
    <!-- Backdrop -->
    <div
      style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background-color: rgba(0,0,0,0.5); z-index: 9998"
      @click="emit('close')"
    ></div>

    <!-- Right Side Panel -->
    <div class="glass" style="position: fixed; top: 0; right: 0; width: 45vw; min-width: 700px; height: 100vh; background: #1a1d23; z-index: 9999; display: flex; flex-direction: column; padding: 2rem; box-shadow: -10px 0 30px rgba(0,0,0,0.5); border-left: 2px solid var(--primary)">
      <h2 style="margin-bottom: 0.5rem">🔧 매수 전략 변경: {{ ticker }}</h2>
      <p style="color: var(--text-muted); margin-bottom: 1.5rem; font-size: 0.9rem">
        전략 변경 시 매매가 잠시 일시정지됩니다.
      </p>

      <div style="flex: 1; display: flex; flex-direction: column; gap: 1.5rem">
        <div>
          <label style="display: block; margin-bottom: 0.5rem; font-weight: bold">전략 선택</label>
          <select
            style="width: 100%; font-size: 1.1rem; padding: 12px"
            v-model="selectedRule"
          >
            <option v-for="r in rules" :key="r" :value="r">{{ r }}</option>
          </select>
        </div>

        <div style="flex: 1; display: flex; flex-direction: column">
          <label style="display: block; margin-bottom: 0.5rem; font-weight: bold">
            {{ selectedRule === 'CUSTOM' ? '커스텀 전략 편집' : '전략 상세 (읽기 전용)' }}
          </label>
          <textarea
            style="flex: 1; width: 100%; font-family: 'Fira Code', Consolas, Monaco, monospace; font-size: 0.95rem; line-height: 1.6; padding: 1.5rem; background-color: rgba(0,0,0,0.2); color: #00f2fe; border: 1px solid var(--border-color); border-radius: 8px; resize: none"
            :value="displayContent"
            @input="onTextareaInput"
            :readonly="selectedRule !== 'CUSTOM'"
            placeholder="[BUY] ..."
          ></textarea>
        </div>

        <div style="display: flex; gap: 1rem; margin-top: auto">
          <button class="primary" style="flex: 1; padding: 1rem; font-size: 1.1rem" @click="handleSave">저장 및 적용</button>
          <button style="flex: 1; padding: 1rem; font-size: 1.1rem" @click="emit('close')">취소</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch, onMounted, computed } from 'vue';
import { updateTickerRule, fetchStrategies } from '../api';

const props = defineProps({
  ticker: String,
  currentRule: String
});

const emit = defineEmits(['close']);

const savedStrategies = ref([]);
const selectedRule = ref('DEFAULT');
const customRule = ref('');

const rules = computed(() => ["없음", "DEFAULT", "GOLDEN_CROSS", "CUSTOM", ...savedStrategies.value.map(s => s.name)]);

const loadStrats = async () => {
  const data = await fetchStrategies();
  savedStrategies.value = data;

  const stratNames = data.map(s => s.name);

  // Set initial selection
  if (props.currentRule === 'NONE' || !props.currentRule) {
    selectedRule.value = '없음';
  } else if (["DEFAULT", "GOLDEN_CROSS"].includes(props.currentRule) || stratNames.includes(props.currentRule)) {
    selectedRule.value = props.currentRule;
  } else {
    selectedRule.value = 'CUSTOM';
    customRule.value = props.currentRule;
  }
};

const displayContent = computed(() => {
  if (selectedRule.value === '없음') return '(전략 없음 - 자동매매를 하지 않고 현재가만 모니터링합니다.)';
  if (selectedRule.value === 'CUSTOM') return customRule.value;
  const strat = savedStrategies.value.find(s => s.name === selectedRule.value);
  return strat ? strat.content : selectedRule.value;
});

onMounted(() => {
  loadStrats();
});

const handleSave = async () => {
  const finalRule = selectedRule.value === 'CUSTOM' ? customRule.value : (selectedRule.value === '없음' ? 'NONE' : selectedRule.value);
  await updateTickerRule(props.ticker, finalRule);
  emit('close');
};

const onTextareaInput = (e) => {
  if (selectedRule.value === 'CUSTOM') {
    customRule.value = e.target.value;
  }
};
</script>
