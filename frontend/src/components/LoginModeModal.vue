<template>
  <Teleport to="body">
    <div
      class="modal-overlay"
      style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.75); display: flex; justify-content: center; align-items: center; z-index: 1000"
      @click.self="emit('close')"
    >
      <div class="modal-card glass" style="padding: 2rem; width: 480px; display: flex; flex-direction: column; gap: 1.5rem; border-radius: 16px; border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 25px 60px rgba(0,0,0,0.6)">

        <!-- Step Indicator -->
        <div style="display: flex; align-items: center; gap: 8px; justify-content: center; margin-bottom: 0.2rem">
          <div class="step-dot" :class="{ active: step === 1, done: step > 1 }">1</div>
          <div class="step-line" :class="{ done: step > 1 }"></div>
          <div class="step-dot" :class="{ active: step === 2 }">2</div>
        </div>

        <!-- ===== STEP 1: 자산 유형 선택 ===== -->
        <template v-if="step === 1">
          <h3 style="color: var(--primary); text-align: center; margin: 0; font-size: 1.15rem">🌐 연결 유형 선택</h3>
          <p style="text-align: center; color: var(--text-muted); font-size: 0.82rem; margin: -0.8rem 0 0">어떤 자산을 매매하시겠습니까?</p>

          <div style="display: flex; gap: 12px">
            <button
              @click="selectAsset('STOCK')"
              :class="['asset-btn', { selected: selectedAsset === 'STOCK' }]"
            >
              <span class="asset-icon">📈</span>
              <span class="asset-name">주식</span>
              <span class="asset-desc">국내/해외 주식 자동매매</span>
            </button>
            <button
              @click="selectAsset('COIN')"
              :class="['asset-btn', { selected: selectedAsset === 'COIN' }]"
            >
              <span class="asset-icon">🪙</span>
              <span class="asset-name">코인</span>
              <span class="asset-desc">바이낸스 암호화폐 자동매매</span>
            </button>
          </div>

          <!-- 코인 선택 시 바이낸스 계정 정보 표시 -->
          <div v-if="selectedAsset === 'COIN'" class="binance-info animate-slide-up">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
              <div class="binance-logo">B</div>
              <strong style="font-size: 0.95rem;">바이낸스 (Binance)</strong>
            </div>
            <div style="display: grid; grid-template-columns: auto 1fr; gap: 6px 12px; font-size: 0.8rem;">
              <span style="color: var(--text-muted);">API Key</span>
              <span :style="{ color: binanceStatus.hasKey ? 'var(--primary)' : 'var(--danger)' }">
                {{ binanceStatus.hasKey ? '✅ 설정됨' : '❌ 미설정' }}
              </span>
              <span style="color: var(--text-muted);">API Secret</span>
              <span :style="{ color: binanceStatus.hasSecret ? 'var(--primary)' : 'var(--danger)' }">
                {{ binanceStatus.hasSecret ? '✅ 설정됨' : '❌ 미설정' }}
              </span>
              <span style="color: var(--text-muted);">시장 유형</span>
              <span style="color: var(--text-main)">
                {{ binanceStatus.marketType === 'FUTURES' ? '🚀 선물 (Futures)' : '💰 현물 (Spot)' }}
              </span>
              <span style="color: var(--text-muted);">네트워크</span>
              <span style="color: var(--text-main)">
                {{ binanceStatus.isTestnet ? '🧪 테스트넷' : '🌐 메인넷' }}
              </span>
            </div>
            <p v-if="!binanceStatus.hasKey || !binanceStatus.hasSecret" style="margin: 10px 0 0; font-size: 0.75rem; color: var(--danger); line-height: 1.4;">
              ⚠️ 바이낸스 API 설정이 필요합니다. 환경 설정 → 바이낸스 설정에서 API Key/Secret을 먼저 입력해주세요.
            </p>
          </div>

          <div style="display: flex; gap: 0.6rem; margin-top: 0.4rem">
            <button
              class="primary"
              style="flex: 1; padding: 10px; font-size: 0.95rem; font-weight: bold"
              :disabled="!selectedAsset || (selectedAsset === 'COIN' && (!binanceStatus.hasKey || !binanceStatus.hasSecret))"
              @click="step = 2"
            >
              다음 →
            </button>
            <button
              style="flex: 0.4; padding: 10px; background: transparent; border: 1px solid var(--border-color); color: var(--text-muted); border-radius: 8px; cursor: pointer"
              @click="emit('close')"
            >
              취소
            </button>
          </div>
        </template>

        <!-- ===== STEP 2: 연결 모드 선택 ===== -->
        <template v-if="step === 2">
          <div style="display: flex; align-items: center; gap: 10px">
            <button class="back-btn" @click="step = 1">←</button>
            <h3 style="color: var(--primary); margin: 0; font-size: 1.15rem">
              {{ selectedAsset === 'STOCK' ? '📈 주식' : '🪙 코인' }} — 연결 모드 선택
            </h3>
          </div>
          <p style="text-align: center; color: var(--text-muted); font-size: 0.82rem; margin: -1rem 0 0">연결 방식을 선택하세요</p>

          <!-- 증권사 선택 (주식일 때만) -->
          <div v-if="selectedAsset === 'STOCK'" style="display: flex; gap: 10px">
            <button
              @click="selectedBroker = 'KIWOOM'"
              :class="['broker-btn', { selected: selectedBroker === 'KIWOOM' }]"
            >
              <span class="broker-logo kiwoom">K</span>
              <span class="broker-name">키움증권</span>
              <span class="broker-tag">OpenAPI+ · 32bit</span>
            </button>
            <button
              @click="selectedBroker = 'KOREA_INVESTMENT'"
              :class="['broker-btn', { selected: selectedBroker === 'KOREA_INVESTMENT' }]"
            >
              <span class="broker-logo kis">H</span>
              <span class="broker-name">한국투자증권</span>
              <span class="broker-tag">KIS REST · 64bit</span>
            </button>
          </div>

          <div style="display: flex; flex-direction: column; gap: 10px">
            <button @click="handleSelect('VIRTUAL')" :style="getButtonStyle('VIRTUAL')">
              🧪 가상 (Virtual)
              <div style="font-size: 0.7rem; opacity: 0.7">가상 데이터로 전략 테스트</div>
            </button>
            <button
              v-if="selectedAsset === 'STOCK'"
              @click="handleSelect('MOCK')"
              :style="getButtonStyle('MOCK')"
            >
              📉 모의투자 (Mock)
              <div style="font-size: 0.7rem; opacity: 0.7">{{ selectedBroker === 'KOREA_INVESTMENT' ? '한국투자증권 모의투자 서버 접속' : '키움증권 모의투자 서버 접속' }}</div>
            </button>
            <button
              v-if="selectedAsset === 'COIN'"
              @click="handleSelect('MOCK')"
              :style="getButtonStyle('MOCK')"
            >
              🧪 테스트넷 (Testnet)
              <div style="font-size: 0.7rem; opacity: 0.7">바이낸스 테스트넷 서버 접속</div>
            </button>
            <button @click="handleSelect('REAL')" :style="getButtonStyle('REAL')">
              💰 실시간 거래 (Real-time)
              <div style="font-size: 0.7rem; opacity: 0.7">
                {{ selectedAsset === 'COIN' 
                    ? '바이낸스 메인넷 API 접속 (주의)' 
                    : (selectedBroker === 'KOREA_INVESTMENT' ? '한국투자증권 API 접속 (64bit)' : '키움증권 계좌 접속 (32bit)')
                }}
              </div>
            </button>
          </div>

          <button @click="emit('close')" style="background: transparent; border: 1px solid var(--border-color); color: var(--text-muted); padding: 8px; border-radius: 8px; cursor: pointer">닫기</button>
        </template>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { fetchStatus, updateAccount } from '../api';

