<template>
  <!-- 도우미 꺼짐: 복원용 미니 버튼 -->
  <button
    v-if="current === 'none'"
    class="mascot-restore"
    title="도우미 켜기"
    @click="showPicker = true"
  >🐾</button>

  <div
    v-else
    class="mascot"
    :class="{ 'on-chat': chatOpen }"
    :style="{ right: pos.right + 'px', bottom: pos.bottom + 'px' }"
    @mousedown="onDragStart"
    @click="onClick"
  >
    <div v-show="bubbleText && !chatOpen" class="mascot-bubble">{{ bubbleText }}</div>
    <div class="mascot-emoji">{{ emoji }}</div>
    <button class="mascot-config" title="도우미 변경" @click.stop="showPicker = !showPicker">⚙</button>
  </div>

  <!-- 도우미 선택 팝업 -->
  <div v-if="showPicker" class="mascot-picker" :style="pickerStyle">
    <div class="picker-title">도우미 선택</div>
    <div
      v-for="(def, id) in MASCOTS"
      :key="id"
      class="picker-item"
      :class="{ selected: current === id }"
      @click="select(id)"
    >
      <span>{{ def.icon }} {{ def.label }}</span>
      <span v-if="current === id">✔</span>
    </div>
    <div class="picker-item" :class="{ selected: current === 'none' }" @click="select('none')">
      <span>🚫 끄기</span>
      <span v-if="current === 'none'">✔</span>
    </div>
  </div>

  <!-- 도우미 채팅창 -->
  <div v-if="chatOpen" class="chat-win">
    <div class="chat-header">
      <span class="chat-title">{{ def().icon }} {{ def().label }} 도우미</span>
      <div class="chat-header-btns">
        <button class="chat-hbtn" title="대화 지우기" @click="clearChat">🗑</button>
        <button class="chat-hbtn" title="닫기" @click="toggleChat">×</button>
      </div>
    </div>

    <div ref="msgsEl" class="chat-msgs">
      <div
        v-for="(m, i) in chatMsgs"
        :key="i"
        :class="m.role === 'user' ? 'chat-msg-user' : 'chat-msg-bot'"
      >
        <div :class="m.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-bot'">{{ m.text }}</div>
      </div>
    </div>

    <div class="chat-input-row">
      <input
        ref="inputEl"
        v-model="chatInput"
        class="chat-input"
        placeholder="무엇이든 물어보세요..."
        :disabled="streaming"
        @keydown.enter="sendChat"
      />
      <button class="chat-send" :disabled="streaming || !chatInput.trim()" @click="sendChat">
        {{ streaming ? '…' : '전송' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue';
import { fetchCliTasks, fetchChatHistory, saveChatMessage, clearChatHistory, streamChat } from '../api';

const MASCOTS = {
  octopus: {
    label: '문어', icon: '🐙',
    wander: ['🐙', '🐙✨', '🐙💡', '🐙🚩', '🐙🎉'],
    idleMsgs: [
      '클릭하면 채팅창이 열려요! 💬',
      '오늘 시장은 어떤가요? 📈',
      '✨ CLI 작업이 기록되면 알려드릴게요!',
      '전략 점검은 하셨나요?',
      '오늘도 열심히 일하고 있어요!',
      '손절 규칙, 잊지 마세요!',
    ],
  },
  penguin: {
    label: '펭귄', icon: '🐧',
    wander: ['🐧', '❄️🐧', '🐧✨', '💙🐧', '🐧🎵'],
    idleMsgs: [
      '뿅! 클릭하면 대화할 수 있어요! 🐧',
      '❄️ 무엇이든 도와드릴게요!',
      '펭귄이 시세를 지켜보고 있어요~',
      '꽥꽥! CLI 작업 탭을 확인해보세요.',
      '빙글빙글 돌며 기다리고 있어요!',
    ],
  },
  cat: {
    label: '고양이', icon: '🐱',
    wander: ['🐱', '😸', '😺', '😻', '🐱✨'],
    idleMsgs: [
      '냐옹~ 클릭하면 채팅할 수 있어요 🐱',
      '😸 수익 나면 츄르 주세요!',
      '고양이 도우미가 도착했어요~',
      '꾹꾹이 중... 잠깐만요.',
      '냐! 무엇이든 물어보세요.',
    ],
  },
  dog: {
    label: '강아지', icon: '🐶',
    wander: ['🐶', '🐕', '🦮', '🐩', '🐶💫'],
    idleMsgs: [
      '멍멍! 클릭하면 대화 시작! 🐶',
      '🦴 오늘의 매매 준비 완료!',
      '강아지 도우미예요, 왈왈~',
      '꼬리 흔드는 중... 도움이 필요하신가요?',
      '멍! 무엇이든 물어보세요.',
    ],
  },
};

const GREETING = '안녕하세요! 단타 매매 시스템 도우미예요. 시스템 사용법을 무엇이든 물어보세요. 💬';
const STORAGE_KEY = 'jbrain_helper';

const current = ref(localStorage.getItem(STORAGE_KEY) || 'octopus');
if (current.value !== 'none' && !MASCOTS[current.value]) current.value = 'octopus';

const emoji = ref('🐙');
const bubbleText = ref('');
const showPicker = ref(false);
const pos = ref({ right: 22, bottom: 22 });

// 채팅 상태
const chatOpen = ref(false);
const chatMsgs = ref([]);
const chatInput = ref('');
const streaming = ref(false);
const msgsEl = ref(null);
const inputEl = ref(null);
let historyLoaded = false;
let savedPos = null;

const pickerStyle = computed(() => ({
  right: (pos.value.right + (current.value === 'none' ? 0 : 70)) + 'px',
  bottom: (pos.value.bottom + 10) + 'px',
}));

let wanderTimer = null;
let idleTimer = null;
let bubbleTimer = null;
let cliPollTimer = null;
let wanderResetTimer = null;
let lastSeenTaskId = null;
let doneNotified = false;
let dragging = false;
let dragMoved = false;
let dragStart = { x: 0, y: 0, right: 0, bottom: 0 };

const def = () => MASCOTS[current.value] || MASCOTS.octopus;

const showBubble = (text) => {
  bubbleText.value = text;
  clearTimeout(bubbleTimer);
  bubbleTimer = setTimeout(() => { bubbleText.value = ''; }, 3500);
};

const wander = () => {
  if (dragging || chatOpen.value || current.value === 'none') return;
  const vw = window.innerWidth, vh = window.innerHeight;
  const margin = 16, size = 64;
  pos.value = {
    right: Math.max(margin, Math.min(vw - size - margin, pos.value.right + (Math.random() - 0.5) * 120)),
    bottom: Math.max(margin, Math.min(vh - size - margin, pos.value.bottom + (Math.random() - 0.5) * 80)),
  };
  const w = def().wander;
  emoji.value = w[Math.floor(Math.random() * w.length)];
  clearTimeout(wanderResetTimer);
  wanderResetTimer = setTimeout(() => { if (current.value !== 'none') emoji.value = def().icon; }, 4000);
  scheduleWander();
};

const scheduleWander = () => {
  clearTimeout(wanderTimer);
  wanderTimer = setTimeout(wander, 6000 + Math.random() * 6000);
};

const idleTalk = () => {
  if (!dragging && !chatOpen.value && current.value !== 'none') {
    const msgs = def().idleMsgs;
    showBubble(msgs[Math.floor(Math.random() * msgs.length)]);
  }
  clearTimeout(idleTimer);
  idleTimer = setTimeout(idleTalk, 18000 + Math.random() * 12000);
};

// CLI 작업 완료 감지 → 말풍선 알림
const pollCliTasks = async () => {
  try {
    const tasks = await fetchCliTasks(1);
    if (Array.isArray(tasks) && tasks.length > 0) {
      const latest = tasks[0];
      if (lastSeenTaskId === null) {
        lastSeenTaskId = latest.id;
        doneNotified = latest.status === 'done';
      } else if (latest.id > lastSeenTaskId || (latest.id === lastSeenTaskId && latest.status === 'done' && !doneNotified)) {
        if (latest.status === 'done') {
          const who = latest.trigger_type === 'antigravity_cli' ? '🚀 Antigravity' : '🤖 Claude';
          showBubble(`${who} 작업 완료: ${latest.title}`);
          doneNotified = true;
        }
        if (latest.id > lastSeenTaskId) {
          lastSeenTaskId = latest.id;
          doneNotified = latest.status === 'done';
        }
      }
    }
  } catch (e) { /* 백엔드 미기동 시 무시 */ }
};

// ── 채팅 ──────────────────────────────────────────────
const scrollMsgs = () => {
  nextTick(() => { if (msgsEl.value) msgsEl.value.scrollTop = msgsEl.value.scrollHeight; });
};

const toggleChat = async () => {
  chatOpen.value = !chatOpen.value;
  if (chatOpen.value) {
    bubbleText.value = '';
    clearTimeout(wanderTimer);
    // 마스코트를 채팅창 위로 이동
    savedPos = { ...pos.value };
    pos.value = { right: 320, bottom: 500 };
    if (!historyLoaded) {
      historyLoaded = true;
      try {
        const history = await fetchChatHistory();
        if (Array.isArray(history) && history.length > 0) {
          chatMsgs.value = history.map((h) => ({ role: h.role, text: h.text }));
        }
      } catch (e) { /* 무시 */ }
    }
    if (chatMsgs.value.length === 0) {
      chatMsgs.value.push({ role: 'assistant', text: GREETING });
    }
    scrollMsgs();
    nextTick(() => { if (inputEl.value) inputEl.value.focus(); });
  } else {
    if (savedPos) { pos.value = savedPos; savedPos = null; }
    scheduleWander();
  }
};

const sendChat = async () => {
  const msg = chatInput.value.trim();
  if (!msg || streaming.value) return;
  chatInput.value = '';
  chatMsgs.value.push({ role: 'user', text: msg });
  saveChatMessage('user', msg);
  scrollMsgs();

  // 직전 대화 6개를 컨텍스트로 전달 (인사말 제외)
  const history = chatMsgs.value
    .filter((m) => m.text !== GREETING)
    .slice(0, -1)
    .slice(-6)
    .map((m) => ({ role: m.role, text: m.text }));

  const bot = { role: 'assistant', text: '…' };
  chatMsgs.value.push(bot);
  streaming.value = true;
  let fullText = '';

  try {
    await streamChat(msg, history, (event, data) => {
      if (event === 'delta') {
        fullText += data.text || '';
        bot.text = fullText;
      } else if (event === 'replace') {
        fullText = data.text || fullText;
        bot.text = fullText;
      } else if (event === 'done') {
        if (data.text) { fullText = data.text; bot.text = fullText; }
      } else if (event === 'error') {
        bot.text = '⚠️ ' + (data.error || '응답 실패');
      }
      scrollMsgs();
    });
    if (fullText) saveChatMessage('assistant', fullText);
  } catch (e) {
    bot.text = '⚠️ 백엔드에 연결할 수 없습니다. 서버(포트 5000)가 실행 중인지 확인하세요.';
  } finally {
    streaming.value = false;
    scrollMsgs();
    nextTick(() => { if (inputEl.value) inputEl.value.focus(); });
  }
};

const clearChat = async () => {
  await clearChatHistory();
  chatMsgs.value = [{ role: 'assistant', text: GREETING }];
};

// ── 마스코트 조작 ─────────────────────────────────────
const onClick = () => {
  if (dragMoved) { dragMoved = false; return; }
  toggleChat();
};

const onDragStart = (e) => {
  if (chatOpen.value) return;
  dragging = true;
  dragMoved = false;
  dragStart = { x: e.clientX, y: e.clientY, right: pos.value.right, bottom: pos.value.bottom };
  window.addEventListener('mousemove', onDragMove);
  window.addEventListener('mouseup', onDragEnd);
};

const onDragMove = (e) => {
  const dx = e.clientX - dragStart.x;
  const dy = e.clientY - dragStart.y;
  if (Math.abs(dx) + Math.abs(dy) > 4) dragMoved = true;
  pos.value = {
    right: Math.max(4, dragStart.right - dx),
    bottom: Math.max(4, dragStart.bottom - dy),
  };
};

const onDragEnd = () => {
  dragging = false;
  window.removeEventListener('mousemove', onDragMove);
  window.removeEventListener('mouseup', onDragEnd);
};

const select = (id) => {
  current.value = id;
  localStorage.setItem(STORAGE_KEY, id);
  showPicker.value = false;
  if (id === 'none') {
    chatOpen.value = false;
  } else {
    emoji.value = MASCOTS[id].icon;
    if (!chatOpen.value) {
      showBubble(MASCOTS[id].idleMsgs[0]);
      scheduleWander();
    }
  }
};

onMounted(() => {
  if (current.value !== 'none') {
    emoji.value = def().icon;
    scheduleWander();
  }
  idleTimer = setTimeout(idleTalk, 6000);
  pollCliTasks();
  cliPollTimer = setInterval(pollCliTasks, 12000);
});

onUnmounted(() => {
  clearTimeout(wanderTimer);
  clearTimeout(idleTimer);
  clearTimeout(bubbleTimer);
  clearTimeout(wanderResetTimer);
  clearInterval(cliPollTimer);
  window.removeEventListener('mousemove', onDragMove);
  window.removeEventListener('mouseup', onDragEnd);
});
</script>

<style scoped>
.mascot {
  position: fixed;
  z-index: 9000;
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: grab;
  user-select: none;
  transition: right 1.2s cubic-bezier(.16, 1, .3, 1), bottom 1.2s cubic-bezier(.16, 1, .3, 1);
}
.mascot:active {
  cursor: grabbing;
}
.mascot.on-chat {
  cursor: pointer;
  transition: right .5s cubic-bezier(.34, 1.56, .64, 1), bottom .5s cubic-bezier(.34, 1.56, .64, 1);
}
.mascot-emoji {
  font-size: 44px;
  line-height: 1;
  filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.4));
  animation: mascot-bob 2.4s ease-in-out infinite;
}
@keyframes mascot-bob {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-6px); }
}
.mascot-bubble {
  position: absolute;
  bottom: 70px;
  right: 0;
  max-width: 240px;
  background: var(--bg-dark, #0d1117);
  border: 1px solid var(--primary, #00ff88);
  color: var(--text-main, #e6edf3);
  border-radius: 12px 12px 2px 12px;
  padding: 8px 12px;
  font-size: 0.8rem;
  line-height: 1.4;
  white-space: pre-wrap;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.45);
}
.mascot-config {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 1px solid var(--border-color, rgba(255,255,255,0.1));
  background: var(--bg-dark, #0d1117);
  color: var(--text-muted, #8b949e);
  font-size: 11px;
  line-height: 1;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s;
}
.mascot:hover .mascot-config {
  opacity: 1;
}
.mascot-restore {
  position: fixed;
  right: 16px;
  bottom: 16px;
  z-index: 9000;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 1px solid var(--border-color, rgba(255,255,255,0.1));
  background: var(--bg-card, rgba(255,255,255,0.05));
  font-size: 16px;
  cursor: pointer;
  opacity: 0.6;
}
.mascot-restore:hover {
  opacity: 1;
}
.mascot-picker {
  position: fixed;
  z-index: 9100;
  background: var(--bg-dark, #0d1117);
  border: 1px solid var(--border-color, rgba(255,255,255,0.1));
  border-radius: 10px;
  padding: 8px;
  min-width: 150px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
}
.picker-title {
  color: var(--text-muted, #8b949e);
  font-size: 0.72rem;
  padding: 2px 8px 8px;
}
.picker-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  color: var(--text-main, #e6edf3);
}
.picker-item:hover {
  background: rgba(255, 255, 255, 0.06);
}
.picker-item.selected {
  color: var(--primary, #00ff88);
}

/* ── 채팅창 ── */
.chat-win {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 8900;
  width: 360px;
  height: 470px;
  display: flex;
  flex-direction: column;
  background: var(--bg-dark, #0d1117);
  border: 1px solid var(--border-color, rgba(255,255,255,0.15));
  border-radius: 14px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.6);
  overflow: hidden;
  animation: chat-enter 0.2s ease-out;
}
@keyframes chat-enter {
  from { opacity: 0; transform: translateY(16px) scale(0.97); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-color, rgba(255,255,255,0.1));
  background: var(--bg-card, rgba(255,255,255,0.05));
}
.chat-title {
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--primary, #00ff88);
}
.chat-header-btns {
  display: flex;
  gap: 4px;
}
.chat-hbtn {
  background: none;
  border: none;
  color: var(--text-muted, #8b949e);
  font-size: 0.95rem;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 6px;
}
.chat-hbtn:hover {
  color: var(--text-main, #e6edf3);
  background: rgba(255, 255, 255, 0.06);
}
.chat-msgs {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.chat-msg-user {
  display: flex;
  justify-content: flex-end;
}
.chat-msg-bot {
  display: flex;
  justify-content: flex-start;
}
.chat-bubble-user {
  max-width: 78%;
  background: rgba(0, 255, 136, 0.12);
  border: 1px solid rgba(0, 255, 136, 0.25);
  color: var(--text-main, #e6edf3);
  border-radius: 12px 12px 2px 12px;
  padding: 8px 12px;
  font-size: 0.84rem;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
.chat-bubble-bot {
  max-width: 85%;
  background: var(--bg-card, rgba(255,255,255,0.05));
  border: 1px solid var(--border-color, rgba(255,255,255,0.1));
  color: var(--text-main, #e6edf3);
  border-radius: 12px 12px 12px 2px;
  padding: 8px 12px;
  font-size: 0.84rem;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
.chat-input-row {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  border-top: 1px solid var(--border-color, rgba(255,255,255,0.1));
}
.chat-input {
  flex: 1;
  background: var(--bg-card, rgba(255,255,255,0.05));
  border: 1px solid var(--border-color, rgba(255,255,255,0.15));
  color: var(--text-main, #e6edf3);
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 0.85rem;
  outline: none;
}
.chat-input:focus {
  border-color: var(--primary, #00ff88);
}
.chat-send {
  background: rgba(0, 255, 136, 0.15);
  border: 1px solid var(--primary, #00ff88);
  color: var(--primary, #00ff88);
  border-radius: 8px;
  padding: 0 14px;
  font-size: 0.85rem;
  cursor: pointer;
  white-space: nowrap;
}
.chat-send:disabled {
  opacity: 0.4;
  cursor: default;
}
</style>
