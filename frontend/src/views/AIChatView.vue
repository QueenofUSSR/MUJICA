<template>
  <div class="ai-chat-page">
    <section class="chat-area">
      <header class="chat-header">
        <div class="title">{{ currentConversation?.title || '多智能体会话' }}</div>
        <div class="header-actions">
          <button class="icon-btn" title="清空会话" aria-label="清空会话" @click="onClickClear" :disabled="clearing">
            <font-awesome-icon icon="trash-alt"/>
          </button>
          <div class="draft" v-if="hasDraft">草稿已保存</div>
          <button class="btn run-btn" @click="runSession" :disabled="runDisabled">
            <span v-if="running" class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
            <span v-else >运行任务</span>
          </button>
          <button class="btn stop-btn" v-if="canStopSession" @click="stopSession">停止</button>
          <div v-if="runProgress" class="run-progress"
               :class="{'text-success': runProgress === '已完成' || runProgress==='completed', 'text-danger': runProgress === '失败' || runProgress==='failed'}">
            {{ runProgress }}
          </div>
        </div>
      </header>

      <nav class="tabs">
        <button :class="['tab', {active: activeTab === 'overview'}]" @click="activeTab = 'overview'">总览</button>
        <button :class="['tab', {active: activeTab === 'tasks'}]" @click="activeTab = 'tasks'">子任务</button>
        <button :class="['tab', {active: activeTab === 'logs'}]" @click="activeTab = 'logs'">日志</button>
      </nav>

      <!-- Overview: 任务需求 + 最终产物 -->
      <section v-if="activeTab === 'overview'" class="panel overview">
        <div class="overview-row">
          <!-- 任务需求输入 -->
          <div class="prompt-card">
            <label class="prompt-label">任务需求</label>
            <textarea ref="inputEl" v-model="overviewPrompt" class="prompt-textarea" rows="4"
                      placeholder="例如：请为我实现一个Java的快速排序，并附带简单测试用例" @input="onInput"></textarea>
            <div class="prompt-params">
              <div class="param-field">
                <label>模型</label>
                <select v-model="llmParams.model_id">
                  <option value="gpt-4o">gpt-4o</option>
                  <option value="gpt-4o-mini">gpt-4o-mini</option>
                  <option value="gpt-4.1">gpt-4.1</option>
                  <option value="gpt-4.1-mini">gpt-4.1-mini</option>
                </select>
              </div>
              <div class="param-field">
                <label>最大 Tokens</label>
                <input type="number" min="256" max="4096" step="64" v-model.number="llmParams.max_tokens"
                       placeholder="1024"/>
              </div>
              <div class="param-field">
                <label>温度</label>
                <input type="number" min="0" max="1" step="0.1" v-model.number="llmParams.temperature"
                       placeholder="0.2"/>
              </div>
              <div class="param-field">
                <label>API Key (可选)</label>
                <input type="password" v-model="llmParams.api_key" placeholder="自定义临时 key"/>
              </div>
            </div>
            <div class="prompt-help">提示：填写后点击右上角“运行任务”，系统将按检索→规划→编码→调试的顺序逐步执行。</div>
          </div>

          <div class="final-result">
            <h3>最终产物</h3>
            <div v-if="finalResult">
              <div class="artifact-meta">来源: {{ finalResult.title || currentConversation?.title }}</div>
              <div class="artifact-meta" v-if="savedLlmParamsText">
                LLM 参数：{{ savedLlmParamsText }}
              </div>
              <div v-if="finalResult.code || finalResult.code_str">
                <div class="code-actions">
                                <button class="btn btn-download" @click="downloadFinalResult">下载</button>
                                <button class="btn btn-run" v-if="!isEditing" @click="runCodeWithAgent">运行</button>
                                <button class="btn" v-if="!isEditing" @click="startEdit">编辑</button>
                                <button class="btn" v-if="isEditing" @click="saveEdit">保存</button>
                                <button class="btn" v-if="isEditing" @click="cancelEdit">取消</button>
                </div>
                              <div v-if="!isEditing">
                                <pre class="code-block hljs"><code v-html="highlightCode(finalResult.code_str || finalResult.code)"></code></pre>
                              </div>
                              <div v-else>
                                <textarea ref="editEl" v-model="editCode" @input="onEditInput" class="prompt-textarea code-edit" style="min-height:160px;white-space:pre;"></textarea>
                              </div>
                <div v-if="finalResult.output || finalResult.comment" style="margin-top:12px;">
                  <div style="margin-bottom:8px;">
                    <label style="font-weight:600;">程序输出</label>
                    <pre class="code-block" style="background:#0b1220;color:#dbeafe;padding:10px;">{{ finalResult.output }}</pre>
                  </div>
                  <div>
                    <label style="font-weight:600;">评估结果</label>
                    <pre class="code-block" style="background:#071029;color:#e6fffa;padding:10px;">{{ finalResult.comment }}</pre>
                  </div>
                </div>
              </div>
              <div v-else-if="finalResult.text">
                <div class="text-artifact" v-html="formatMessage(finalResult.text)"></div>
              </div>
              <div v-else>
                <div class="empty">未生成最终产物</div>
              </div>
            </div>
            <div v-else class="empty">尚无结果，运行任务后将显示最终聚合产物。</div>
            <div v-if="!finalResult" class="help-card">
              <h4>快速上手</h4>
              <ol>
                <li>在左侧选择或新建一个会话（点击“＋ 新建会话”）。</li>
                <li>在上方“任务需求”中填写你的任务描述，然后点击“运行任务”。</li>
                <li>切到 <strong>Tasks</strong> 查看子任务进度与结果。</li>
                <li>最终产物将在此处展示，可下载或复制。</li>
              </ol>
              <div class="help-actions">
                <button class="btn" @click="() => { /* 预留：加载示例 */ }">查看示例</button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Tasks panel -->
      <section v-if="activeTab === 'tasks'" class="panel tasks-panel">
        <h3>子任务列表</h3>
        <ul class="task-list">
          <li v-for="t in visibleTasks" :key="t.id" :class="['task-item', roleColor(t.assigned_role_id)]">
            <div class="task-header" @click="toggleTaskCollapse(t.id)">
              <div class="task-title">
                <span class="task-toggle" :class="{collapsed: isTaskCollapsed(t.id)}"></span>
                {{ t.title }} <span class="role">[{{ getRoleName(t.assigned_role_id) }}]</span>
              </div>
              <div class="task-meta">状态: {{ t.status }} · 置信度: {{ t.confidence ?? '-' }}</div>
            </div>
            <div class="task-body" v-if="taskResultText(t)">
              <div class="result" v-if="!isTaskCollapsed(t.id)">
                <strong>结果</strong>
                <pre class="result-block">{{ taskResultText(t) }}</pre>
              </div>
              <div class="result collapsed-preview" v-else>
                <strong>结果</strong>
                <p>{{ truncatedTaskResult(t, 120) }}</p>
              </div>
            </div>
            <div class="task-actions">
              <button class="btn btn-copy" @click.stop="copyTaskResult(t)">复制</button>
              <button class="btn btn-download" @click.stop="downloadTaskResult(t)">下载</button>
            </div>
          </li>
        </ul>
      </section>

      <!-- Logs panel -->
      <section v-if="activeTab === 'logs'" class="panel logs-panel">
        <h3>执行日志</h3>
        <ul class="log-list">
          <li v-for="l in logs" :key="l.id" class="log-item">
            <div class="log-meta">[{{ l.level }}] {{ l.created_at }}</div>
            <div class="log-msg">{{ l.message }}</div>
            <div class="log-payload" v-if="l.payload">{{ JSON.stringify(l.payload) }}</div>
          </li>
        </ul>
      </section>

      <!-- Input area removed (chat footer) -->
    </section>
  </div>
