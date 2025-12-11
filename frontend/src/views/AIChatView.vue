<template>
  <div class="ai-chat-page">
    <!-- conversation list moved to global Siderbar component; AIChatView only renders the chat area -->

    <section class="chat-area">
      <header class="chat-header">
        <div class="title">{{ currentConversation?.title || '聊天' }}</div>
        <div class="header-actions">
          <button class="icon-btn" title="清空聊天记录" aria-label="清空聊天记录" @click="onClickClear"
                  :disabled="clearing">
            <font-awesome-icon icon="trash-alt"/>
          </button>
          <div class="draft" v-if="hasDraft">草稿已保存</div>
        </div>
      </header>

      <!-- Confirm modal for clearing chat -->
      <div v-if="showClearConfirm" class="confirm-overlay" @keydown.esc="cancelClear" @click.self="cancelClear" tabindex="-1">
        <div class="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-title" ref="confirmDialogRef" tabindex="0">
            <div class="confirm-body">清空后将无法恢复历史消息，是否确认删除当前会话？</div>
            <div class="confirm-actions">
              <button class="btn btn-confirm" @click="confirmClear" :disabled="clearing">确认</button>
            </div>
        </div>
      </div>

      <div class="messages" ref="messagesEl">
        <div v-for="m in messages" :key="m.id + (m.streaming ? '-s' : '-f')" :class="['message', m.role]">
          <div class="bubble">
            <template v-if="m.role === 'assistant'">
              <!-- Always render assistant content as HTML produced by markdown-it. This ensures ordered lists and other markdown
                   structures are parsed and rendered during streaming and on initial load. -->
              <div class="assistant-content" v-html="formatMessage(m.content)"></div>
            </template>
            <div v-else class="user-content">{{ m.content }}</div>
            <div class="status" v-if="m.status && m.status !== '已完成'">{{ m.status }}</div>
          </div>
        </div>
      </div>

      <footer class="chat-input">
        <textarea ref="inputEl" v-model="input" rows="4" @input="onInput" @keydown.enter.exact.prevent="onSend"
                  placeholder="输入消息，按 Enter 发送">
        </textarea>
        <div class="controls" aria-hidden="false">
          <select v-model="modelId" class="model-select" title="选择模型">
            <option value="deepseek-chat">deepseek-chat</option>
            <option value="deepseek-reasoner">deepseek-reasoner</option>
          </select>

          <button class="send-icon" title="发送" aria-label="发送消息" :class="{disabled: sending || !input.trim()}"
                  :disabled="sending || !input.trim()" @click="onSend">
            <font-awesome-icon icon="paper-plane"/>
          </button>
        </div>
      </footer>
    </section>

  </div>
</template>

<script setup>
import {computed, nextTick, onMounted, ref, watch} from 'vue';
import {useRoute} from 'vue-router';
import MarkdownIt from 'markdown-it';
import hljs from 'highlight.js';
import 'highlight.js/styles/github.css';
import apiClient from '@/utils/axios';
import {useConversationStore} from '@/stores/conversationStore';

// FontAwesome setup for chat action icons
import {library} from '@fortawesome/fontawesome-svg-core';
import {faPaperPlane, faTrashAlt} from '@fortawesome/free-solid-svg-icons';
import {useAuthStore} from "@/stores/authStore.js";
import {showError, showInfo} from "@/utils/toast.js";

library.add(faTrashAlt, faPaperPlane);

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true, // 启用换行符转换
  typographer: true, // 启用排版优化
  highlight: function (str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return '<pre class="hljs"><code>' + hljs.highlight(str, {language: lang}).value + '</code></pre>';
      } catch (__) {
      }
    }
    try {
      return '<pre class="code-block hljs"><code>' + hljs.highlightAuto(str).value + '</code></pre>';
    } catch (__) {
    }
    return '<pre class="code-block hljs"><code>' + md.utils.escapeHtml(str) + '</code></pre>';
  }
});

// Reactive state
const conversationId = ref(null);
const currentConversation = ref(null);
const conversationStore = useConversationStore();
const conversations = ref([]);
const messages = ref([]);
const messagesEl = ref(null);
const input = ref('');
const inputEl = ref(null); // textarea ref
const sending = ref(false);
const clearing = ref(false);
// continuousConversation and queryDatabase removed; backend will always use recent context
const modelId = ref('deepseek-chat');
const draftKey = (id) => `ai_draft_user_${id}`;
const authStore = useAuthStore();
const MIN_ROWS = 3;
const MAX_ROWS = 10;

