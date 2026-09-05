<template>
  <div class="import-panel glass">
    <div class="header">
      <h3>📥 데이터 가져오기 (CSV)</h3>
      <p class="subtitle">외부 파일을 업로드하여 데이터베이스에 저장합니다.</p>
    </div>

    <div class="import-form">
      <div class="form-row">
        <div class="form-group">
          <label style="display: flex; justify-content: space-between; align-items: center">
            <span>종목 선택</span>
            <div style="display: flex; align-items: center; gap: 8px">
              <small v-if="availableTickers.length > 0" style="color: var(--primary); font-size: 0.7rem">
                ({{ availableTickers.length }}개 로드됨)
              </small>
              <small v-else-if="!loadingTickers" style="color: var(--text-muted); font-size: 0.7rem">
                (로드된 종목 없음)
              </small>
              <small v-else style="color: #ff6b6b; font-size: 0.7rem">
                (로드 중...)
              </small>
              <button @click="refreshTickers" class="icon-btn" title="새로고침" style="padding: 2px; background: transparent; border: none; cursor: pointer; opacity: 0.7">
                🔄
              </button>
            </div>
          </label>
          <select v-model="selectedTicker">
            <option value="" disabled>확인할 종목을 선택하세요</option>
            <option v-for="t in availableTickers" :key="t.ticker" :value="t.ticker">{{ t.name }}</option>
          </select>
        </div>
        
        <div class="form-group">
          <label>주기 선택</label>
          <div class="tabs">
            <button 
              v-for="opt in intervalOptions" 
              :key="opt" 
              :class="{ active: selectedInterval === opt }"
              @click="selectedInterval = opt"
            >
              {{ opt }}
            </button>
          </div>
        </div>
      </div>

      <!-- Tick Specific Metadata -->
      <div class="form-row animated" v-if="selectedInterval === '틱'">
        <div class="form-group">
          <label>생성 알고리즘 (파일에 정보 없을 때)</label>
          <select v-model="algorithm">
            <option value="REALISTIC">REALISTIC (보간법)</option>
            <option value="SIMPLE">SIMPLE (균등)</option>
            <option value="PATTERNED">PATTERNED (패턴)</option>
          </select>
        </div>
        <div class="form-group">
          <label>기준 주기 (파일에 정보 없을 때)</label>
          <select v-model="baseInterval">
            <option value="1분">1분봉</option>
            <option value="5분">5분봉</option>
            <option value="일봉">일봉</option>
          </select>
        </div>
      </div>

      <div class="dropzone" @click="$refs.fileInput.click()" @dragover.prevent @drop.prevent="handleDrop" :class="{ dragging: isDragging }">
        <input type="file" ref="fileInput" @change="handleFileSelect" accept=".csv" style="display: none">
        <div v-if="!selectedFile" class="drop-msg">
          <span class="icon">📁</span>
          <p>CSV 파일을 드래그하거나 클릭하여 선택하세요.</p>
        </div>
        <div v-else class="file-info">
          <span class="icon">📄</span>
          <div class="details">
            <p class="name">{{ selectedFile.name }}</p>
            <p class="size">{{ (selectedFile.size / 1024).toFixed(1) }} KB</p>
          </div>
          <button class="remove-btn" @click.stop="clearFile">✕</button>
        </div>
      </div>

      <!-- Preview Table -->
      <div v-if="previewData.length > 0" class="preview-section animated">
        <div class="preview-header">
          <h4>미리보기 (상위 5개)</h4>
          <span class="badge">{{ totalRows }} rows detected</span>
        </div>
        <div class="preview-table-wrapper">
          <table>
            <thead>
              <tr>
                <th v-for="h in previewHeaders" :key="h">{{ h }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, idx) in previewData" :key="idx">
                <td v-for="h in previewHeaders" :key="h">{{ row[h] }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="actions">
        <button class="cancel-btn" @click="$emit('cancel')">취소</button>
        <button 
          class="import-btn" 
          @click="startImport" 
          :disabled="!isValid || loading"
        >
          <span v-if="loading">⏳ 처리 중...</span>
          <span v-else>🚀 데이터 가져오기 시작</span>
        </button>
      </div>
    </div>
  </div>

  <!-- Success Notification -->
  <div v-if="showSuccess" class="success-toast">
    ✅ {{ successCount }}건의 데이터가 저장되었습니다.
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { fetchCollectedTickers, fetchStatus } from '../api';

const props = defineProps({
  initialTicker: String
});

const emit = defineEmits(['cancel', 'imported']);

const availableTickers = ref([]);
const selectedTicker = ref(props.initialTicker || '');
const selectedInterval = ref('일봉');
const intervalOptions = ['틱', '1분', '5분', '일봉'];
const algorithm = ref('REALISTIC');
const baseInterval = ref('1분');

const selectedFile = ref(null);
const previewData = ref([]);
const previewHeaders = ref([]);
const totalRows = ref(0);
const loading = ref(false);
const loadingTickers = ref(false);
const isDragging = ref(false);
const showSuccess = ref(false);
const successCount = ref(0);

const isValid = computed(() => {
  return selectedTicker.value && selectedFile.value;
});

const handleFileSelect = (e) => {
  const file = e.target.files[0];
  if (file) processFile(file);
};

const handleDrop = (e) => {
  isDragging.value = false;
  const file = e.dataTransfer.files[0];
  if (file && file.name.endsWith('.csv')) processFile(file);
};

const pendingInferenceFile = ref(null);

const processFile = (file) => {
  selectedFile.value = file;
  
  if (availableTickers.value.length === 0) {
    pendingInferenceFile.value = file;
  } else {
    performInference(file);
  }

  const reader = new FileReader();
  reader.onload = (e) => {
    const text = e.target.result;
    const lines = text.split('\n').filter(l => l.trim());
    if (lines.length > 0) {
      const headers = lines[0].split(',').map(h => h.trim());
      previewHeaders.value = headers;
      
      const data = lines.slice(1, 6).map(line => {
        const values = line.split(',');
        const obj = {};
        headers.forEach((h, i) => obj[h] = values[i]?.trim());
        return obj;
      });
      previewData.value = data;
      totalRows.value = lines.length - 1;
    }
  };
  reader.readAsText(file);
};

const performInference = (file) => {
  if (!file) return;
  
  console.log("[Import] --- Inference started for:", file.name, "---");
  const nameBase = file.name.replace(/\.[^/.]+$/, ""); // 확장자 제거
  const nameUpper = nameBase.toUpperCase();
  const nameClean = nameBase.replace(/[^a-z0-9가-힣]/gi, ''); 
  const parts = nameBase.split(/[_ \-()]/).filter(p => p.trim()); 
  
  console.log("[Import] Parsed name parts:", parts);
  console.log("[Import] Available tickers count:", availableTickers.value.length);

  // 1. 주기 추론
  for (const part of parts) {
    const p = part.trim();
    if (intervalOptions.includes(p)) {
      selectedInterval.value = p;
      console.log("[Import] Matched interval:", p);
      break;
    }
  }
  
  // 2. 종목 추론
  if (availableTickers.value.length > 0) {
    const sortedTickers = [...availableTickers.value].sort((a, b) => b.name.length - a.name.length);
    
    // 전략 1: 이름 완전 일치 또는 포함
    let match = sortedTickers.find(t => {
      if (!t.name) return false;
      const tName = t.name.trim();
      const cleanTName = tName.replace(/[^a-z0-9가-힣]/gi, '');
      const normalizedName = tName.replace(/[^a-z0-9가-힣]/gi, '_');
      
      const found = (
        nameBase.includes(tName) || 
        nameBase.includes(normalizedName) || 
        nameClean.includes(cleanTName) ||
        parts.some(p => p === tName || p === normalizedName || p === cleanTName)
      );
      if (found) console.log("[Import] Match found by name:", tName, t.ticker);
      return found;
    });

    // 전략 2: 종목 코드 일치 (숫자 6자리 등)
    if (!match) {
      match = sortedTickers.find(t => {
        if (!t.ticker) return false;
        const tickerOnly = t.ticker.split('.')[0].toUpperCase();
        const found = (
          nameUpper.includes(tickerOnly) || 
          nameUpper.includes(t.ticker.toUpperCase()) ||
          nameClean.includes(tickerOnly) ||
          parts.some(p => p.toUpperCase() === tickerOnly)
        );
        if (found) console.log("[Import] Match found by code:", t.ticker);
        return found;
      });
    }
    
    if (match) {
      selectedTicker.value = match.ticker;
      console.log("[Import] Auto-selected ticker:", match.ticker);
    } else {
      console.log("[Import] No ticker match found in filename parts.");
      // 힌트 출력: 처음 5개 종목 이름 출력
      console.log("[Import] First 5 available tickers for reference:", availableTickers.value.slice(0, 5).map(t => t.name));
    }
  } else {
    console.log("[Import] availableTickers is empty, inference deferred.");
  }
};

const refreshTickers = async () => {
  console.log("[Import] Manually refreshing tickers...");
  loadingTickers.value = true;
  try {
    const newList = await fetchCollectedTickers();
    availableTickers.value = newList;
    console.log("[Import] Tickers refreshed, count:", newList.length);
  } finally {
    loadingTickers.value = false;
  }
};

watch(availableTickers, (newList) => {
  console.log("[Import] availableTickers watch triggered, count:", newList.length);
  if (newList.length > 0 && pendingInferenceFile.value) {
    performInference(pendingInferenceFile.value);
    pendingInferenceFile.value = null;
  }
});

const clearFile = () => {
  selectedFile.value = null;
  previewData.value = [];
  previewHeaders.value = [];
  totalRows.value = 0;
};

const startImport = async () => {
  if (!isValid.value) return;
  
  loading.value = true;
  const formData = new FormData();
  formData.append('file', selectedFile.value);
  formData.append('ticker', selectedTicker.value);
  formData.append('interval', selectedInterval.value);
  
  if (selectedInterval.value === '틱') {
    formData.append('algorithm', algorithm.value);
    formData.append('baseInterval', baseInterval.value);
  }
  
  try {
    const apiUrl = `http://${window.location.hostname}:5000/collector/import`;
    const response = await fetch(apiUrl, {
      method: 'POST',
      body: formData
    });
    const result = await response.json();
    
    if (result.status === 'SUCCESS') {
      successCount.value = result.count;
      showSuccess.value = true;
      
      // localStorage에 마지막 수집 주기 저장 (조회 탭이 아직 열리지 않은 경우를 대비)
      localStorage.setItem('lastCollectedInterval', selectedInterval.value);
      localStorage.setItem('lastCollectedTicker', selectedTicker.value);
      
      // 수집 완료 이벤트 발행 (가져온 주기 정보 포함)
      console.log('[FileImportPanel] 가져오기 완료, 주기:', selectedInterval.value);
      window.dispatchEvent(new CustomEvent('collection-complete', { 
        detail: { interval: selectedInterval.value } 
      }));
      
      setTimeout(() => {
        showSuccess.value = false;
        emit('imported', { ticker: selectedTicker.value });
      }, 3000);
    } else {
      alert(`가져오기 실패: ${result.message}`);
    }
  } catch (e) {
    console.error("Import error", e);
    alert("서버 연결에 실패했습니다.");
  } finally {
    loading.value = false;
  }
};

onMounted(async () => {
  loadingTickers.value = true;
  try {
    availableTickers.value = await fetchCollectedTickers();
  } finally {
    loadingTickers.value = false;
  }
});
</script>

<style scoped>
.import-panel {
  padding: 2.5rem;
  border-radius: 20px;
  max-width: 800px;
  margin: 0 auto;
}

.header {
  margin-bottom: 2rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  padding-bottom: 1.5rem;
}

.header h3 {
  margin: 0;
  color: var(--primary);
  font-size: 1.5rem;
}

.subtitle {
  color: var(--text-muted);
  margin: 8px 0 0 0;
  font-size: 0.95rem;
}

.import-form {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.form-row {
  display: flex;
  gap: 2rem;
}

.form-group {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group label {
  font-size: 0.85rem;
  font-weight: bold;
  color: var(--text-muted);
}

select {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: white;
  padding: 10px 14px;
  border-radius: 10px;
  outline: none;
}

.tabs {
  display: flex;
  background: rgba(255, 255, 255, 0.05);
  padding: 4px;
  border-radius: 10px;
}

.tabs button {
  flex: 1;
  padding: 8px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  border-radius: 8px;
  transition: all 0.2s;
}

.tabs button.active {
  background: var(--primary);
  color: #1e1e2d;
  font-weight: bold;
}

.dropzone {
  border: 2px dashed rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 3rem;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  background: rgba(255, 255, 255, 0.02);
}

.dropzone:hover, .dropzone.dragging {
  border-color: var(--primary);
  background: rgba(var(--primary-rgb, 0, 255, 149), 0.05);
}

.drop-msg .icon {
  font-size: 3rem;
  margin-bottom: 1rem;
  display: block;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  text-align: left;
}

.file-info .icon {
  font-size: 2.5rem;
}

.file-info .details {
  flex: 1;
}

.file-info .name {
  margin: 0;
  font-weight: bold;
  color: white;
}

.file-info .size {
  margin: 4px 0 0 0;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.remove-btn {
  background: rgba(255, 255, 255, 0.1);
  border: none;
  color: white;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  cursor: pointer;
}

.preview-section {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 12px;
  padding: 1.5rem;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.preview-header h4 {
  margin: 0;
  color: var(--text-muted);
}

.badge {
  background: rgba(255, 255, 255, 0.1);
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 0.75rem;
}

.preview-table-wrapper {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

th {
  text-align: left;
  padding: 8px;
  color: var(--primary);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

td {
  padding: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 1rem;
}

.import-btn {
  padding: 12px 24px;
  background: var(--primary);
  color: #1e1e2d;
  border: none;
  border-radius: 10px;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.2s;
}

.import-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.cancel-btn {
  padding: 12px 24px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: white;
  border-radius: 10px;
  cursor: pointer;
}

.success-toast {
  position: fixed;
  bottom: 2rem;
  right: 2rem;
  background: var(--primary);
  color: #1e1e2d;
  padding: 1rem 2rem;
  border-radius: 12px;
  font-weight: bold;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
  animation: slideIn 0.3s ease-out;
  z-index: 1000;
}

@keyframes slideIn {
  from { transform: translateX(100%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}

.animated {
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
