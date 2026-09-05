<template>
  <div class="main-tab-content glass" style="flex: 1; overflow: hidden; display: flex; flex-direction: column; gap: 2rem; padding: 2.5rem">
    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid var(--primary); padding-bottom: 1rem">
      <h2 style="color: var(--primary); margin: 0; display: flex; align-items: center; gap: 12px">
        <span style="font-size: 1.8rem">📊</span> 전략 관리자
        <button 
          @click="showHelp = !showHelp" 
          style="background: rgba(0, 242, 254, 0.1); border: 1px solid var(--primary); color: var(--primary); padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; cursor: pointer; margin-left: 10px; transition: all 0.2s"
          :style="showHelp ? 'background: var(--primary); color: black' : ''"
        >
          {{ showHelp ? '도움말 닫기' : '도움말 보기' }}
        </button>
      </h2>
      <div style="text-align: right">
        <div style="font-size: 0.9rem; color: var(--text-main); font-weight: 600">활성 전략 프로파일</div>
        <div style="font-size: 0.8rem; color: var(--primary)">{{ filteredStrategies.length }}개 표시됨 (총 {{ strategies.length }}개)</div>
      </div>
    </div>

    <div style="display: flex; gap: 20px; flex: 1; min-height: 0">
      <!-- List -->
      <div style="width: 280px; border-right: 1px solid rgba(255,255,255,0.1); overflow-y: auto; padding-right: 10px; display: flex; flex-direction: column; gap: 1rem">
        <button class="primary" style="width: 100%" @click="handleNew">+ 새 전략 생성</button>
        
        <div class="filter-group">
          <button 
            v-for="f in ['ALL', 'SINGLE', 'DUAL']" 
            :key="f"
            class="filter-btn"
            :class="{ active: filter === f }"
            @click="filter = f"
          >
            {{ f === 'ALL' ? '전체' : f === 'SINGLE' ? '싱글' : '듀얼' }}
          </button>
        </div>

        <div style="display: flex; flex-direction: column; gap: 8px">
          <div
            v-for="s in filteredStrategies"
            :key="s.name"
            class="strategy-item-card"
            :class="{ active: selectedStrat?.name === s.name }"
            @click="handleSelect(s)"
          >
            <div style="display: flex; justify-content: space-between; align-items: center; width: 100%">
              <span class="strat-name">{{ s.name }}</span>
              <button
                class="danger-btn"
                @click.stop="handleDelete(s.name)"
              >삭제</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Editor -->
      <div style="flex: 1; display: flex; flex-direction: column; gap: 1rem; min-width: 0">
        <template v-if="isEditing">
          <div style="display: flex; flex-direction: column; gap: 8px">
            <label style="font-size: 0.85rem; color: var(--text-muted)">전략 명칭</label>
            <input
              type="text"
              placeholder="전략 이름을 입력하세요"
              v-model="name"
              style="padding: 12px; font-size: 1.1rem; font-weight: bold; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1); color: white; border-radius: 8px"
            />
          </div>
          <div style="flex: 1; display: flex; flex-direction: column; gap: 8px">
            <label style="font-size: 0.85rem; color: var(--text-muted)">전략 구성 (DSL)</label>
            <textarea
              placeholder="[BUY] ..."
              style="flex: 1; font-family: 'Fira Code', monospace; font-size: 0.95rem; padding: 15px; background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.1); color: #00f2fe; border-radius: 8px; resize: none"
              v-model="content"
            ></textarea>
          </div>
          <div style="display: flex; gap: 12px; justify-content: flex-end; padding-top: 1rem">
            <button class="secondary" @click="isEditing = false" style="padding: 10px 20px">편집 취소</button>
            <button class="primary" @click="handleSave" style="padding: 10px 25px">전략 저장하기</button>
          </div>
        </template>
        <div v-else style="flex: 1; display: flex; align-items: center; justify-content: center; color: var(--text-muted); border: 1px dashed rgba(255,255,255,0.1); border-radius: 12px">
          <div style="text-align: center">
            <div style="font-size: 3rem; margin-bottom: 1rem">💡</div>
            <h3>전략을 선택하거나 새로 만들어주세요</h3>
            <p>전략은 [BUY], [SELL] 섹션으로 구성된 DSL 형식을 따릅니다.</p>
          </div>
        </div>
      </div>

      <!-- Help Panel -->
      <transition name="slide">
        <div v-if="showHelp" style="width: 350px; background: rgba(0,0,0,0.3); border-left: 1px solid rgba(255,255,255,0.1); padding: 1.5rem; overflow-y: auto">
          <h3 style="color: var(--primary); margin-bottom: 1.5rem; display: flex; align-items: center; gap: 8px">
            <span>📖</span> DSL 사용 가이드
          </h3>
          
          <div class="help-section">
            <h4>주요 변수 리스트</h4>
            <ul class="help-list">
              <li><code>price</code>: 현재 실시간 가격</li>
              <li><code>prev_price</code>: 이전 봉 종가</li>
              <li><code>entry_price</code>: 평균 진입 가격</li>
              <li><code>avg_price</code>: 전체 보유 비중의 평단가</li>
              <li><code>first_buy_price</code>: 해당 포지션 최초 매수가</li>
              <li><code>last_buy_price</code>: 가장 최근 추가 매수가</li>
            </ul>
          </div>

          <div class="help-section">
            <h4>기술적 지표</h4>
            <ul class="help-list">
              <li><code>ma_5</code>: 5봉 이동평균선</li>
              <li><code>ema20 / ema60</code>: 지수 이동평균 (20/60)</li>
              <li><code>macd / signal</code>: MACD 지표 및 시그널선</li>
              <li><code>hist / prev_hist</code>: MACD 히스토그램 (현재/이전)</li>
              <li><code>vwap</code>: 거래량 가중 평균 가격</li>
              <li><code>atr</code>: 평균 실제 변동 범위</li>
              <li><code>rsi</code>: 상대 강도 지수 (14)</li>
              <li><code>bb_upper / bb_lower</code>: 볼린저 밴드 상/하단</li>
            </ul>
          </div>

          <div class="help-section">
            <h4>기타 상태 및 상구</h4>
            <ul class="help-list">
              <li><code>volume / avg_volume</code>: 거래량 / 20봉 평균 거래량</li>
              <li><code>is_market_close</code>: 15:20 이후 여부 (True/False)</li>
              <li><code>is_fractal_low</code>: 프랙탈 저점 형성 (최근 3봉)</li>
              <li><code>tick_size</code>: 해당 종목의 호가 단위</li>
            </ul>
          </div>

          <div style="margin-top: 2rem; padding: 1rem; background: rgba(0, 242, 254, 0.05); border-radius: 8px; border: 1px solid rgba(0, 242, 254, 0.1)">
            <h4 style="color: var(--primary); margin-bottom: 0.5rem">💡 작성 팁</h4>
            <p style="font-size: 0.85rem; line-height: 1.5; color: var(--text-muted)">
              섹션은 <code>[BUY]</code>, <code>[BUY_STEP_N]</code>, <code>[SELL]</code>, <code>[STOP_LOSS]</code> 등으로 구분합니다. 각 단계의 <code>condition</code>에 위 변수들을 조합하여 작성하세요.
            </p>
          </div>
        </div>
      </transition>
    </div>

    <!-- Custom Alert Modal -->
    <StatusAlertModal
      :show="alertState.show"
      :type="alertState.type"
      :title="alertState.title"
      :message="alertState.message"
      @close="alertState.show = false"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { fetchStrategies, saveStrategy, deleteStrategy } from '../api';