const props = defineProps({
  broker: {
    type: String,
    default: 'KIWOOM'
  }
});

const emit = defineEmits(['select', 'close']);

const step = ref(1);
const selectedAsset = ref('STOCK'); // 기본값: 주식 (기존 연결과 호환)
const selectedMode = ref('VIRTUAL');
const selectedBroker = ref(props.broker || 'KIWOOM');

// 바이낸스 설정 상태
const binanceStatus = ref({
  hasKey: false,
  hasSecret: false,
  isTestnet: false,
  marketType: 'FUTURES'
});

// 마운트 시 바이낸스 설정 상태 조회
onMounted(async () => {
  try {
    const result = await fetchStatus();
    if (result && result.account && result.account.binance_config) {
      const bnConfig = result.account.binance_config;
      const marketType = bnConfig.market_type || 'FUTURES';
      binanceStatus.value.marketType = marketType;
      binanceStatus.value.isTestnet = bnConfig.is_testnet || false;

      if (marketType === 'SPOT') {
        binanceStatus.value.hasKey = bnConfig.spot_api_key === '*****';
        binanceStatus.value.hasSecret = bnConfig.spot_api_secret === '*****';
      } else {
        binanceStatus.value.hasKey = bnConfig.futures_api_key === '*****';
        binanceStatus.value.hasSecret = bnConfig.futures_api_secret === '*****';
      }
    }
  } catch (e) {
    console.error('Failed to fetch binance status:', e);
  }
});

