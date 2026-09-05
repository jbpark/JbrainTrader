<template>
  <div class="settings-panel animate-in" style="padding: 2.5rem; color: var(--text-main); height: 100%; overflow-y: auto; background: radial-gradient(circle at top right, rgba(0, 255, 136, 0.05), transparent 400px);">
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 2.5rem;">
      <div style="width: 40px; height: 40px; background: rgba(0, 255, 136, 0.1); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1.5rem;">⚙️</div>
      <h2 style="color: var(--primary); font-size: 1.8rem; margin: 0; font-weight: 800; letter-spacing: -0.5px;">
        환경 설정
      </h2>
    </div>

    <!-- 탭 메뉴 추가 -->
    <div class="settings-tabs" style="display: flex; gap: 10px; margin-bottom: 2rem; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 10px; flex-wrap: wrap;">
      <button 
        class="tab-btn" 
        :class="{ active: activeTab === 'BROKER' }"
        @click="activeTab = 'BROKER'"
      >
        <span style="margin-right: 8px;">🔌</span> 증권 서버 설정
      </button>
      <button 
        class="tab-btn" 
        :class="{ active: activeTab === 'BINANCE' }"
        @click="activeTab = 'BINANCE'"
      >
        <span style="margin-right: 8px;">🪙</span> 바이낸스 설정
      </button>
      <button 
        class="tab-btn" 
        :class="{ active: activeTab === 'DISCORD' }"
        @click="activeTab = 'DISCORD'"
      >
        <span style="margin-right: 8px;">💬</span> Discord 설정
      </button>
    </div>

    <!-- 탭 콘텐츠 영역 -->
    <div v-if="activeTab === 'BROKER'" class="tab-content animate-slide-up">
      <!-- 증권사 선택 카드 -->
      <div class="setting-card glass" style="margin-bottom: 2.5rem; padding: 2rem; border-radius: 20px; border: 1px solid rgba(255,255,255,0.05);">
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 1.5rem;">
          <span style="font-size: 1.2rem;">🔌</span>
          <h3 style="margin: 0; font-size: 1.2rem; font-weight: 700;">증권 서버 연결 (Broker)</h3>
        </div>
        
        <p style="color: var(--text-muted); font-size: 0.9rem; margin-bottom: 2rem; line-height: 1.6;">
          시스템이 시세를 수집하고 주문을 실행할 타겟 증권사를 선택합니다.<br/>
          선택한 증권사의 API 규격에 맞춰 엔진이 자동으로 전환됩니다.
        </p>

        <div class="broker-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px;">
          <label 
            class="broker-card pointer" 
            :class="{ active: selectedBroker === 'KIWOOM' }"
            @click="selectedBroker = 'KIWOOM'; saveSettings()"
          >
            <div class="selection-indicator"></div>
            <div style="display: flex; flex-direction: column; height: 100%; justify-content: space-between;">
              <div>
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 15px;">
                  <div class="broker-logo kiwoom">K</div>
                  <span v-if="selectedBroker === 'KIWOOM'" class="status-badge">ACTIVE</span>
                </div>
                <strong style="font-size: 1.15rem; display: block; margin-bottom: 8px;">키움증권</strong>
                <div class="tag-row">
                  <span class="tag">ActiveX</span>
                  <span class="tag">32-bit</span>
                </div>
              </div>
              <p style="margin-top: 15px; font-size: 0.8rem; color: var(--text-muted); line-height: 1.5;">
                Kiwoom Open API+ OCX를 활용하며 32비트 게이트웨이 프로세스와 연동합니다.
              </p>
            </div>
          </label>

          <label 
            class="broker-card pointer" 
            :class="{ active: selectedBroker === 'KOREA_INVESTMENT' }"
            @click="selectedBroker = 'KOREA_INVESTMENT'; saveSettings()"
          >
            <div class="selection-indicator"></div>
            <div style="display: flex; flex-direction: column; height: 100%; justify-content: space-between;">
              <div>
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 15px;">
                  <div class="broker-logo kis">H</div>
                  <span v-if="selectedBroker === 'KOREA_INVESTMENT'" class="status-badge">ACTIVE</span>
                </div>
                <strong style="font-size: 1.15rem; display: block; margin-bottom: 8px;">한국투자증권</strong>
                <div class="tag-row">
                  <span class="tag gold">REST API</span>
                  <span class="tag gold">64-bit</span>
                </div>
              </div>
              <p style="margin-top: 15px; font-size: 0.8rem; color: var(--text-muted); line-height: 1.5;">
                한국투자증권 KIS API를 사용하며 64비트 메인 엔진에서 직접 REST 통신을 수행합니다.
              </p>
            </div>
          </label>
        </div>
      </div>
      
      <!-- KIS 상세 설정 -->
      <div v-if="selectedBroker === 'KOREA_INVESTMENT'" class="setting-card glass animate-slide-up" style="padding: 2rem; border-radius: 20px; border: 1px solid rgba(255,255,255,0.05);">
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 2rem;">
          <span style="font-size: 1.2rem;">📝</span>
          <h3 style="margin: 0; font-size: 1.2rem; font-weight: 700;">한국투자증권 API 상세 설정</h3>
        </div>

        <div class="config-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 40px;">
          <div class="config-section">
            <h4 style="color: var(--primary); margin-bottom: 20px; display: flex; align-items: center; gap: 8px;">
              <span style="width: 8px; height: 8px; background: #ff4d4d; border-radius: 50%;"></span>
              실전 투자 (Real)
            </h4>
            <div class="config-form" style="display: grid; gap: 15px;">
              <div class="form-item">
                <label>계좌번호 (8~10자리 숫자)</label>
                <div style="position: relative;">
                  <input type="text" v-model="kisConfig.REAL.acc_no" placeholder="예: 12345678" class="custom-input" style="width: 100%;" />
                </div>
              </div>
              <div class="form-item">
                <label>APP KEY</label>
                <div style="position: relative;">
                  <input type="password" v-model="kisConfig.REAL.app_key" @focus="kisConfig.REAL.app_key === '********' ? kisConfig.REAL.app_key = '' : null" placeholder="App Key를 입력하세요" class="custom-input" style="width: 100%;" />
                  <span v-if="kisConfig.REAL.has_key && kisConfig.REAL.app_key === '********'" class="stored-badge">SET</span>
                </div>
              </div>
              <div class="form-item">
                <label>APP SECRET</label>
                <div style="position: relative;">
                  <input type="password" v-model="kisConfig.REAL.app_secret" @focus="kisConfig.REAL.app_secret === '********' ? kisConfig.REAL.app_secret = '' : null" placeholder="App Secret을 입력하세요" class="custom-input" style="width: 100%;" />
                  <span v-if="kisConfig.REAL.has_secret && kisConfig.REAL.app_secret === '********'" class="stored-badge">SET</span>
                </div>
              </div>
            </div>
          </div>

          <div class="config-section">
            <h4 style="color: #ffd700; margin-bottom: 20px; display: flex; align-items: center; gap: 8px;">
              <span style="width: 8px; height: 8px; background: #ffd700; border-radius: 50%;"></span>
              모의 투자 (Mock)
            </h4>
            <div class="config-form" style="display: grid; gap: 15px;">
              <div class="form-item">
                <label>계좌번호 (8~10자리 숫자)</label>
                <div style="position: relative;">
                  <input type="text" v-model="kisConfig.MOCK.acc_no" placeholder="예: 12345678" class="custom-input" style="width: 100%;" />
                </div>
              </div>
              <div class="form-item">
                <label>APP KEY</label>
                <div style="position: relative;">
                  <input type="password" v-model="kisConfig.MOCK.app_key" @focus="kisConfig.MOCK.app_key === '********' ? kisConfig.MOCK.app_key = '' : null" placeholder="App Key를 입력하세요" class="custom-input" style="width: 100%;" />
                  <span v-if="kisConfig.MOCK.has_key && kisConfig.MOCK.app_key === '********'" class="stored-badge">SET</span>
                </div>
              </div>
              <div class="form-item">
                <label>APP SECRET</label>
                <div style="position: relative;">
                  <input type="password" v-model="kisConfig.MOCK.app_secret" @focus="kisConfig.MOCK.app_secret === '********' ? kisConfig.MOCK.app_secret = '' : null" placeholder="App Secret을 입력하세요" class="custom-input" style="width: 100%;" />
                  <span v-if="kisConfig.MOCK.has_secret && kisConfig.MOCK.app_secret === '********'" class="stored-badge">SET</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <div style="margin-top: 2rem; padding-top: 1.5rem; border-top: 1px solid rgba(255,255,255,0.05); display: flex; justify-content: space-between; align-items: center;">
          <p style="margin: 0; color: var(--text-muted); font-size: 0.85rem;">
            💡 환경에 맞는 본인의 한국투자증권 실제/모의 계좌번호를 숫자로만 입력해주세요 (하이픈 제외).
          </p>
          <button class="save-btn" @click="saveDetailedSettings">
            API 정보 안전하게 저장하기
          </button>
        </div>
      </div>

      <!-- Kiwoom 상세 설정 -->
      <div v-if="selectedBroker === 'KIWOOM'" class="setting-card glass animate-slide-up" style="padding: 2rem; border-radius: 20px; border: 1px solid rgba(255,255,255,0.05);">
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 1.5rem;">
          <span style="font-size: 1.2rem;">📝</span>
          <h3 style="margin: 0; font-size: 1.2rem; font-weight: 700;">키움증권 자동로그인 설정</h3>
        </div>
        
        <div style="margin-bottom: 20px;">
          <p style="color: var(--text-muted); font-size: 0.9rem; line-height: 1.6;">
            자동 로그인을 위해 키움증권 계정 정보를 입력해주세요. 정보는 암호화되어 .env 파일에 안전하게 저장됩니다.
          </p>
        </div>

        <div class="config-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 2rem;">
          <div class="form-item">
            <label>사용자 ID</label>
            <div style="position: relative;">
              <input type="text" v-model="kiwoomConfig.user_id" @focus="kiwoomConfig.user_id === '********' ? kiwoomConfig.user_id = '' : null" placeholder="ID 입력" class="custom-input" style="width: 100%;" />
              <span v-if="kiwoomConfig.has_id && kiwoomConfig.user_id === '********'" class="stored-badge">SET</span>
            </div>
          </div>
          <div class="form-item">
            <label>비밀번호</label>
            <div style="position: relative;">
              <input type="password" v-model="kiwoomConfig.user_pw" @focus="kiwoomConfig.user_pw === '********' ? kiwoomConfig.user_pw = '' : null" placeholder="비밀번호 입력" class="custom-input" style="width: 100%;" />
              <span v-if="kiwoomConfig.has_pw && kiwoomConfig.user_pw === '********'" class="stored-badge">SET</span>
            </div>
          </div>
          <div class="form-item">
            <label>인증비밀번호</label>
            <div style="position: relative;">
              <input type="password" v-model="kiwoomConfig.cert_pw" @focus="kiwoomConfig.cert_pw === '********' ? kiwoomConfig.cert_pw = '' : null" placeholder="인증비밀번호 입력" class="custom-input" style="width: 100%;" />
              <span v-if="kiwoomConfig.has_cert && kiwoomConfig.cert_pw === '********'" class="stored-badge">SET</span>
            </div>
          </div>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 1.5rem; border-top: 1px solid rgba(255,255,255,0.05);">
          <p style="margin: 0; color: var(--text-muted); font-size: 0.85rem;">
            💡 비밀번호 저장 설정은 키움증권 로그인 창에서도 별도로 완료해야 할 수 있습니다.
          </p>
          <button class="save-btn" @click="saveKiwoomSettings">
            계정 정보 안전하게 저장하기
          </button>
        </div>
      </div>
    </div>

    <!-- 바이낸스 설정 탭 -->
    <div v-if="activeTab === 'BINANCE'" class="tab-content animate-slide-up">
      <div class="setting-card glass" style="padding: 2rem; border-radius: 20px; border: 1px solid rgba(255,255,255,0.05); margin-bottom: 1.5rem;">
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 1.5rem;">
          <div class="broker-logo binance">B</div>
          <h3 style="margin: 0; font-size: 1.2rem; font-weight: 700;">바이낸스 API 설정</h3>
        </div>

        <p style="color: var(--text-muted); font-size: 0.9rem; margin-bottom: 2rem; line-height: 1.6;">
          암호화폐 자동매매를 위한 바이낸스 API 설정입니다. <br/>
          선물(Futures)과 현물(Spot)에 각각 다른 API Key를 사용할 수 있습니다. API Key/Secret은 암호화되어 .env 파일에 안전하게 저장됩니다.
        </p>

        <!-- 선물 (Futures) API -->
        <div style="margin-bottom: 2rem;">
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 1rem;">
            <span style="font-size: 1.1rem;">🚀</span>
            <strong style="font-size: 1rem; color: var(--primary);">선물 (Futures) API Key</strong>
          </div>
          <div class="config-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px;">
            <div class="form-item" style="grid-column: span 2;">
              <label>Futures API Key</label>
              <div style="position: relative;">
                <input type="password" v-model="binanceConfig.futures_api_key" @focus="binanceConfig.futures_api_key === '********' ? binanceConfig.futures_api_key = '' : null" placeholder="선물 API Key를 입력하세요" class="custom-input" style="width: 100%;" />
                <span v-if="binanceConfig.has_futures_key && binanceConfig.futures_api_key === '********'" class="stored-badge">SET</span>
              </div>
            </div>
            <div class="form-item" style="grid-column: span 2;">
              <label>Futures API Secret</label>
              <div style="position: relative;">
                <input type="password" v-model="binanceConfig.futures_api_secret" @focus="binanceConfig.futures_api_secret === '********' ? binanceConfig.futures_api_secret = '' : null" placeholder="선물 API Secret을 입력하세요" class="custom-input" style="width: 100%;" />
                <span v-if="binanceConfig.has_futures_secret && binanceConfig.futures_api_secret === '********'" class="stored-badge">SET</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 구분선 -->
        <div style="border-top: 1px solid rgba(255,255,255,0.05); margin-bottom: 2rem;"></div>

        <!-- 현물 (Spot) API -->
        <div style="margin-bottom: 2rem;">
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 1rem;">
            <span style="font-size: 1.1rem;">💰</span>
            <strong style="font-size: 1rem; color: #F0B90B;">현물 (Spot) API Key</strong>
          </div>
          <div class="config-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px;">
            <div class="form-item" style="grid-column: span 2;">
              <label>Spot API Key</label>
              <div style="position: relative;">
                <input type="password" v-model="binanceConfig.spot_api_key" @focus="binanceConfig.spot_api_key === '********' ? binanceConfig.spot_api_key = '' : null" placeholder="현물 API Key를 입력하세요" class="custom-input" style="width: 100%;" />
                <span v-if="binanceConfig.has_spot_key && binanceConfig.spot_api_key === '********'" class="stored-badge">SET</span>
              </div>
            </div>
            <div class="form-item" style="grid-column: span 2;">
              <label>Spot API Secret</label>
              <div style="position: relative;">
                <input type="password" v-model="binanceConfig.spot_api_secret" @focus="binanceConfig.spot_api_secret === '********' ? binanceConfig.spot_api_secret = '' : null" placeholder="현물 API Secret을 입력하세요" class="custom-input" style="width: 100%;" />
                <span v-if="binanceConfig.has_spot_secret && binanceConfig.spot_api_secret === '********'" class="stored-badge">SET</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 구분선 -->
        <div style="border-top: 1px solid rgba(255,255,255,0.05); margin-bottom: 2rem;"></div>

        <!-- 공통 설정 -->
        <div class="config-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom: 2rem;">
          <div class="form-item">
            <label>활성 시장 유형</label>
            <div style="display: flex; gap: 12px; margin-top: 4px;">
              <label class="network-option" :class="{ active: binanceConfig.market_type === 'FUTURES' }" @click="binanceConfig.market_type = 'FUTURES'">
                <span style="font-size: 1rem;">🚀</span>
                <span>선물 (Futures)</span>
              </label>
              <label class="network-option" :class="{ active: binanceConfig.market_type === 'SPOT' }" @click="binanceConfig.market_type = 'SPOT'">
                <span style="font-size: 1rem;">💰</span>
                <span>현물 (Spot)</span>
              </label>
            </div>
          </div>
          <div class="form-item">
            <label>네트워크 모드</label>
            <div style="display: flex; gap: 12px; margin-top: 4px;">
              <label class="network-option" :class="{ active: !binanceConfig.is_testnet }" @click="binanceConfig.is_testnet = false">
                <span style="font-size: 1rem;">🌐</span>
                <span>메인넷</span>
              </label>
              <label class="network-option" :class="{ active: binanceConfig.is_testnet }" @click="binanceConfig.is_testnet = true">
                <span style="font-size: 1rem;">🧪</span>
                <span>테스트넷</span>
              </label>
            </div>
          </div>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 1.5rem; border-top: 1px solid rgba(255,255,255,0.05);">
          <p style="margin: 0; color: var(--text-muted); font-size: 0.85rem;">
            💡 바이낸스에서 API Key 생성 시 IP 제한 및 권한 설정을 꼭 확인하세요.
          </p>
          <button class="save-btn" @click="saveBinanceSettings" style="background: linear-gradient(135deg, #F0B90B, #E8A800); color: #000;">
            바이낸스 설정 저장하기
          </button>
        </div>
      </div>
    </div>

    <!-- Discord 설정 탭 -->
    <div v-if="activeTab === 'DISCORD'" class="tab-content animate-slide-up">
      <div class="setting-card glass" style="padding: 2rem; border-radius: 20px; border: 1px solid rgba(255,255,255,0.05);">
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 1.5rem;">
          <div style="width: 32px; height: 32px; background: #5865F2; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 1.2rem;">💬</div>
          <h3 style="margin: 0; font-size: 1.2rem; font-weight: 700;">Discord 알림 및 명령 설정</h3>
        </div>
        
        <p style="color: var(--text-muted); font-size: 0.9rem; margin-bottom: 2rem; line-height: 1.6;">
          엔진의 주요 로그를 Discord 채널로 전송하고, 명령어를 수신할 봇 설정을 입력합니다. <br/>
          민감한 봇 토큰은 암호화되어 .env 에 안전하게 보관됩니다.
        </p>

        <div class="config-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom: 2rem;">
          <div class="form-item" style="grid-column: span 2;">
            <label>Discord Bot Token</label>
            <div style="position: relative;">
              <input type="password" v-model="discordConfig.bot_token" @focus="discordConfig.bot_token === '********' ? discordConfig.bot_token = '' : null" placeholder="Bot Token을 입력하세요" class="custom-input" style="width: 100%;" />
              <span v-if="discordConfig.has_token && discordConfig.bot_token === '********'" class="stored-badge">SET</span>
            </div>
          </div>
          <div class="form-item">
            <label>서버(Guild) ID</label>
            <div style="position: relative;">
              <input type="text" v-model="discordConfig.guild_id" @focus="discordConfig.guild_id === '********' ? discordConfig.guild_id = '' : null" placeholder="Guild ID 입력" class="custom-input" style="width: 100%;" />
              <span v-if="discordConfig.has_guild && discordConfig.guild_id === '********'" class="stored-badge">SET</span>
            </div>
          </div>
          <div class="form-item">
            <label>Log 채널 ID</label>
            <div style="position: relative;">
              <input type="text" v-model="discordConfig.log_channel_id" @focus="discordConfig.log_channel_id === '********' ? discordConfig.log_channel_id = '' : null" placeholder="Log Channel ID 입력" class="custom-input" style="width: 100%;" />
              <span v-if="discordConfig.has_log_ch && discordConfig.log_channel_id === '********'" class="stored-badge">SET</span>
            </div>
          </div>
          <div class="form-item">
            <label>Command 채널 ID</label>
            <div style="position: relative;">
              <input type="text" v-model="discordConfig.cmd_channel_id" @focus="discordConfig.cmd_channel_id === '********' ? discordConfig.cmd_channel_id = '' : null" placeholder="Command Channel ID 입력" class="custom-input" style="width: 100%;" />
              <span v-if="discordConfig.has_cmd_ch && discordConfig.cmd_channel_id === '********'" class="stored-badge">SET</span>
            </div>
          </div>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 1.5rem; border-top: 1px solid rgba(255,255,255,0.05);">
          <p style="margin: 0; color: var(--text-muted); font-size: 0.85rem;">
            💡 각 ID는 Discord 개발자 모드 활성화 후 대상 우클릭 → ID 복사로 획득 가능합니다.
          </p>
          <button class="save-btn" @click="saveDiscordSettings" style="background: #5865F2; color: white;">
            Discord 설정 저장하기
          </button>
        </div>
      </div>
    </div>

    <Transition name="fade">
      <div v-if="saveMessage" class="save-toast">
        <span style="margin-right: 8px;">✅</span> {{ saveMessage }}
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue';
import { updateAccount, fetchStatus } from '../api';