function adjustTextareaHeight() {
  const el = inputEl.value;
  if (!el) return;
  el.style.height = 'auto';
  const cs = window.getComputedStyle(el);
  let lineHeight = parseFloat(cs.lineHeight);
  if (!lineHeight || isNaN(lineHeight)) {
    const fontSize = parseFloat(cs.fontSize) || 16;
    lineHeight = fontSize * 1.2;
  }
  const paddingTop = parseFloat(cs.paddingTop) || 0;
  const paddingBottom = parseFloat(cs.paddingBottom) || 0;
  const borderTop = parseFloat(cs.borderTopWidth) || 0;
  const borderBottom = parseFloat(cs.borderBottomWidth) || 0;
  const maxHeight = Math.round(lineHeight * MAX_ROWS + paddingTop + paddingBottom + borderTop + borderBottom);
  const minHeight = Math.round(lineHeight * MIN_ROWS + paddingTop + paddingBottom + borderTop + borderBottom);
  el.style.minHeight = minHeight + 'px';
  const desired = el.scrollHeight;
  const newHeight = Math.min(desired, maxHeight);
  el.style.height = newHeight + 'px';
  if (desired > maxHeight) {
    el.style.overflowY = 'auto';
  } else {
    el.style.overflowY = 'hidden';
  }
}

function scrollMessages() {
  try {
    if (messagesEl.value) {
      nextTick(() => {
        try {
          messagesEl.value.scrollTop = messagesEl.value.scrollHeight;
        } catch (e) {
        }
      });
    }
  } catch (e) {
  }
}

function onInput() {
  adjustTextareaHeight();
}

// formatting helper used in template
function formatMessage(text) {
  if (!text) return '';
  try {
    let processedText = text
        .replace(/\*\*(.*?)\*\*/g, '**$1**') // 确保粗体格式
        .replace(/\*(.*?)\*/g, '*$1*') // 确保斜体格式
        .replace(/`(.*?)`/g, '`$1`'); // 确保代码格式
    return md.render(processedText);
  } catch (e) {
    console.error('Markdown 渲染错误:', e);
    return text.replace(/\n/g, '<br>');
  }
}

watch(() => conversationStore.conversations, (list) => {
  conversations.value = list || [];
}, { immediate: true });

async function loadConversations() {
  try {
    const res = await conversationStore.fetchConversations();
    const payload = res || {};
    conversations.value = payload.conversations || [];
    const curr = payload.current || null;
    if (curr) {
      conversationId.value = curr.id;
      currentConversation.value = {id: curr.id, title: curr.title, created_at: curr.created_at};
      messages.value = curr.messages || [];
    } else {
      conversationId.value = null;
      currentConversation.value = null;
      messages.value = [];
    }

    const uid = authStore.user?.id;
    const draft = uid ? localStorage.getItem(draftKey(uid)) : null;
    input.value = draft || '';

    await nextTick(() => {
      try {
        messagesEl.value.scrollTop = messagesEl.value.scrollHeight;
      } catch (e) {}
    });
  } catch (e) {
    console.error('Failed to load conversations', e);
  }
}

async function openConversation(id) {
  try {
    const res = await apiClient.get('/agent', {params: {conversation_id: id}});
    const payload = res.data || {};
    conversationId.value = payload.id || id;
    currentConversation.value = {id: payload.id, title: payload.title || ('会话 ' + id), created_at: payload.created_at};
    messages.value = payload.messages || [];
    await nextTick(() => adjustTextareaHeight());
    scrollMessages();
  } catch (e) {
    console.error('openConversation failed', e);
  }
}

