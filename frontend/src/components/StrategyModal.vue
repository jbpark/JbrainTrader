<template>
  <Teleport to="body">
    <div class="modal-overlay">
      <div class="modal-content glass" style="width: 800px; max-width: 90vw; height: 80vh">
        <div style="display: flex; justify-content: space-between; margin-bottom: 1.5rem; align-items: center">
          <h2 style="color: var(--primary)">📊 전략 관리자</h2>
          <button class="secondary" @click="emit('close')">닫기</button>
        </div>

        <div style="display: flex; gap: 20px; height: calc(100% - 100px)">
          <!-- List -->
          <div style="width: 250px; border-right: 1px solid rgba(255,255,255,0.1); overflow-y: auto; padding-right: 10px">
            <button class="primary" style="width: 100%; margin-bottom: 10px" @click="handleNew">+ 새 전략</button>
            <div style="display: flex; flex-direction: column; gap: 5px">
              <div
                v-for="s in strategies"
                :key="s.name"
                class="card"
                :class="{ active: selectedStrat?.name === s.name }"
                :style="{
                  padding: '10px',
                  cursor: 'pointer',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  backgroundColor: selectedStrat?.name === s.name ? 'rgba(0, 242, 254, 0.1)' : 'rgba(255,255,255,0.05)'
                }"
                @click="handleSelect(s)"
              >
                <span style="font-weight: bold">{{ s.name }}</span>
                <button
                  class="danger"
                  style="padding: 2px 8px; font-size: 0.7rem;"
                  @click.stop="handleDelete(s.name)"
                >삭제</button>
              </div>
            </div>
          </div>

          <!-- Editor -->
          <div style="flex: 1; display: flex; flex-direction: column; gap: 10px">
            <template v-if="isEditing">
              <input
                type="text"
                placeholder="전략 이름"
                v-model="name"
                style="font-size: 1.1rem; font-weight: bold"
              />
              <textarea
                placeholder="[BUY] ..."
                style="flex: 1; font-family: monospace; font-size: 0.9rem"
                v-model="content"
              ></textarea>
              <div style="display: flex; gap: 10px; justify-content: flex-end">
                <button class="secondary" @click="isEditing = false">취소</button>
                <button class="primary" @click="handleSave">전략 저장</button>
              </div>
            </template>
            <div v-else style="display: flex; align-items: center; justify-content: center; height: 100%; color: var(--text-dim)">
              왼쪽에서 전략을 선택하거나 새 전략을 만들어주세요.
            </div>
          </div>
        </div>
      </div>
    </div>
    <!-- Custom Alert Modal -->
    <StatusAlertModal
      :show="alertState.show"
      :type="alertState.type"
      :title="alertState.title"
      :message="alertState.message"
      @close="alertState.show = false"
    />
  </Teleport>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { fetchStrategies, saveStrategy, deleteStrategy } from '../api';
import StatusAlertModal from './StatusAlertModal.vue';

const emit = defineEmits(['close']);

const strategies = ref([]);
const selectedStrat = ref(null);
const name = ref('');
const content = ref('');
const isEditing = ref(false);

// Custom Alert Modal State
const alertState = reactive({
  show: false,
  type: 'success',
  title: '',
  message: '',
});

const showAlert = (type, title, message) => {
  alertState.type = type;
  alertState.title = title;
  alertState.message = message;
  alertState.show = true;
};

const loadStrategies = async () => {
  const data = await fetchStrategies();
  strategies.value = data;
};

onMounted(() => {
  loadStrategies();
});

const handleSave = async () => {
  if (!name.value || !content.value) {
    showAlert('error', '입력 오류', '이름과 내용을 모두 입력해주세요.');
    return;
  }
  const res = await saveStrategy(name.value, content.value);
  if (res.status === 'SUCCESS') {
    showAlert('success', '저장 완료', '전략이 성공적으로 저장되었습니다.');
    loadStrategies();
    isEditing.value = false;
    selectedStrat.value = null;
    name.value = '';
    content.value = '';
  } else {
    showAlert('error', '저장 실패', res.message || '저장 중 오류가 발생했습니다.');
  }
};

const handleDelete = async (stratName) => {
  if (!window.confirm(`'${stratName}' 전략을 삭제하시겠습니까?`)) return;
  const res = await deleteStrategy(stratName);
  if (res.status === 'SUCCESS') {
    loadStrategies();
    if (name.value === stratName) {
      name.value = '';
      content.value = '';
      isEditing.value = false;
    }
  }
};

const handleSelect = (strat) => {
  selectedStrat.value = strat;
  name.value = strat.name;
  content.value = strat.content;
  isEditing.value = true;
};

const handleNew = () => {
  selectedStrat.value = null;
  name.value = '';
  content.value = '[BUY]\nmax_steps = 3\n\n[BUY_STEP_1]\ncondition = price > ma_5\nsize = 0.4\n\n[SELL]\nmax_steps = 1\n\n[STOP_LOSS]\ncondition = price <= avg_price * 0.97';
  isEditing.value = true;
};
</script>