const selectedBroker = ref('KIWOOM');
const saveMessage = ref('');
const activeTab = ref('BROKER');

const kisConfig = reactive({
  REAL: { app_key: '', app_secret: '', acc_no: '', has_key: false, has_secret: false },
  MOCK: { app_key: '', app_secret: '', acc_no: '', has_key: false, has_secret: false }
});

const kiwoomConfig = reactive({
  user_id: '',
  user_pw: '',
  cert_pw: '',
  has_id: false,
  has_pw: false,
  has_cert: false
});

const discordConfig = reactive({
  bot_token: '',
  guild_id: '',
  log_channel_id: '',
  cmd_channel_id: '',
  has_token: false,
  has_guild: false,
  has_log_ch: false,
  has_cmd_ch: false
});

const binanceConfig = reactive({
  futures_api_key: '',
  futures_api_secret: '',
  spot_api_key: '',
  spot_api_secret: '',
  is_testnet: false,
  market_type: 'FUTURES',
  has_futures_key: false,
  has_futures_secret: false,
  has_spot_key: false,
  has_spot_secret: false
});

onMounted(async () => {
  const result = await fetchStatus();
  if (result && result.account) {
    if (result.account.broker) {
      selectedBroker.value = result.account.broker;
    }
    
    // 엔진에서 내려준 마스킹된 설정 확인 또는 .env 기반 설정 로드
    // (backend main.py에서 각 모드별 설정을 내려주도록 수정됨)
    const modes = ['REAL', 'MOCK'];
    modes.forEach(m => {
      // account_config.json에 저장된 마스킹된 데이터 또는 status에서 온 데이터
      const m_config = result.account.kis_config ? result.account.kis_config[m] : null;
      if (m_config) {
        if (m_config.app_key === '*****') { kisConfig[m].app_key = '********'; kisConfig[m].has_key = true; }
        if (m_config.app_secret === '*****') { kisConfig[m].app_secret = '********'; kisConfig[m].has_secret = true; }
        if (m_config.acc_no) { kisConfig[m].acc_no = m_config.acc_no; }
      }
    });

    // Kiwoom 설정 로드
    const kw_config = result.account.kiwoom_config;
    if (kw_config) {
      if (kw_config.user_id === '*****') { kiwoomConfig.user_id = '********'; kiwoomConfig.has_id = true; }
      if (kw_config.user_pw === '*****') { kiwoomConfig.user_pw = '********'; kiwoomConfig.has_pw = true; }
      if (kw_config.cert_pw === '*****') { kiwoomConfig.cert_pw = '********'; kiwoomConfig.has_cert = true; }
    }

    // Discord 설정 로드
    const dc_config = result.account.discord_config;
    if (dc_config) {
      if (dc_config.bot_token === '*****') { discordConfig.bot_token = '********'; discordConfig.has_token = true; }
      if (dc_config.guild_id === '*****') { discordConfig.guild_id = '********'; discordConfig.has_guild = true; }
      if (dc_config.log_channel_id === '*****') { discordConfig.log_channel_id = '********'; discordConfig.has_log_ch = true; }
      if (dc_config.cmd_channel_id === '*****') { discordConfig.cmd_channel_id = '********'; discordConfig.has_cmd_ch = true; }
    }

    // Binance 설정 로드
    const bn_config = result.account.binance_config;
    if (bn_config) {
      if (bn_config.futures_api_key === '*****') { binanceConfig.futures_api_key = '********'; binanceConfig.has_futures_key = true; }
      if (bn_config.futures_api_secret === '*****') { binanceConfig.futures_api_secret = '********'; binanceConfig.has_futures_secret = true; }
      if (bn_config.spot_api_key === '*****') { binanceConfig.spot_api_key = '********'; binanceConfig.has_spot_key = true; }
      if (bn_config.spot_api_secret === '*****') { binanceConfig.spot_api_secret = '********'; binanceConfig.has_spot_secret = true; }
      binanceConfig.is_testnet = bn_config.is_testnet || false;
      binanceConfig.market_type = bn_config.market_type || 'FUTURES';
    }
  }
});