</template>

<script setup>
import {computed, nextTick, onMounted, onUnmounted, ref, watch} from 'vue';
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
  breaks: true,
  typographer: true,
});

// Reactive state
const conversationId = ref(null);
const currentConversation = ref(null);
const conversationStore = useConversationStore();
const conversations = ref([]);
const overviewPrompt = ref('');
const messages = ref([]);
const input = ref('');
const inputEl = ref(null); // textarea ref
const editEl = ref(null); // editor textarea ref (autosize)
const clearing = ref(false);
const modelId = ref('gpt-4o');
const llmParams = ref({
  model_id: 'gpt-4o',
  max_tokens: 1024,
  temperature: 0.2,
  api_key: ''
});
const savedLlmParams = ref(null);
// helper: build per-user draft key used for localStorage caching
const draftKey = (uid) => `agent_task_draft_${uid}`;
const savedLlmParamsText = computed(() => {
  if (!savedLlmParams.value) return '';
  const parts = [];
  if (savedLlmParams.value.model_id) parts.push(`模型 ${savedLlmParams.value.model_id}`);
  if (savedLlmParams.value.max_tokens) parts.push(`max_tokens=${savedLlmParams.value.max_tokens}`);
  if (savedLlmParams.value.temperature !== undefined) parts.push(`temp=${savedLlmParams.value.temperature}`);
  if (savedLlmParams.value.api_key) parts.push('自定义 key');
  return parts.join(' · ');
});
const authStore = useAuthStore();
const route = useRoute();

// New multi-agent UI state
const activeTab = ref('overview');
const finalResult = ref(null);
const tasks = ref([]);
const collapsedTasks = ref(new Set());
const visibleTasks = computed(() => (tasks.value || [])
    .filter(t => t && t.parent_id !== null && t.parent_id !== undefined)
    .sort((a, b) => Number(a.id) - Number(b.id)));
const logs = ref([]);
const sessionStatus = ref(''); // 'queued' | 'running' | 'completed' | 'failed' | ''
const currentSessionId = ref(null);
let lastTasksRefreshSessionId = null;
const isEditing = ref(false);
const editCode = ref('');