import StatusAlertModal from './StatusAlertModal.vue';

const strategies = ref([]);
const filter = ref('ALL'); // ALL, SINGLE, DUAL
const selectedStrat = ref(null);
const name = ref('');
const content = ref('');
const isEditing = ref(false);
const showHelp = ref(false);

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

const filteredStrategies = computed(() => {
  if (filter.value === 'SINGLE') {
    return strategies.value.filter(s => s.type === 'single');
  } else if (filter.value === 'DUAL') {
    return strategies.value.filter(s => s.type === 'dual');
  }
  return strategies.value;
});

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

<style scoped>
.filter-group {
  display: flex;
  background: rgba(255, 255, 255, 0.05);
  padding: 4px;
  border-radius: 8px;
  gap: 4px;
}

.filter-btn {
  flex: 1;
  background: transparent;
  border: none;
  color: var(--text-muted);
  padding: 6px;
  font-size: 0.8rem;
  font-weight: 600;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.filter-btn:hover {
  background: rgba(255, 255, 255, 0.05);
  color: white;
}

.filter-btn.active {
  background: var(--primary);
  color: black;
}

.strategy-item-card {
  padding: 12px;
  cursor: pointer;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.05);
  border-radius: 8px;
  transition: all 0.2s;
}

.strategy-item-card:hover {
  background: rgba(255,255,255,0.08);
  border-color: rgba(255,255,255,0.1);
}

.strategy-item-card.active {
  background: rgba(0, 242, 254, 0.1);
  border-color: var(--primary);
  box-shadow: 0 0 15px rgba(0, 242, 254, 0.1);
}

.strat-name {
  font-weight: 600;
  font-size: 0.95rem;
  color: var(--text-main);
}

.danger-btn {
  background: transparent;
  border: 1px solid rgba(255, 107, 107, 0.3);
  color: #ff6b6b;
  padding: 4px 8px;
  font-size: 0.75rem;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.danger-btn:hover {
  background: rgba(255, 107, 107, 0.1);
  border-color: #ff6b6b;
}

textarea:focus, input:focus {
  outline: none;
  border-color: var(--primary) !important;
  box-shadow: 0 0 0 2px rgba(0, 242, 254, 0.1);
}

.help-section {
  margin-bottom: 1.5rem;
}

.help-section h4 {
  font-size: 0.9rem;
  color: var(--text-main);
  margin-bottom: 0.8rem;
  border-left: 3px solid var(--primary);
  padding-left: 10px;
}

.help-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.help-list li {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.help-list li code {
  color: #00f2fe;
  background: rgba(0, 242, 254, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Fira Code', monospace;
  margin-right: 6px;
}

/* Slide Transition */
.slide-enter-active, .slide-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.slide-enter-from, .slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}
</style>