const saveSettings = async () => {
  try {
    await updateAccount({ broker: selectedBroker.value });
    showToast('증권사 설정이 변경되었습니다.');
  } catch(e) {
    console.error("Setting save error", e);
    showToast('설정 저장 중 오류가 발생했습니다.');
  }
};

const saveDetailedSettings = async () => {
  try {
    // 값이 변경된 대상을 선별하여 전송
    const payload = {
      broker: selectedBroker.value,
      kis_config: {
        REAL: {},
        MOCK: {}
      }
    };

    let hasChange = false;
    ['REAL', 'MOCK'].forEach(m => {
      if (kisConfig[m].app_key && kisConfig[m].app_key !== '********') {
        payload.kis_config[m].app_key = kisConfig[m].app_key;
        hasChange = true;
      }
      if (kisConfig[m].app_secret && kisConfig[m].app_secret !== '********') {
        payload.kis_config[m].app_secret = kisConfig[m].app_secret;
        hasChange = true;
      }
      if (kisConfig[m].acc_no) {
        payload.kis_config[m].acc_no = kisConfig[m].acc_no;
        hasChange = true;
      }
    });

    if (!hasChange) {
       showToast('변경사항이 없습니다.');
       return;
    }

    await updateAccount(payload);
    showToast('API 설정이 암호화되어 .env에 저장되었습니다.');
    
    // 입력창 마스킹 처리 (저장 후 상태 유지 표시)
    ['REAL', 'MOCK'].forEach(m => {
       if (payload.kis_config[m].app_key) { kisConfig[m].app_key = '********'; kisConfig[m].has_key = true; }
       if (payload.kis_config[m].app_secret) { kisConfig[m].app_secret = '********'; kisConfig[m].has_secret = true; }
    });
  } catch(e) {
    console.error("Detailed setting save error", e);
    showToast('상세 설정 저장 실패');
  }
};