// Define loadConversations early so mounted hook can use it safely
async function loadConversations() {
  try {
    const token = authStore.accessToken;
    const url = token ? `/mapcoder/session?token=${encodeURIComponent(token)}` : '/mapcoder/session';
    const res = await apiClient.get(url, {headers: token ? {Authorization: `Bearer ${token}`} : {}});
    const list = Array.isArray(res.data) ? res.data : [];
    list.sort((a, b) => Number(b.id) - Number(a.id));
    conversations.value = list;
    if (!conversationId.value && list.length) {
      await openConversation(list[0].id);
    }
  } catch (e) {
    console.warn('加载会话列表失败', e);
  }
}

function syncCollapsedTasks(list) {
  const ids = new Set((list || []).map(t => Number(t.id)));
  const next = new Set();
  ids.forEach(id => next.add(id));
  collapsedTasks.value = next;
}

function applyTasks(list) {
  const normalized = Array.isArray(list) ? list : [];
  tasks.value = normalized;
  syncCollapsedTasks(normalized);
}

// New UI state for run/polling and selected task
const running = ref(false);
const runProgress = ref('');
let pollTimer = null;
let fallbackTimer = null;

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

const sessionActiveStatuses = ['pending', 'queued', 'running'];
const isSessionActive = computed(() => {
  const status = (sessionStatus.value || '').toLowerCase();
  return !!currentSessionId.value && sessionActiveStatuses.includes(status);
});
const runDisabled = computed(() => {
  const promptEmpty = !overviewPrompt.value || !overviewPrompt.value.trim();
  return promptEmpty || !conversationId.value || running.value || isSessionActive.value;
});
const canStopSession = computed(() => isSessionActive.value);

function taskResultText(task) {
  if (!task) return '';
  const res = task.result || {};
  return res.code || res.text || res.output || task.plan || '';
}

// SSE (Server-Sent Events) subscription
const sse = ref(null);
const sseStatus = ref('idle'); // 'idle' | 'connecting' | 'connected' | 'fallback'
let sseConnectTimer = null;

function startSSE(sessionId) {
  stopSSE();
  if (!sessionId) return;
  const base = apiClient.defaults.baseURL || '';
  const token = authStore.accessToken;
  const url = token ? `${base}/mapcoder/session/${sessionId}/events?token=${encodeURIComponent(token)}` : `${base}/mapcoder/session/${sessionId}/events`;
  try {
    sseStatus.value = 'connecting';
    const es = new EventSource(url);
    sse.value = es;
    es.onopen = () => {
      sseStatus.value = 'connected';
    };
    es.onmessage = (ev) => {
      try {
        const payload = JSON.parse(ev.data);
        handleSSEEvent(payload);
      } catch (e) {
      }
    };
    es.onerror = () => {
      stopSSE();
      startFallbackPolling(sessionId);
    };
  } catch (e) {
    console.warn('SSE failed, fallback to polling', e);
    startFallbackPolling(sessionId);
  }
}

function stopSSE() {
  if (sseConnectTimer) {
    clearTimeout(sseConnectTimer);
    sseConnectTimer = null;
  }
  if (sse.value) {
    try {
      sse.value.close();
    } catch (e) {
    }
    sse.value = null;
  }
  // 不改变 sseStatus，这由上层流程来设置
}

async function fetchSessionStatus(sessionId) {
  try {
    const res = await apiClient.get(`/mapcoder/session/${sessionId}/status`);
    const data = res.data || {};
    // merge logs and tasks from status response
    if (Array.isArray(data.recent_logs)) {
      // recent_logs comes most recent first in backend; normalize to chronological
      const recent = (data.recent_logs || []).slice().reverse();
      // prepend new logs not already present (by id)
      const existingIds = new Set(logs.value.map(l => Number(l.id)));
      recent.forEach(l => {
        if (!existingIds.has(Number(l.id))) logs.value.push(l);
      });
    }
    if (Array.isArray(data.active_tasks)) {
      // replace tasks list with active tasks for simplicity
      tasks.value = data.active_tasks || tasks.value;
    }
    // if session reported final status, refresh full session
    const sess = data.session || {};
    const statusLower = (sess.status || '').toLowerCase();
    if (sessionActiveStatuses.includes(statusLower)) {
      sessionStatus.value = sess.status;
      running.value = true;
    }
    if (sess.status === 'completed' || sess.status === 'failed' || sess.status === 'canceled') {
      running.value = false;
      runProgress.value = sess.status;
      stopPolling();
      stopSSE();
      stopFallbackPolling();
      sseStatus.value = 'idle';
      await openSession(sessionId);
    }
  } catch (e) {
    // ignore transient errors
    console.warn('fallback poll error', e);
  }
}

function startFallbackPolling(sessionId) {
  stopFallbackPolling();
  // immediate fetch then interval
  fetchSessionStatus(sessionId);
  fallbackTimer = setInterval(() => fetchSessionStatus(sessionId), 2000);
}

function stopFallbackPolling() {
  if (fallbackTimer) {
    clearInterval(fallbackTimer);
    fallbackTimer = null;
  }
}