async function onSend() {
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  const uid = authStore.user?.id;
  if (uid) localStorage.removeItem(draftKey(uid));
  await nextTick(() => adjustTextareaHeight());
  sending.value = true;
  try {
    const userMsg = {id: 'tmp-' + Date.now(), role: 'user', content: text, status: '已完成'};
    const assistantMsg = {
      id: 'tmp-assistant-' + Date.now(),
      role: 'assistant',
      content: '',
      status: '思考中...',
      streaming: true,
      streamingBuffer: '',
      flushTimer: null
    };
    messages.value.push(userMsg);
    messages.value.push(assistantMsg);
    scrollMessages();

    // include conversation_id when sending if present
    const body = {
      text: text,
      model_id: modelId.value
    };
    if (conversationId.value) body.conversation_id = conversationId.value;

    const response = await fetch('http://localhost:8000/agent', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authStore.accessToken}`
      },
      body: JSON.stringify(body)
    });

    if (!response.ok) {
      // Backend returned error (e.g., 503 when model provider is not configured)
      const errText = await response.text().catch(() => response.statusText || '请求失败');
      assistantMsg.streaming = false;
      assistantMsg.status = '调用模型失败';
      assistantMsg.content = '';
      sending.value = false;
      showError(new Error(`模型调用失败: ${errText}`));
      // reload conversation list to reflect that user message was saved but no assistant reply
      await loadConversations();
      if (conversationId.value) {
        await openConversation(conversationId.value);
      }
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    assistantMsg.status = '输出中...';
    assistantMsg.streaming = false;
    let accumulatedText = '';
    try {
      while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, {stream: true});
        accumulatedText += chunk;
            assistantMsg.content = accumulatedText;
            scrollMessages();
        await new Promise(resolve => setTimeout(resolve, 10));
      }
      assistantMsg.streaming = false;
      assistantMsg.status = '已完成';
      assistantMsg.updated_at = new Date().toISOString();
    } finally {
      reader.releaseLock();
    }

    // after sending, reload conversation list and current messages to reflect saved messages
    await loadConversations();
    if (conversationId.value) {
      await openConversation(conversationId.value);
    }

    scrollMessages();
    sending.value = false;
  } catch (e) {
    console.error('发送消息失败:', e);
    sending.value = false;
  }
}


async function clearChat() {
  if (!conversationId.value) {
    messages.value = [];
    const uid = authStore.user?.id;
    if (uid) localStorage.removeItem(draftKey(uid));
    return;
  }
  try {
    const response = await apiClient.delete(`/agent`, {params: {conversation_id: conversationId.value}});
    if (response && response.data?.status === 'success') {
      showInfo(response.data.message)
    } else {
      showError(new Error('清空聊天记录失败'));
    }
    const removedId = Number(response?.data?.conversation_id ?? conversationId.value);
    if (!Number.isNaN(removedId)) {
      conversationStore.removeConversationById(removedId);
      conversations.value = (conversations.value || []).filter(c => Number(c.id) !== removedId);
      if (Number(conversationId.value) === removedId) {
        conversationId.value = null;
        currentConversation.value = null;
        messages.value = [];
      }
    }
    // reload list and open latest (or none)
    await loadConversations();
    const convs = conversations.value || [];
    if (convs.length) {
      await openConversation(convs[0].id);
    } else {
      conversationId.value = null;
      currentConversation.value = null;
      messages.value = [];
    }
    const uid = authStore.user?.id;
    if (uid) localStorage.removeItem(draftKey(uid));
  } catch (e) {
    console.error('Failed to clear conversation', e);
  }
}

watch(input, (v) => {
  const uid = authStore.user?.id;
  if (!uid) return;
  if (!v || v.trim() === '') {
    localStorage.removeItem(draftKey(uid));
  } else {
    localStorage.setItem(draftKey(uid), v);
  }
});

const hasDraft = computed(() => {
  const uid = authStore.user?.id;
  if (!uid) return false;
  return localStorage.getItem(draftKey(uid));
});

// Confirmation modal state for clearing chat
const showClearConfirm = ref(false);
const confirmDialogRef = ref(null);

function onClickClear() {
  // open the confirmation dialog instead of clearing immediately
  showClearConfirm.value = true;
  nextTick(() => {
    try {
      confirmDialogRef.value && confirmDialogRef.value.focus();
    } catch (e) {}
  });
}

async function confirmClear() {
  if (clearing.value) return;
  clearing.value = true;
  try {
    await clearChat();
    showClearConfirm.value = false;
  } catch (e) {
    console.error('clearChat failed', e);
  } finally {
    clearing.value = false;
  }
}

function cancelClear() {
  showClearConfirm.value = false;
}

const route = useRoute();

onMounted(async () => {
  // If the sidebar navigated with a conversation_id query param, open that conversation;
  // otherwise load the conversation list and default current conversation.
  const q = route.query?.conversation_id;
  if (q) {
    const id = parseInt(Array.isArray(q) ? q[0] : q);
    if (!isNaN(id)) {
      await openConversation(id);
      // still reload the conversation list in background
      loadConversations();
    } else {
      await loadConversations();
    }
  } else {
    await loadConversations();
  }
  nextTick(() => adjustTextareaHeight());
});

// react to route query changes (when user clicks conversation in sidebar)
watch(() => route.query?.conversation_id, async (val, oldVal) => {
  if (!val) return;
  const id = parseInt(Array.isArray(val) ? val[0] : val);
  if (!isNaN(id) && id !== conversationId.value) {
    await openConversation(id);
  }
});
</script>

<style scoped>
.ai-chat-page {
  display: flex;
  background: transparent; /* light bg */
  color: #111827; /* light text */
}

.conversation-list {
  width: 260px;
  border-right: 1px solid rgba(0,0,0,0.06);
  padding: 12px;
  box-sizing: border-box;
}
.list-header {
  font-weight: 700;
  margin-bottom: 8px;
}
.list-controls {
  margin-bottom: 8px;
}
.list-rows {
  list-style: none;
  padding: 0;
  margin: 0;
  max-height: 70vh;
  overflow: auto;
}
.list-rows .row {
  padding: 8px;
  border-radius: 6px;
  cursor: pointer;
}
.list-rows .row:hover { background: rgba(0,0,0,0.03); }
.list-rows .row.active { background: rgba(37,99,235,0.06); }
.row-title { font-weight: 600; }
.row-sub { font-size: 12px; color: #6b7280; }

.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: transparent;
  border-radius: 12px;
  align-items: center;
}

.chat-header {
  padding: 16px;
  display: flex;
  width: 80%;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  color: #111827; /* ensure header uses explicit text color */
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.chat-header .title {
  color: #111827; /* explicit title color */
  font-weight: 700;
  font-size: 1.1rem;
  letter-spacing: 1px;
}

.icon-btn {
  background: transparent;
  border: 1px solid rgba(0, 0, 0, 0.08);
  color: #111827; /* icon color */
  padding: 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 40px;
  min-height: 40px;
}

.icon-btn:hover {
  background: rgba(37, 99, 235, 0.06); /* icon hover */
  color: #2563eb; /* primary */
  border-color: transparent;
}

.icon-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.messages {
  flex: 1;
  overflow: auto;
  padding: 20px;
  background: transparent;
  width: 70%;
  box-sizing: border-box;
  /* leave extra space at the bottom so floating footer doesn't overlap messages */
  padding-bottom: calc(10vh + 180px);
}

/* Ensure the v-for wrapper for each message fills the container so inner .message justify-content works */
.messages > div {
  width: 100%;
  box-sizing: border-box;
}

.message {
  margin-bottom: 16px;
  display: flex;
  width: 100%;
  font-size: 1rem;
}

.message.user {
  justify-content: flex-end;
}

.message.user .bubble {
  background: #e6f7ff;
  color: #111827;
  align-self: flex-end;
  border-radius: 12px 12px 4px 12px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.message.assistant {
  justify-content: flex-start;
}

.message.assistant .bubble {
  background: transparent;
  color: #111827;
  border-radius: 12px 12px 12px 4px;
}

.bubble {
  padding: 10px;
  max-width: 100%;
  overflow-wrap: anywhere;
  word-break: break-word;
}

/* ensure markdown lists and code blocks fit inside bubble */
.assistant-content ul,
.assistant-content ol {
  padding-left: 1.2em;
  margin: 0 0 0.5em 0;
  list-style-position: inside; /* put bullets/numbers inside the container to avoid overflow */
}

.assistant-content li {
  overflow-wrap: anywhere;
  word-break: break-word;
  hyphens: auto;
}

.assistant-content pre {
  white-space: pre-wrap; /* allow long code lines to wrap */
  overflow: auto;
}

.assistant-content code {
  word-break: break-word;
}

.chat-input {
  padding: 16px;
  display: flex;
  flex-direction: column;
  height: auto;
  gap: 12px;
  background: #ececf3;
  position: fixed;
  bottom: 3%;
  border-radius: 30px;
  width: 70%;
  z-index: 60; /* float above other content */
  box-shadow: 0 10px 30px rgba(2, 6, 23, 0.08);
}

.chat-input textarea {
  flex: 1;
  resize: none;
  padding: 12px 60px 12px 12px;
  background: transparent;
  transition: all 0.2s ease;
  min-height: calc(1.2rem * 3);
  max-height: calc(1.2rem * 10);
  overflow-y: hidden;
  font-size: 1rem;
  border: transparent;
}

.chat-input textarea:focus {
  outline: none;
}

.dark-theme .chat-input textarea {
  background: #212121 !important;
  color: #e6eef8;
}

/* New toggle controls styles */
.controls {
  display: flex;
  align-items: flex-end;
  gap: 20px;
  margin-top: 12px;
}

.model-select {
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid #111827;
  background: transparent;
  color: #0b3080;
  font-size: 0.9rem;
}
.dark-theme .model-select {
  color: #5b68f5;
  border-color: #5b68f5;
}

.model-select:focus {
  outline: none;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.08);
}

.toggle-btn {
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid #111827;
  background: transparent;
  color: #afafaf;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.12s ease;
  width: fit-content;
}

.toggle-btn.enabled {
  border-color: #123a96;
  color: #0b3080;
}

.toggle-btn:hover {
  background: rgba(0, 0, 0, 0.05);
}

.dark-theme .toggle-btn {
  border-color: #93989d;
  color: #b8bfc7;
}

.dark-theme .toggle-btn.enabled {
  /* keep enabled color as sky-blue in dark mode */
  border-color: #5b68f5;
  color: #5b68f5;
}

.dark-theme .chat-input {
  background: #212121 !important;
  color: #e6eef8;
}


.send-icon {
  position: absolute;
  right: 22px;
  bottom: 22px;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: #467cf1;
  color: #ffffff;
  cursor: pointer;
  transition: all 0.15s ease;
  box-shadow: 0 6px 18px rgba(37, 99, 235, 0.12);
}

.send-icon:hover {
  opacity: 0.95;
  background: #2563eb;
  transform: translateY(-1px);
}

.dark-theme .send-icon:hover {
  background: #5787f5;
}

.send-icon.disabled {
  opacity: 0.6;
  cursor: not-allowed;
  box-shadow: none;
}

.send-icon:disabled {
  cursor: not-allowed;
}

.icon-btn svg, .send-icon svg {
  width: 18px;
  height: 18px;
  display: block;
  color: inherit;
  fill: currentColor;
  stroke: currentColor;
}

.draft {
  margin-left: 12px;
  color: #6b7280;
  font-size: 0.9rem;
}

.message .status {
  font-size: 12px;
  color: #6b7280;
  margin-top: 6px;
}

/* DARK styles applied when root has .is-dark class */
.dark-theme .ai-chat-page {
  background: #0b1220;
  color: #e6eef8;
}

.dark-theme .chat-header {
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  color: #e6eef8;
}

.dark-theme .chat-header .title {
  color: #e6eef8;
}

.dark-theme .icon-btn {
  border: 1px solid rgba(255, 255, 255, 0.06);
  color: #e6eef8;
}

.dark-theme .icon-btn:hover {
  background: rgba(59, 130, 246, 0.08);
  color: #3b82f6;
}

.dark-theme .message.user .bubble {
  background: #013241;
  color: #e6eef8;
}

.dark-theme .message.assistant .bubble {
  color: #e6eef8;
}

.dark-theme .send-icon {
  background: #3b82f6;
  color: #ffffff;
  box-shadow: 0 6px 18px rgba(59, 130, 246, 0.12);
}

.dark-theme .draft {
  color: #9ca3af;
}

.dark-theme .message .status {
  color: #9ca3af;
}

/* Confirm dialog styles */
.confirm-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.confirm-dialog {
  background: #ffffff;
  border-radius: 12px;
  padding: 24px;
  max-width: 400px;
  width: 90%;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
}
.dark-theme .confirm-dialog {
  background: #0b1320;
  color: #e6eef8;
}

.confirm-body {
  font-size: 1rem;
  margin-bottom: 24px;
  color: #374151;
}
.dark-theme .confirm-body {
  background: #0b1320;
  color: #e6eef8;
}

.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
.dark-theme .confirm-actions {
  color: #e6eef8;
}

.btn {
  padding: 10px 16px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.15s ease;
}

.btn-confirm {
  background: #2563eb;
  color: #ffffff;
}
.dark-theme .btn-confirm {
  background: #5787f5;
  color: #ffffff;
}

.btn-confirm:hover {
  background: #1d4ed8;
}
.dark-theme .btn-confirm:hover {
  background: #5686ef !important;
}
</style>