const saveKiwoomSettings = async () => {
  try {
    const payload = {
      broker: 'KIWOOM',
      kiwoom_config: {}
    };

    let hasChange = false;
    if (kiwoomConfig.user_id && kiwoomConfig.user_id !== '********') {
      payload.kiwoom_config.user_id = kiwoomConfig.user_id;
      hasChange = true;
    }
    if (kiwoomConfig.user_pw && kiwoomConfig.user_pw !== '********') {
      payload.kiwoom_config.user_pw = kiwoomConfig.user_pw;
      hasChange = true;
    }
    if (kiwoomConfig.cert_pw && kiwoomConfig.cert_pw !== '********') {
      payload.kiwoom_config.cert_pw = kiwoomConfig.cert_pw;
      hasChange = true;
    }

    if (!hasChange) {
      showToast('변경사항이 없습니다.');
      return;
    }

    await updateAccount(payload);
    showToast('키움 계정 정보가 암호화되어 저장되었습니다.');

    // 입력창 마스킹 처리
    if (payload.kiwoom_config.user_id) { kiwoomConfig.user_id = '********'; kiwoomConfig.has_id = true; }
    if (payload.kiwoom_config.user_pw) { kiwoomConfig.user_pw = '********'; kiwoomConfig.has_pw = true; }
    if (payload.kiwoom_config.cert_pw) { kiwoomConfig.cert_pw = '********'; kiwoomConfig.has_cert = true; }
  } catch(e) {
    console.error("Kiwoom setting save error", e);
    showToast('키움 설정 저장 실패');
  }
};