// modify openConversation to use conversation detail before legacy /agent
async function openConversation(id) {
  try {
    const res = await apiClient.get(`/mapcoder/session/${id}`);
    const payload = res.data || {};
    conversationId.value = payload.id || id;
    currentConversation.value = {
      id: conversationId.value,
      title: payload.title || (`任务 ${conversationId.value}`),
      created_at: payload.created_at
    };
    overviewPrompt.value = (payload.metadata?.prompt) || '';
    if (payload.metadata?.llm_params) {
      savedLlmParams.value = payload.metadata.llm_params;
      llmParams.value = {
        model_id: payload.model_id || llmParams.value.model_id,
        max_tokens: payload.metadata.llm_params.max_tokens ?? llmParams.value.max_tokens,
        temperature: payload.metadata.llm_params.temperature ?? llmParams.value.temperature,
        api_key: payload.metadata.llm_params.api_key || ''
      };
    }
    finalResult.value = payload.final_result || null;
    tasks.value = payload.tasks || [];
    logs.value = payload.logs || [];
    sessionStatus.value = payload.status || '';
    activeTab.value = 'overview';
  } catch (e) {
    console.error('openConversation failed', e);
  }
}

// new: open a specific session and start SSE on it
async function openSession(sessionId) {
  try {
    const res = await apiClient.get(`/mapcoder/session/${sessionId}`);
    const payload = res.data || {};
    currentSessionId.value = payload.id || sessionId;
    conversationId.value = payload.conversation_id || conversationId.value;
    currentConversation.value = {
      id: conversationId.value,
      title: payload.title || currentConversation.value?.title,
      created_at: payload.created_at
    };
    if (payload.metadata?.llm_params) {
      savedLlmParams.value = payload.metadata.llm_params;
    }
    messages.value = Array.isArray(payload.messages) ? payload.messages : messages.value;
    finalResult.value = payload.final_result || null;
    tasks.value = payload.tasks || [];
    logs.value = payload.logs || [];
    sessionStatus.value = payload.status || '';
    activeTab.value = 'overview';
    const isFinal = !!finalResult.value || sessionStatus.value === 'completed' || sessionStatus.value === 'failed';
    if (isFinal) {
      running.value = false;
      runProgress.value = sessionStatus.value;
      stopPolling();
      stopSSE();
      stopFallbackPolling();
      sseStatus.value = 'idle';
      currentSessionId.value = null;
    } else {
      running.value = true;
      startSSE(currentSessionId.value);
    }
    await nextTick(() => adjustTextareaHeight());
    scrollMessages();
  } catch (e) {
    console.error('openSession failed', e);
  }
}

// also stopSSE when switching sessions via watch on route.query
watch(() => route.query?.session_id, async (val) => {
  if (!val) return;
  const id = parseInt(Array.isArray(val) ? val[0] : val);
  if (!isNaN(id) && id !== conversationId.value) {
    stopSSE();
    await openConversation(id);
  }
});


