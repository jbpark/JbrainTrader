<template>
  <div class="header-container" style="display: flex; gap: 1rem; width: 100%">
    <!-- 사용자명 -->
    <div class="glass account-card" style="padding: 1.5rem; flex: 1; min-width: 0; position: relative">
      <h4 style="color: var(--text-muted); font-size: 0.8rem; text-transform: uppercase">👤 사용자명</h4>
      <div v-if="editingField === 'name'" class="edit-box">
        <input 
          v-model="editValue" 
          @keyup.enter="saveEdit" 
          @blur="cancelEdit"
          ref="nameInput"
          placeholder="사용자명 입력"
        />
      </div>
      <div v-else @click="startEdit('name', account.name)" class="display-val clickable">
        {{ account.name || '로그인 필요' }}
        <span class="edit-icon">✏️</span>
      </div>
    </div>

    <!-- 계좌번호 -->
    <div class="glass account-card" style="padding: 1.5rem; flex: 1.5; min-width: 0; position: relative">
      <h4 style="color: var(--text-muted); font-size: 0.8rem; text-transform: uppercase">💳 계좌번호</h4>
      
      <div style="display: flex; align-items: center; gap: 0.8rem; margin-top: 0.5rem">
        <!-- 계좌 선택/편집 영역 -->
        <div style="flex: 1; position: relative">
          <!-- 계좌 목록이 여러 개인 경우 선택 드롭다운 표시 -->
          <div v-if="account.acc_list && account.acc_list.length > 1" class="select-box">
            <select :value="account.acc_no" @change="handleAccChange" class="acc-select">
              <option v-for="acc in account.acc_list" :key="acc" :value="acc">
                {{ formatAccNo(acc) }}
              </option>
            </select>
            <div class="acc-count" style="top: -1.8rem; right: 0">총 {{ account.acc_list.length }}개</div>
          </div>

          <!-- 그 외의 경우 (기존 편집/표시 로직) -->
          <template v-else>
            <div v-if="editingField === 'acc_no'" class="edit-box">
              <input 
                v-model="editValue" 
                @keyup.enter="saveEdit" 
                @blur="cancelEdit"
                ref="accNoInput"
                placeholder="계좌번호 입력"
              />
            </div>
            <div v-else @click="startEdit('acc_no', account.acc_no)" class="display-val clickable">
              {{ formatAccNo(account.acc_no) }}
              <span class="edit-icon">✏️</span>
            </div>
          </template>
        </div>

        <!-- 국내/해외 버튼 -->
        <div v-if="hasOverseasConnected" class="market-toggle">
          <button
            :class="['toggle-btn', { active: (account.market || 'DOMESTIC') === 'DOMESTIC' }]"
            @click="setMarket('DOMESTIC')"
          >국내</button>
          <button
            :class="['toggle-btn', { active: account.market === 'OVERSEAS' }]"
            @click="setMarket('OVERSEAS')"
          >해외</button>
        </div>
      </div>

      <!-- 계좌별 시장 고정 설정: 체크하면 계좌 변경 시 국내/해외가 자동 적용됨 -->
      <div class="market-pref" title="체크해 두면 이 계좌로 변경할 때 국내/해외가 자동으로 전환됩니다">
        <label class="pref-label">
          <input type="checkbox"
                 :checked="currentPref === 'DOMESTIC'"
                 @change="setMarketPref('DOMESTIC', $event.target.checked)" />
          국내전용
        </label>
        <label class="pref-label" v-if="hasOverseasConnected">
          <input type="checkbox"
                 :checked="currentPref === 'OVERSEAS'"
                 @change="setMarketPref('OVERSEAS', $event.target.checked)" />
          해외전용
        </label>
      </div>
    </div>

    <!-- 예수금 -->
    <div class="glass account-card" style="padding: 1.5rem; flex: 1; min-width: 0; position: relative">
      <h4 style="color: var(--text-muted); font-size: 0.8rem; text-transform: uppercase" v-html="marketIcon"></h4>
      <div v-if="editingField === 'balance'" class="edit-box">
        <input 
          v-model.number="editValue" 
          type="number"
          @keyup.enter="saveEdit" 
          @blur="cancelEdit"
          ref="balanceInput"
          placeholder="금액 입력"
        />
      </div>
      <div v-else @click="startEdit('balance', account.balance)" class="display-val clickable" style="color: var(--primary)">
        {{ currencySymbol }} {{ account.balance?.toLocaleString() || '0' }}
        <span class="edit-icon">✏️</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, computed } from 'vue';
import { updateAccount } from '../api';

const props = defineProps({
  account: {
    type: Object,
    default: () => ({ acc_no: '', name: '', balance: 0, acc_list: [], market: 'DOMESTIC', has_overseas: false })
  }
});

const emit = defineEmits(['refresh', 'update-status']);

const formatAccNo = (acc) => {
  if (!acc) return '-';
  
  // 키움 스타일 포맷팅: 0000-0000[유형]
  if (acc.length === 10) {
    const prefix = acc.substring(0, 4);
    const mid = acc.substring(4, 8);
    const suffix = acc.substring(8, 10);
    
    let type = "[위탁]"; // 기본값
    
    if (suffix === '11') {
      type = "[위탁]";
    } else if (suffix === '10') {
      // 사용자가 제공한 특정 계좌 패턴 매핑
      if (acc.startsWith('6453')) {
        type = "[연금저축]";
      } else {
        type = "[위탁종합]";
      }
    }
    
    return `${prefix}-${mid}${type}`;
  }
  return acc;
};