const saveDiscordSettings = async () => {
  try {
    const payload = {
      discord_config: {}
    };

    let hasChange = false;
    if (discordConfig.bot_token && discordConfig.bot_token !== '********') {
      payload.discord_config.bot_token = discordConfig.bot_token;
      hasChange = true;
    }
    if (discordConfig.guild_id && discordConfig.guild_id !== '********') {
      payload.discord_config.guild_id = discordConfig.guild_id;
      hasChange = true;
    }
    if (discordConfig.log_channel_id && discordConfig.log_channel_id !== '********') {
      payload.discord_config.log_channel_id = discordConfig.log_channel_id;
      hasChange = true;
    }
    if (discordConfig.cmd_channel_id && discordConfig.cmd_channel_id !== '********') {
      payload.discord_config.cmd_channel_id = discordConfig.cmd_channel_id;
      hasChange = true;
    }

    if (!hasChange) {
      showToast('변경사항이 없습니다.');
      return;
    }

    await updateAccount(payload);
    showToast('Discord 설정이 암호화되어 저장되었습니다.');

    // 마스킹 상태 업데이트
    if (payload.discord_config.bot_token) { discordConfig.bot_token = '********'; discordConfig.has_token = true; }
    if (payload.discord_config.guild_id) { discordConfig.guild_id = '********'; discordConfig.has_guild = true; }
    if (payload.discord_config.log_channel_id) { discordConfig.log_channel_id = '********'; discordConfig.has_log_ch = true; }
    if (payload.discord_config.cmd_channel_id) { discordConfig.cmd_channel_id = '********'; discordConfig.has_cmd_ch = true; }
  } catch(e) {
    console.error("Discord setting save error", e);
    showToast('Discord 설정 저장 실패');
  }
};