async function clearChat() {
  if (!conversationId.value) {
    overviewPrompt.value = '';
    tasks.value = [];
    logs.value = [];
    finalResult.value = null;
    return;
  }
  try {
    await apiClient.delete(`/mapcoder/session/${conversationId.value}`);
    showInfo('任务已删除');
    conversationStore.removeConversationById(conversationId.value);
    conversations.value = (conversations.value || []).filter(c => Number(c.id) !== Number(conversationId.value));
    if (conversations.value.length) {
      await openConversation(conversations.value[0].id);
    } else {
      conversationId.value = null;
      currentConversation.value = null;
      overviewPrompt.value = '';
      tasks.value = [];
      logs.value = [];
      finalResult.value = null;
    }
  } catch (e) {
    console.error('Failed to clear session', e);
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
// const showClearConfirm = ref(false);
// const confirmDialogRef = ref(null);

function onClickClear() {
  // directly clear without modal for now
  if (clearing.value) return;
  clearing.value = true;
  clearChat().finally(() => {
    clearing.value = false;
  });
}

// remove confirmClear and cancelClear functions entirely

onMounted(async () => {
  const q = route.query?.session_id;
  if (q) {
    const id = parseInt(Array.isArray(q) ? q[0] : q);
    if (!isNaN(id)) {
      await openConversation(id);
      loadConversations();
    } else {
      await loadConversations();
    }
  } else {
    await loadConversations();
  }
  nextTick(() => adjustTextareaHeight());
});

// autosize helper: adjust both the prompt textarea and the code editor textarea
function adjustTextareaHeight() {
  nextTick(() => {
    try {
      if (inputEl.value && inputEl.value.style) {
        const ta = inputEl.value;
        ta.style.height = 'auto';
        const max = Math.round(window.innerHeight * 0.45);
        ta.style.height = Math.min(ta.scrollHeight, max) + 'px';
      }
      if (editEl.value && editEl.value.style) {
        const ta = editEl.value;
        ta.style.height = 'auto';
        const max = Math.round(window.innerHeight - 220);
        ta.style.height = Math.min(ta.scrollHeight, max) + 'px';
      }
    } catch (e) {
      // ignore
    }
  });
}

// Fix watch signature to remove unused oldVal
watch(() => route.query?.session_id, async (val) => {
  if (!val) return;
  const id = parseInt(Array.isArray(val) ? val[0] : val);
  if (!isNaN(id) && id !== conversationId.value) {
    await openConversation(id);
  }
});

// 替换 runSession：先创建 Session（带 prompt），再运行
async function runSession() {
  if (!conversationId.value) return;
  const prompt = (overviewPrompt.value || '').trim();
  if (!prompt) return;
  try {
    running.value = true;
    runProgress.value = 'Scheduling...';
    const payload = {
      title: currentConversation.value?.title || undefined,
      model_id: llmParams.value.model_id || modelId.value,
      prompt,
      max_tokens: llmParams.value.max_tokens,
      temperature: llmParams.value.temperature,
      api_key: llmParams.value.api_key || undefined
    };
    const createRes = await apiClient.post(`/mapcoder/session`, payload);
    const sess = createRes.data || {};
    if (!sess || !sess.id) {
      throw new Error('创建任务会话失败');
    }
    conversationId.value = sess.id;
    currentSessionId.value = sess.id;
    currentConversation.value = {
      id: sess.id,
      title: sess.title || (currentConversation.value?.title || `任务 ${sess.id}`),
      created_at: sess.created_at || new Date().toISOString()
    };
    savedLlmParams.value = sess.metadata?.llm_params || payload;
    finalResult.value = null;
    tasks.value = [];
    logs.value = [];
    sessionStatus.value = sess.status || 'pending';
    await apiClient.post(`/mapcoder/session/${sess.id}/run`, {
      prompt,
      title: payload.title,
      max_tokens: payload.max_tokens,
      temperature: payload.temperature,
      api_key: payload.api_key
    });
    runProgress.value = 'Running';
    await openSession(sess.id);
    const poll = async () => {
      const sid = currentSessionId.value;
      if (!sid) return;
      try {
        const res = await apiClient.get(`/mapcoder/session/${sid}/status`);
        const s = res.data?.session || {};
        runProgress.value = s.status || '';
        if (Array.isArray(res.data?.recent_logs)) {
          logs.value = (res.data.recent_logs || []).slice().reverse();
        }
        if (Array.isArray(res.data?.active_tasks)) {
          tasks.value = res.data.active_tasks || [];
        }
        if (['completed', 'failed', 'canceled'].includes((s.status || '').toLowerCase())) {
          stopPolling();
          running.value = false;
          await openSession(sid);
        } else {
          running.value = true;
        }
      } catch (e) { /* ignore */
      }
    };
    await poll();
    stopPolling();
    pollTimer = setInterval(poll, 1500);
  } catch (e) {
    showError(new Error('启动任务失败'));
    running.value = false;
    runProgress.value = '';
  }
}

async function stopSession() {
  try {
    const sid = currentSessionId.value;
    if (!sid) return;
    await apiClient.post(`/mapcoder/session/${sid}/stop`);
    runProgress.value = 'canceled';
    running.value = false;
    stopSSE();
    stopFallbackPolling();
    sseStatus.value = 'idle';
    currentSessionId.value = null;
    sessionStatus.value = 'canceled';
    await openSession(sid);
  } catch (e) {
    showError(new Error('停止任务失败'));
  }
}

function downloadBack(content, filename) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  const name = filename.replace(/\s+/g, '_');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function inferFileExtension(text, declaredLang) {
  const lang = (declaredLang || '').toLowerCase();
  const sample = (text || '').slice(0, 800).toLowerCase();
  if (lang.includes('python') || sample.includes('import ') && sample.includes('def ')) return '.py';
  if (lang.includes('java') || sample.includes('public class') || sample.includes('static void main')) return '.java';
  if (lang.includes('c++') || lang.includes('cpp') || sample.includes('#include <')) return '.cpp';
  if (lang.includes('javascript') || lang.includes('js') || sample.includes('function ') || sample.includes('const ')) return '.js';
  if (lang.includes('typescript') || lang.includes('ts') || sample.includes('interface ') && sample.includes('export ')) return '.ts';
  if (lang.includes('go ') || lang === 'go' || sample.includes('package main')) return '.go';
  if (lang.includes('c#') || lang.includes('csharp') || sample.includes('namespace ') && sample.includes('class ')) return '.cs';
  if (lang.includes('php') || sample.includes('<?php')) return '.php';
  if (lang.includes('ruby') || sample.includes('def ') && sample.includes('end')) return '.rb';
  if (lang.includes('kotlin') || sample.includes('fun main(')) return '.kt';
  return '.txt';
}

function downloadFinalResult() {
  const fr = finalResult.value;
  if (!fr) return;
  const content = fr.code_str || fr.code || fr.text || JSON.stringify(fr, null, 2);
  const ext = inferFileExtension(content, fr.language || fr.lang || fr.meta?.language);
  downloadBack(content, `result${ext}`);
}

function startEdit() {
  if (!finalResult.value) return;
  editCode.value = finalResult.value.code_str || finalResult.value.code || '';
  isEditing.value = true;
  nextTick(() => {
    try {
      if (editEl.value && editEl.value.focus) editEl.value.focus();
    } catch (e) {}
    adjustTextareaHeight();
  });
}

function cancelEdit() {
  isEditing.value = false;
  editCode.value = '';
}

function onEditInput() {
  adjustTextareaHeight();
}

async function saveEdit() {
  if (!conversationId.value) {
    showError(new Error('没有激活的会话，无法保存'));
    return;
  }
  // update local state immediately
  const fr = finalResult.value || {};
  fr.code_str = String(editCode.value || '');
  fr.code = fr.code || fr.code_str;
  finalResult.value = fr;
  isEditing.value = false;
  try {
    const res = await apiClient.patch(`/mapcoder/session/${conversationId.value}`, {
      final_result: finalResult.value
    });
    const payload = res.data || {};
    // backend returns full session detail; normalize final_result
    if (payload.final_result) {
      finalResult.value = payload.final_result;
      finalResult.value.code_str = finalResult.value.code_str || finalResult.value.code;
      finalResult.value.code = finalResult.value.code || finalResult.value.code_str;
    }
    showInfo('保存成功');
  } catch (e) {
    console.error('saveEdit error', e);
    showError(new Error('保存失败'));
  }
}

// TODO: 更新finalResult.code为后端code_str
// TODO：接收后端output和comments等字段，完善运行结果展示
function runCodeWithAgent() {
  const sid = conversationId.value;
  if (!sid) {
    showError(new Error('没有激活的会话，无法运行代码'));
    return;
  }
  const fr = finalResult.value;
  const code = fr?.code_str || fr?.code || fr?.text || fr || '';
  if (!code || String(code).trim() === '') {
    showError(new Error('没有可运行的代码'));
    return;
  }
  const language = fr?.language || fr?.lang || 'python';
  // call backend endpoint
  (async () => {
    try {
      showInfo('正在在后台运行代码...');
      const res = await apiClient.post(`/mapcoder/session/${sid}/run_code`, {
        code: String(code),
        language,
        program_input: ''
      });
      if (res && res.data && res.data.final_result) {
        // normalize backend final_result: prefer code_str, code, output, comment
        const frx = res.data.final_result || {};
        frx.code_str = frx.code_str || frx.code || frx.code_str;
        frx.code = frx.code || frx.code_str;
        finalResult.value = frx;
        activeTab.value = 'overview';
        showInfo('代码运行完成，结果已更新');
      } else if (res && res.data && res.data.output) {
        // older style response fallback
        finalResult.value = { code: String(code), code_str: String(code), output: res.data.output, language };
        showInfo('代码运行完成，结果已更新');
      } else {
        showError(new Error('后端未返回运行结果'));
      }
    } catch (e) {
      console.error('runCodeWithAgent error', e);
      showError(new Error('运行代码失败'));
    }
  })();
}

function downloadTaskResult(t) {
  if (!t) return;
  const text = taskResultText(t);
  if (!text) return;
  const name = (t.title || 'task_result').replace(/\s+/g, '_');
  downloadBack(text, `${name}.txt`);
}

function copyTaskResult(t) {
  copyToClipboard(taskResultText(t));
}

// Add a helper to compute role color class (optional)
function roleColor(roleId) {
  // simple mapping by role name or id; roleId could be string or number
  const r = String(roleId || '').toLowerCase();
  if (r.includes('retriever') || r.includes('retrieve') || r === '1') return 'role-retriever';
  if (r.includes('planner') || r === '2') return 'role-planner';
  if (r.includes('coder') || r === '3') return 'role-coder';
  if (r.includes('debugger') || r === '4') return 'role-debugger';
  return 'role-default';
}

function getRoleName(roleId) {
  const r = String(roleId || '').toLowerCase();
  if (r.includes('retriever') || r.includes('retrieve') || r === '1') return 'retriever';
  if (r.includes('planner') || r === '2') return 'planner';
  if (r.includes('coder') || r === '3') return 'coder';
  if (r.includes('debugger') || r === '4') return 'debugger';
  return 'assistant';
}

// Update copyToClipboard to accept strings or objects (already handles strings)

onUnmounted(() => {
  stopPolling();
  stopSSE();
});

// Add helpers that were missing
function highlightCode(code) {
  try {
    const lang = (code && code.includes('class') && code.includes('public')) ? 'java' : 'plaintext';
    const res = hljs.highlight(code || '', {language: lang, ignoreIllegals: true});
    return res.value;
  } catch (e) {
    return (code || '').replace(/[&<>]/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;'}[c]));
  }
}

function formatMessage(text) {
  // minimal markdown renderer using MarkdownIt already instantiated as md
  try {
    return md.render(text || '');
  } catch (e) {
    return (text || '').replace(/[&<>]/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;'}[c]));
  }
}

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(String(text || ''));
    showInfo('已复制到剪贴板');
  } catch (e) {
    showError(new Error('复制失败'));
  }
}

// Handle incoming SSE payloads (status/log/task/message updates)
function handleSSEEvent(payload) {
  if (!payload || typeof payload !== 'object') return;
  if (payload.final_result) {
    finalResult.value = payload.final_result;
    activeTab.value = 'overview';
  }
  if (payload.session) {
    const s = payload.session;
    if (s.title) currentConversation.value = {...(currentConversation.value || {}), title: s.title, id: s.id};
    if (s.status) sessionStatus.value = s.status;
    const statusLower = (s.status || '').toLowerCase();
    if (sessionActiveStatuses.includes(statusLower)) {
      running.value = true;
    }
    if (s.status === 'completed' || s.status === 'failed' || s.status === 'canceled') {
      running.value = false;
      runProgress.value = s.status;
      stopPolling();
      stopSSE();
      stopFallbackPolling();
      sseStatus.value = 'idle';
    }
  }
  if (Array.isArray(payload.tasks)) applyTasks(payload.tasks);
  if (payload.task) {
    const id = Number(payload.task.id);
    const next = [...tasks.value];
    const idx = next.findIndex(t => Number(t.id) === id);
    if (idx >= 0) next.splice(idx, 1, payload.task);
    else next.push(payload.task);
    applyTasks(next);
  }
  if (Array.isArray(payload.logs)) {
    const existingIds = new Set(logs.value.map(l => Number(l.id)));
    payload.logs.forEach(l => {
      if (!existingIds.has(Number(l.id))) logs.value.push(l);
    });
  }
  if (payload.log) {
    const id = Number(payload.log.id);
    if (!logs.value.some(l => Number(l.id) === id)) logs.value.push(payload.log);
  }
}

// New helper to refresh tasks when Tasks tab selected so user can see progress even without SSE
async function refreshTasksPanel(force = false) {
  const sid = conversationId.value;
  if (!sid) return;
  if (!force && lastTasksRefreshSessionId === sid && tasks.value?.length) return;
  try {
    const res = await apiClient.get(`/mapcoder/session/${sid}`);
    const payload = res.data || {};
    tasks.value = payload.tasks || [];
    if (Array.isArray(payload.logs)) {
      logs.value = payload.logs;
    }
    if (payload.final_result) {
      finalResult.value = payload.final_result;
    }
    sessionStatus.value = payload.status || sessionStatus.value;
    lastTasksRefreshSessionId = sid;
  } catch (e) {
    console.warn('刷新任务面板失败', e);
  }
}

watch(activeTab, (tab) => {
  if (tab === 'tasks') {
    refreshTasksPanel(true);
  }
});

function isTaskCollapsed(id) {
  return collapsedTasks.value.has(Number(id));
}

function toggleTaskCollapse(id) {
  const nid = Number(id);
  const next = new Set(collapsedTasks.value);
  if (next.has(nid)) next.delete(nid); else next.add(nid);
  collapsedTasks.value = next;
}

function truncatedTaskResult(task, limit = 100) {
  const text = taskResultText(task) || '';
  if (text.length <= limit) return text;
  return text.slice(0, limit) + '…';
}

</script>

<style scoped>
:root {
  --btn-primary-start: #4f7df3;
  --btn-primary-end: #5888ff;
  --btn-accent-start: #1e53ff;
  --btn-accent-end: #2a84ec;
  --btn-danger-start: #ff6b6b;
  --btn-danger-end: #f2495e;
  --btn-copy-start: #3b82f6;
  --btn-copy-end: #5794ff;
  --btn-download-start: #22c55e;
  --btn-download-end: #2dd07f;
  --btn-hover-shadow: rgba(79, 125, 243, 0.25);
}

.ai-chat-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #f2f3f7;
  color: #1f1f1f;
}

.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 20px;
  background-color: #ffffff;
  border-bottom: 1px solid #d9dfe7;
}