// 해외 주식 연결 여부 판별
const hasOverseasConnected = computed(() => {
  if (props.account.has_overseas) return true;
  if (!props.account.acc_no) return false;
  // 접미사가 10(종합)인 경우 해외 주식 가능으로 간주
  return props.account.acc_no.endsWith('10');
});

const currencySymbol = computed(() => {
  return props.account.market === 'OVERSEAS' ? '$' : '₩';
});

const marketIcon = computed(() => {
  return props.account.market === 'OVERSEAS' ? '🌎 해외 예수금' : '💰 국내 예수금';
});

// 현재 계좌의 시장 고정 설정 (없으면 null → 수동 전환 모드)
const currentPref = computed(() =>
  (props.account.acc_market_prefs || {})[props.account.acc_no] || null);

const setMarketPref = async (market, checked) => {
  try {
    // 체크 → 해당 시장으로 고정 (반대 체크는 자동 해제), 해제 → 수동 모드
    const res = await updateAccount({
      acc_market_prefs: { [props.account.acc_no]: checked ? market : null },
    });
    if (res.status === 'SUCCESS') emit('refresh');
  } catch (e) {
    alert('설정 저장 실패: ' + e.message);
  }
};

const setMarket = async (market) => {
  if (props.account.market === market) return;
  try {
    const res = await updateAccount({ market });
    if (res.status === 'SUCCESS') {
      emit('refresh');
    }
  } catch (e) {
    console.error(e);
  }
};

const editingField = ref(null);
const editValue = ref('');

const nameInput = ref(null);
const accNoInput = ref(null);
const balanceInput = ref(null);

const startEdit = (field, currentVal) => {
  editingField.value = field;
  editValue.value = currentVal;
  
  nextTick(() => {
    if (field === 'name') nameInput.value?.focus();
    if (field === 'acc_no') accNoInput.value?.focus();
    if (field === 'balance') balanceInput.value?.focus();
  });
};

const saveEdit = async () => {
  if (!editingField.value) return;
  
  const payload = {};
  payload[editingField.value] = editValue.value;
  
  try {
    const res = await updateAccount(payload);
    if (res.status === 'SUCCESS') {
      // Trigger immediate refresh in parent
      emit('refresh');
      editingField.value = null;
    } else {
      alert('업데이트 실패');
    }
  } catch (e) {
    console.error(e);
  }
};

const cancelEdit = () => {
  editingField.value = null;
};

const handleAccChange = async (event) => {
  const newAcc = event.target.value;
  try {
    const res = await updateAccount({ acc_no: newAcc });
    if (res.status === 'SUCCESS') {
      emit('refresh');
      emit('update-status');
    } else {
      alert('계좌 변경 실패');
    }
  } catch (e) {
    console.error(e);
  }
};
</script>

<style scoped>
.account-card {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.account-card:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.15);
  transform: translateY(-2px);
}

.display-val {
  font-size: 1.2rem;
  font-weight: bold;
  height: 28px;
  display: flex;
  align-items: center;
}

.display-val.clickable {
  cursor: pointer;
}

.edit-icon {
  font-size: 0.9rem;
  opacity: 0;
  margin-left: 10px;
  transition: opacity 0.2s;
}

.account-card:hover .edit-icon {
  opacity: 0.5;
}

.edit-box input {
  width: 100%;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--primary);
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 1.1rem;
  font-weight: bold;
  outline: none;
  box-shadow: 0 0 10px rgba(0, 255, 149, 0.2);
}

/* Remove number arrows */
input::-webkit-outer-spin-button,
input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.acc-select {
  width: 100%;
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: white;
  padding: 6px 10px;
  border-radius: 8px;
  font-size: 1.1rem;
  font-weight: bold;
  outline: none;
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 8px center;
  background-size: 16px;
  transition: all 0.2s ease;
}

.acc-select:hover {
  background-color: rgba(255, 255, 255, 0.1);
  border-color: var(--primary);
  box-shadow: 0 0 10px rgba(0, 255, 149, 0.1);
}

.acc-select:focus {
  border-color: var(--primary);
  box-shadow: 0 0 15px rgba(0, 255, 149, 0.2);
}

.acc-count {
  position: absolute;
  top: 1.5rem;
  right: 1.5rem;
  font-size: 0.7rem;
  color: var(--primary);
  background: rgba(0, 255, 149, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
}

/* Market Toggle Styles */
.market-toggle {
  display: flex;
  background: rgba(0, 0, 0, 0.4);
  padding: 3px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.toggle-btn {
  padding: 4px 12px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 0.85rem;
  font-weight: bold;
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.2s;
  white-space: nowrap;
}

.toggle-btn.active {
  background: var(--primary);
  color: black;
  box-shadow: 0 0 10px rgba(0, 255, 149, 0.3);
}

.toggle-btn:hover:not(.active) {
  background: rgba(255, 255, 255, 0.05);
  color: white;
}

/* 계좌별 시장 고정 설정 체크박스 */
.market-pref {
  display: flex;
  gap: 14px;
  margin-top: 0.5rem;
}

.pref-label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 0.8rem;
  color: var(--text-muted);
  cursor: pointer;
  user-select: none;
}

.pref-label input {
  accent-color: var(--primary);
  cursor: pointer;
}
</style>