const selectAsset = (asset) => {
  selectedAsset.value = asset;
};

const handleSelect = async (mode) => {
  selectedMode.value = mode;
  // 주식 연결이고 증권사가 변경된 경우, 로그인 전에 서버에 반영
  if (selectedAsset.value === 'STOCK' && selectedBroker.value !== props.broker) {
    try {
      await updateAccount({ broker: selectedBroker.value });
    } catch (e) {
      console.error('Failed to update broker:', e);
    }
  }
  emit('select', mode, selectedAsset.value);
};

const getButtonStyle = (mode) => ({
  padding: '15px',
  border: selectedMode.value === mode ? '2px solid var(--primary)' : '1px solid var(--border-color)',
  background: selectedMode.value === mode ? 'rgba(0, 255, 136, 0.1)' : 'rgba(255,255,255,0.02)',
  transform: selectedMode.value === mode ? 'scale(1.02)' : 'scale(1)',
  transition: 'all 0.2s ease',
  textAlign: 'left',
  borderRadius: '10px',
  cursor: 'pointer',
  color: 'var(--text-main)'
});
</script>

<style scoped>
.modal-card {
  animation: modalSlideIn 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes modalSlideIn {
  from { opacity: 0; transform: scale(0.92) translateY(20px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

/* Step Indicator */
.step-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: var(--text-muted);
  font-size: 0.78rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
}

.step-dot.active {
  background: var(--primary);
  border-color: var(--primary);
  color: #000;
  box-shadow: 0 0 12px rgba(0, 255, 136, 0.5);
}

.step-dot.done {
  background: rgba(0, 255, 136, 0.2);
  border-color: var(--primary);
  color: var(--primary);
}

.step-line {
  flex: 1;
  height: 2px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
  max-width: 60px;
  transition: background 0.3s ease;
}

.step-line.done {
  background: var(--primary);
}

/* Asset Buttons */
.asset-btn {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 20px 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  color: var(--text-main);
}

.asset-btn:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.2);
  transform: translateY(-2px);
}

.asset-btn.selected {
  background: rgba(0, 255, 136, 0.08);
  border-color: var(--primary);
  box-shadow: 0 0 20px rgba(0, 255, 136, 0.15), inset 0 1px 0 rgba(255,255,255,0.05);
  transform: translateY(-2px);
}

.asset-icon {
  font-size: 2rem;
  line-height: 1;
}

.asset-name {
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-main);
}

.asset-desc {
  font-size: 0.72rem;
  color: var(--text-muted);
  text-align: center;
  line-height: 1.3;
}

/* Broker Buttons */
.broker-btn {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  color: var(--text-main);
}

.broker-btn:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.2);
}

.broker-btn.selected {
  background: rgba(0, 255, 136, 0.08);
  border-color: var(--primary);
  box-shadow: 0 0 12px rgba(0, 255, 136, 0.12);
}

.broker-logo {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  font-weight: 900;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.broker-logo.kiwoom {
  background: linear-gradient(135deg, #E8412E, #B22B1D);
}

.broker-logo.kis {
  background: linear-gradient(135deg, #1E4FA0, #14356E);
}

.broker-name {
  font-size: 0.85rem;
  font-weight: 700;
}

.broker-tag {
  font-size: 0.65rem;
  color: var(--text-muted);
}

/* Binance Info Card */
.binance-info {
  padding: 16px;
  background: rgba(240, 185, 11, 0.05);
  border: 1px solid rgba(240, 185, 11, 0.2);
  border-radius: 12px;
}

.binance-logo {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: linear-gradient(135deg, #F0B90B, #E8A800);
  color: #000;
  font-weight: 900;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.animate-slide-up {
  animation: slideUp 0.3s ease-out;
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Back Button */
.back-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  transition: all 0.2s;
  flex-shrink: 0;
}

.back-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--text-main);
}

button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