.title {
  font-size: 18px;
  font-weight: 500;
}

.header-actions {
  display: flex;
  align-items: center;
}

.icon-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 8px;
  margin-left: 10px;
  border-radius: 50%;
  color: #4f7df3;
  transition: background 0.15s ease, transform 0.15s ease;
}

.icon-btn:hover:not(:disabled) {
  background: rgba(79, 125, 243, 0.2);
  transform: translateY(-1px);
}

.icon-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.draft {
  color: #28a745;
  margin-left: 10px;
}

.btn {
  padding: 8px 14px;
  margin-left: 10px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  background: linear-gradient(90deg, var(--btn-primary-start), var(--btn-primary-end));
  color: #fff;
  font-weight: 500;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 110px;
  max-width: 220px;
  white-space: nowrap;
}

.btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(79, 125, 243, 0.25);
}

.btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.run-btn {
  background: #2a84ec;
}

.run-btn:hover {
  background: #1b6dcc;
}


.stop-btn {
  background: #fa0636;
}

.run-progress {
  margin-left: 10px;
}

.tabs {
  display: flex;
  border-bottom: 1px solid #d9dfe7;
  background: #f6f8fb;
}

.tab {
  flex: 1;
  padding: 12px 0;
  text-align: center;
  cursor: pointer;
  border: none;
  background: transparent;
  color: #798598;
  font-weight: 600;
  transition: color 0.15s ease, background 0.15s ease;
}