const saveBinanceSettings = async () => {
  try {
    const payload = {
      binance_config: {}
    };

    if (binanceConfig.futures_api_key && binanceConfig.futures_api_key !== '********') {
      payload.binance_config.futures_api_key = binanceConfig.futures_api_key;
    }
    if (binanceConfig.futures_api_secret && binanceConfig.futures_api_secret !== '********') {
      payload.binance_config.futures_api_secret = binanceConfig.futures_api_secret;
    }
    if (binanceConfig.spot_api_key && binanceConfig.spot_api_key !== '********') {
      payload.binance_config.spot_api_key = binanceConfig.spot_api_key;
    }
    if (binanceConfig.spot_api_secret && binanceConfig.spot_api_secret !== '********') {
      payload.binance_config.spot_api_secret = binanceConfig.spot_api_secret;
    }
    payload.binance_config.is_testnet = binanceConfig.is_testnet;
    payload.binance_config.market_type = binanceConfig.market_type;

    await updateAccount(payload);
    showToast('바이낸스 API 설정이 암호화되어 저장되었습니다.');

    // 마스킹 상태 업데이트
    if (payload.binance_config.futures_api_key) { binanceConfig.futures_api_key = '********'; binanceConfig.has_futures_key = true; }
    if (payload.binance_config.futures_api_secret) { binanceConfig.futures_api_secret = '********'; binanceConfig.has_futures_secret = true; }
    if (payload.binance_config.spot_api_key) { binanceConfig.spot_api_key = '********'; binanceConfig.has_spot_key = true; }
    if (payload.binance_config.spot_api_secret) { binanceConfig.spot_api_secret = '********'; binanceConfig.has_spot_secret = true; }
  } catch(e) {
    console.error('Binance setting save error', e);
    showToast('바이낸스 설정 저장 실패');
  }
};

