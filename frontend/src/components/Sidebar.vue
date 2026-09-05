<template>
  <div class="sidebar glass" style="width: 300px; height: 100vh; position: sticky; top: 0; display: flex; flex-direction: column; border-right: 1px solid rgba(255, 255, 255, 0.05)">
    <!-- Header -->
    <div style="padding: 20px; border-bottom: 1px solid rgba(255, 255, 255, 0.05)">
      <h2 style="color: var(--primary); display: flex; align-items: center; gap: 10px; margin: 0">
        <JBLogo :size="32" /> <span>JBrain</span>
      </h2>
    </div>

    <!-- Scrollable Content -->
    <div class="menu-content" style="padding: 10px 20px">
      <!-- Account Status Section (simplified) -->
      <div class="sidebar-section-title">계정 및 상태</div>
      <div class="card" style="margin-bottom: 1.5rem; padding: 12px; background: rgba(255,255,255,0.02)">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px">
          <span style="font-size: 0.8rem; color: var(--text-muted)">상태</span>
          <span :style="{ fontSize: '0.8rem', color: status === 'CONNECTED' || status?.includes('CONNECTED') ? 'var(--primary)' : 'var(--danger)' }">
            ● {{ status }}
          </span>
        </div>
        <button @click="showLoginModal = true" style="width: 100%; padding: 6px; font-size: 0.8rem">연결 설정</button>
      </div>

      <!-- Navigation System Section -->
      <div class="sidebar-section-title" style="margin-top: 2rem">네비게이션</div>
      <div class="side-nav-group">
        <div class="nav-button account" @click="emit('select-tab', 'MAIN')">
          <span class="nav-icon">👤</span>
          <span class="nav-label">계정</span>
        </div>
        <div class="nav-button" @click="emit('select-tab', 'LOG')">
          <span class="nav-icon">📜</span>
          <span class="nav-label">로그</span>
        </div>
        <div class="nav-button" @click="emit('select-tab', 'HOLDINGS')">
          <span class="nav-icon">📁</span>
          <span class="nav-label">보유종목</span>
        </div>
        <div class="nav-button" @click="emit('select-tab', 'MONITORING')">
          <span class="nav-icon">🖥️</span>
          <span class="nav-label">관심종목</span>
        </div>


        <div class="nav-button" @click="emit('select-tab', 'DATA')">
          <span class="nav-icon">📂</span>
          <span class="nav-label">데이터</span>
        </div>
        <div class="nav-button" @click="emit('select-tab', 'COLLECTOR')">
          <span class="nav-icon">📥</span>
          <span class="nav-label">수집기</span>
        </div>
        <div class="nav-button featured" @click="emit('select-tab', 'STRATEGY')">
          <span class="nav-icon">⚡</span>
          <span class="nav-label">전략</span>
        </div>
        <div class="nav-button featured" @click="emit('select-tab', 'AIPICKS')">
          <span class="nav-icon">✨</span>
          <span class="nav-label">AI 종목</span>
        </div>
        <div class="nav-button featured" @click="emit('select-tab', 'AITRADES')">
          <span class="nav-icon">🤖</span>
          <span class="nav-label">AI 매매</span>
        </div>
        <div class="nav-button featured" @click="emit('select-tab', 'AICALENDAR')">
          <span class="nav-icon">📅</span>
          <span class="nav-label">AI캘린더</span>
        </div>
        <div class="nav-button featured" @click="emit('select-tab', 'AINOTICE')">
          <span class="nav-icon">🔔</span>
          <span class="nav-label">AI Notice</span>
        </div>

        <div class="nav-button" @click="emit('select-tab', 'CLI')">
          <span class="nav-icon">🤖</span>
          <span class="nav-label">CLI 작업</span>
        </div>
        <div class="nav-button" @click="emit('select-tab', 'SETTINGS')">
          <span class="nav-icon">⚙️</span>
          <span class="nav-label">환경 설정</span>
        </div>
      </div>
    </div>



    <LoginModeModal
      v-if="showLoginModal"
      :broker="account?.broker"
      @select="handleLogin"
      @close="showLoginModal = false"
    />

    <AlertPopup 
      v-if="alertMessage"
      :message="alertMessage"
      @close="alertMessage = null"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { tryLogin } from '../api';
import LoginModeModal from './LoginModeModal.vue';
import AlertPopup from './AlertPopup.vue';
import JBLogo from './JBLogo.vue';

const props = defineProps({
  status: {
    type: String,
    default: 'OFFLINE'
  },
  account: {
    type: Object,
    default: () => ({ broker: 'KIWOOM' })
  }
});

const emit = defineEmits(['openSim', 'select-tab']);

const showLoginModal = ref(false);
const alertMessage = ref(null);

const handleLogin = async (mode = "REAL", assetType = "STOCK") => {
  const result = await tryLogin(mode, assetType);
  if (result?.status === 'TIME_ERROR') {
    alertMessage.value = result.message;
  }
  showLoginModal.value = false;
};

// 백엔드에서 비동기로 수신되는 에러 상태 감시
import { watch } from 'vue';
watch(() => props.status, (newStatus) => {
  if (newStatus && newStatus.startsWith('ERROR:')) {
    alertMessage.value = newStatus.replace('ERROR:', '').trim();
  }
});
</script>

<style scoped>
.side-nav-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 1.5rem;
}

.nav-button {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
}

.nav-button:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: var(--secondary);
  transform: translateX(4px);
  box-shadow: 0 4px 15px rgba(0, 212, 255, 0.1);
}

.nav-button:active {
  transform: scale(0.98) translateX(2px);
}

.nav-icon {
  font-size: 1.2rem;
  filter: drop-shadow(0 0 5px rgba(0, 0, 0, 0.3));
}

.nav-label {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-main);
  letter-spacing: 0.3px;
}

/* Special styling for featured buttons */
.nav-button.featured {
  background: linear-gradient(135deg, rgba(0, 212, 255, 0.1), rgba(112, 0, 255, 0.05));
  border-color: rgba(0, 212, 255, 0.2);
}

.nav-button.featured:hover {
  background: linear-gradient(135deg, rgba(0, 212, 255, 0.2), rgba(112, 0, 255, 0.1));
  border-color: var(--secondary);
}

/* Special styling for account button */
.nav-button.account {
  background: rgba(255, 255, 255, 0.02);
}

.sidebar-section-title {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--text-muted);
  letter-spacing: 1px;
  margin-bottom: 0.75rem;
  margin-top: 0.5rem;
  padding-left: 4px;
}
</style>