.tab:hover {
  background: rgba(79, 125, 243, 0.1);
}

.tab.active {
  background-color: #ffffff;
  color: #1e2a44;
  box-shadow: inset 0 -2px 0 #4f7df3;
}

.panel {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

.overview-row {
  display: flex;
  flex-direction: column;
}

.prompt-card {
  background-color: #fff;
  border: 1px solid #dfe3eb;
  border-radius: 6px;
  padding: 15px;
  margin-bottom: 20px;
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.05);
}

.prompt-label {
  font-weight: 500;
  margin-bottom: 10px;
}

.prompt-textarea {
  width: 100%;
  border: 1px solid #cfd6e4;
  border-radius: 6px;
  padding: 10px;
  font-size: 14px;
  resize: vertical;
  min-height: 120px;
  max-height: 280px;
  color: #1f1f1f;
}

/* Code-like editor style for the editable final result */
.code-edit {
  background-color: #0b1220;
  color: #e6f0ff;
  border: 1px solid #26334a;
  border-radius: 8px;
  padding: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, 'Roboto Mono', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre;
  overflow: auto;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.02), 0 10px 26px rgba(2,6,23,0.35);
  caret-color: #7ee3ff;
  min-height: 80px;
  height: auto;
  resize: none;
  max-height: calc(100vh - 220px);
  transition: box-shadow 0.12s ease, border-color 0.12s ease;
  box-sizing: border-box;
}
.code-edit:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 12px 30px rgba(59,130,246,0.12);
}
.code-edit::placeholder {
  color: rgba(230,240,255,0.35);
}