const showToast = (msg) => {
  saveMessage.value = msg;
  setTimeout(() => {
    saveMessage.value = '';
  }, 3000);
};
</script>

<style scoped>
.broker-card {
  padding: 1.5rem;
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,0.05);
  background: rgba(255,255,255,0.02);
  transition: all 0.4s cubic-bezier(0.165, 0.84, 0.44, 1);
  position: relative;
  overflow: hidden;
  min-height: 180px;
}

.broker-card:hover {
  background: rgba(255,255,255,0.05);
  border-color: rgba(255,255,255,0.15);
  transform: translateY(-5px);
  box-shadow: 0 10px 30px rgba(0,0,0,0.3);
}

.broker-card.active {
  background: rgba(0, 255, 136, 0.03);
  border: 2px solid var(--primary);
  box-shadow: 0 0 25px rgba(0, 255, 136, 0.1);
}

.selection-indicator {
  position: absolute;
  top: 0;
  right: 0;
  width: 0;
  height: 0;
  border-style: solid;
  border-width: 0 40px 40px 0;
  border-color: transparent var(--primary) transparent transparent;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.broker-card.active .selection-indicator {
  opacity: 1;
}

.broker-logo {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 900;
  font-size: 1.2rem;
  color: white;
}

.kiwoom { background: linear-gradient(135deg, #e61919, #800000); }
.kis { background: linear-gradient(135deg, #0055ff, #002266); }
.binance { background: linear-gradient(135deg, #F0B90B, #E8A800); color: #000; }

.network-option {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 16px;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.02);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.25s ease;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-muted);
}

.network-option:hover {
  background: rgba(255,255,255,0.06);
  border-color: rgba(255,255,255,0.15);
}

.network-option.active {
  background: rgba(240, 185, 11, 0.1);
  border-color: #F0B90B;
  color: #F0B90B;
  box-shadow: 0 0 10px rgba(240, 185, 11, 0.15);
}

.status-badge {
  font-size: 0.65rem;
  font-weight: 800;
  padding: 3px 8px;
  border-radius: 20px;
  background: var(--primary);
  color: #000;
  letter-spacing: 0.5px;
}

.tag-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.tag {
  font-size: 0.65rem;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(255,255,255,0.05);
  color: var(--text-muted);
  border: 1px solid rgba(255,255,255,0.05);
}

.tag.gold {
  color: #ffd700;
  border-color: rgba(255, 215, 0, 0.2);
  background: rgba(255, 215, 0, 0.05);
}

.save-toast {
  position: fixed;
  bottom: 30px;
  right: 30px;
  background: var(--primary);
  color: #010c14;
  padding: 12px 24px;
  border-radius: 12px;
  font-weight: 700;
  box-shadow: 0 10px 30px rgba(0, 255, 136, 0.3);
  z-index: 1000;
  display: flex;
  align-items: center;
}

.fade-enter-active, .fade-leave-active { transition: all 0.5s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; transform: translateY(20px); }

.animate-in {
  animation: fadeIn 0.6s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.animate-slide-up {
  animation: slideUp 0.5s ease-out;
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

.tab-btn {
  padding: 10px 20px;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-muted);
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s ease;
  font-size: 0.95rem;
  display: flex;
  align-items: center;
}

.tab-btn:hover {
  color: var(--text-main);
  background: rgba(255,255,255,0.03);
}

.tab-btn.active {
  color: var(--primary);
  border-bottom-color: var(--primary);
  background: rgba(0, 255, 136, 0.05);
  border-radius: 8px 8px 0 0;
}

.config-form .form-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.config-form label {
  font-size: 0.75rem;
  font-weight: 800;
  color: var(--primary);
  letter-spacing: 1px;
}

.custom-input {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 12px 16px;
  border-radius: 12px;
  color: white;
  outline: none;
  transition: all 0.3s ease;
  font-family: inherit;
}

.custom-input:focus {
  border-color: var(--primary);
  background: rgba(0, 255, 136, 0.05);
  box-shadow: 0 0 15px rgba(0, 255, 136, 0.1);
}

.save-btn {
  background: var(--primary);
  color: #010c14;
  border: none;
  padding: 14px 28px;
  border-radius: 12px;
  font-weight: 800;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.save-btn:hover {
  transform: scale(1.05);
  box-shadow: 0 5px 20px rgba(0, 255, 136, 0.4);
}

.save-btn:active {
  transform: scale(0.95);
}

.stored-badge {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 0.6rem;
  font-weight: 800;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--primary);
  color: #000;
  pointer-events: none;
  opacity: 0.8;
  letter-spacing: 0.5px;
}

.pointer { cursor: pointer; }
</style>