/* Ensure displayed (non-edit) code blocks can scroll when very long */
.final-result .code-block,
.code-block.hljs {
  max-height: calc(60vh);
  overflow: auto;
  box-sizing: border-box;
}

.prompt-help {
  font-size: 12px;
  color: #6c757d;
  margin-top: 5px;
}

.final-result {
  background-color: #fff;
  border: 1px solid #dfe3eb;
  border-radius: 6px;
  padding: 15px;
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.05);
}

.artifact-meta {
  font-size: 12px;
  color: #6c757d;
  margin-bottom: 10px;
}

.code-actions {
  margin-bottom: 10px;
}

.code-block {
  background-color: #0f172a;
  color: #f8fafc;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
}

.task-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.task-item {
  background-color: #fff;
  border: 1px solid #dfe3eb;
  border-radius: 8px;
  padding: 15px;
  margin-bottom: 12px;
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.06);
  transition: border-color 0.15s ease, transform 0.15s ease;
}

.task-item:hover {
  border-color: #c3ccdd;
  transform: translateY(-1px);
}

.task-header {
  cursor: pointer;
}

.task-title {
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.task-toggle {
  width: 14px;
  height: 14px;
  border-radius: 3px;
  background: #dfe3eb;
  display: inline-block;
  position: relative;
  transition: background 0.15s ease;
}

.task-toggle::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 6px;
  height: 6px;
  border-right: 2px solid #4f5c74;
  border-bottom: 2px solid #4f5c74;
  transform: translate(-50%, -50%) rotate(-45deg);
}

.task-toggle.collapsed::after {
  transform: translate(-50%, -50%) rotate(45deg);
}

.task-body {
  margin-bottom: 10px;
}

.result {
  font-size: 14px;
  color: #333;
}

.collapsed-preview p {
  margin: 6px 0 0;
  color: #5c6579;
}

.task-actions {
  display: flex;
  justify-content: flex-end;
  gap: 16px;
}

.task-actions .btn {
  margin-left: 0;
  min-width: 95px;
}

.btn-copy {
  background: #0b0b49;
  margin-right: 8px;
}

.btn-download {
  background: #2f2f2f;
}

.btn {
  background: #0066ffff;
}
.btn:hover:not(:disabled) {
  background: #00388dff;
}
.logs-panel {
  background-color: #fff;
  border: 1px solid #dfe3eb;
  border-radius: 8px;
  padding: 15px;
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.05);
}

.log-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.log-item {
  border-bottom: 1px solid #e1e1e6;
  padding: 10px 0;
}

.log-meta {
  font-size: 12px;
  color: #6c757d;
  margin-bottom: 5px;
}

.log-msg {
  font-size: 14px;
  color: #333;
}

.log-payload {
  font-size: 12px;
  color: #6c757d;
  margin-top: 5px;
}

.prompt-params {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 12px;
}

.param-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 140px;
  flex: 1 1 200px;
}

.param-field label {
  font-size: 0.85rem;
  color: #4b5563;
}

.param-field select,
.param-field input {
  border: 1px solid rgba(148, 163, 184, 0.6);
  border-radius: 8px;
  padding: 8px 10px;
  background: #f5f6fb;
  color: #111827;
}
</style>

