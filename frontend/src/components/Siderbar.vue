<template>
  <div class="siderbar" :class="{ 'collapsed': isCollapsed }">
    <div class="toggle-icon" @click="toggleCollapse">
      <span class="toggle-symbol" aria-hidden="true">
        <img
            :src="apiClient.defaults.baseURL + '/static/icons/' + (isCollapsed ? 'siderbar-right.png' : 'siderbar-left.png')"
            alt="toggle"
            style="width:1.2rem; height:auto; display:inline-block;"
        />
      </span>
    </div>
    <div v-if="!isCollapsed" class="conv-section">
      <div class="conv-header">
          <input class="conv-search" v-model="q" placeholder="搜索会话" @input="applyFilter" />
          <button class="btn-new" @click="onCreateNew" :disabled="creating">＋ 新建任务</button>
      </div>
      <ul class="conv-list">
        <li v-for="c in filteredConversations" @click="openConversation(c.id)" :key="c.id" :class="['conv-item', {active: isActiveConversation(c.id)}]">
          <div class="conv-main">
            <div class="conv-title-row">{{ c.title || ('对话 ' + c.id) }}</div>
            <div class="conv-sub">
              {{ c.last_message ? (c.last_message.slice(0, 60) + (c.last_message.length > 60 ? '...' : '')) : '' }}
            </div>
          </div>
          <div class="conv-meta">
            <div class="meta-top">{{ c.model_id || '' }}</div>
            <div class="meta-bottom">{{ formatTime(c.updated_at) }}</div>
            <div class="actions">
              <button class="action" title="重命名" @click.stop="renameConversation(c)">✎</button>
              <button class="action" title="删除" @click.stop="confirmDelete(c)">🗑</button>
            </div>
          </div>
        </li>
      </ul>
      <div class="conv-footer">
        <div class="footer-left">共 {{ conversations.length }} 会话</div>
        <div class="footer-right">
          <button class="btn-small" @click="loadConversations">刷新</button>
        </div>
      </div>
    </div>

    <!-- Delete confirm modal -->
    <div v-if="showDeleteConfirm" class="modal-overlay" @click.self="cancelDelete">
      <div class="modal">
        <div class="modal-body">确认删除会话 "{{ deleting?.title }}" 吗？此操作不可恢复。</div>
        <div class="modal-actions">
          <button class="btn" @click="cancelDelete">取消</button>
          <button class="btn btn-danger" @click="doDelete">确认删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import {useRoute, useRouter} from 'vue-router';
import {onMounted, onUnmounted, ref, watch, computed} from 'vue';
import apiClient from "@/utils/axios.js";
import {useAuthStore} from '@/stores/authStore';
import {useConversationStore} from '@/stores/conversationStore';

const route = useRoute();
const router = useRouter();
const isCollapsed = ref(false);
const authStore = useAuthStore();
const conversationStore = useConversationStore();
const conversations = ref([]);
const q = ref('');
const filteredConversations = computed(() => {
  if (!q.value) return conversations.value || [];
  const key = q.value.toLowerCase();
  return (conversations.value || []).filter(c => (c.title || '').toLowerCase().includes(key) || (c.last_message || '').toLowerCase().includes(key));
});

const SIDEBAR_EXPANDED_WIDTH = '15%';
const SIDEBAR_COLLAPSED_WIDTH = '45px';

const applySidebarWidthVar = (width) => {
  try { document.documentElement.style.setProperty('--sidebar-width', width); } catch (e) {}
};

const isActiveConversation = (convId) => {
  const qv = route.query?.session_id;
  const id = qv ? parseInt(Array.isArray(qv) ? qv[0] : qv) : null;
  if (id && !isNaN(id)) return id === convId;
  if (!id && conversations.value && conversations.value.length) return conversations.value[0].id === convId;
  return false;
};

const toggleCollapse = () => {
  isCollapsed.value = !isCollapsed.value;
  localStorage.setItem('sidebarCollapsed', isCollapsed.value);
  applySidebarWidthVar(isCollapsed.value ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_EXPANDED_WIDTH);
};

const creating = ref(false);
const showDeleteConfirm = ref(false);
const deleting = ref(null);

async function loadConversations() {
  try {
    // use conversation-centric list with current auth token
    const token = authStore.accessToken;
    const url = token ? `/mapcoder/session?token=${encodeURIComponent(token)}` : '/mapcoder/session';
    const res = await apiClient.get(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    });
    const list = Array.isArray(res.data) ? res.data : [];
    const normalized = list.sort((a,b) => Number(b.id) - Number(a.id));
    conversationStore.setConversations(normalized);
    conversations.value = normalized;
    if (conversations.value && conversations.value.length) {
      const qv = route.query?.session_id;
      if (!qv) openConversation(conversations.value[0].id);
    }
  } catch (e) { console.error('loadConversations failed', e); }
}

watch(() => conversationStore.conversations, (list) => { conversations.value = list || []; }, { immediate: true });

async function openConversation(id) {
  try { await router.push({path: '/overview', query: {session_id: id}}); } catch (e) { console.error('openConversation router push failed', e); }
}

async function onCreateNew() {
  if (creating.value) return; creating.value = true;
  try {
    const apiResp = await apiClient.post('/mapcoder/session', { title: '', prompt: null });
    const data = apiResp.data || {};
    if (data && data.id) {
      const newItem = {
        id: data.id,
        title: data.title || `任务 ${data.id}`,
        last_message: data.metadata?.prompt || '',
        updated_at: data.updated_at || new Date().toISOString(),
        status: data.status,
      };
      const existing = conversationStore.conversations || [];
      conversationStore.setConversations([newItem, ...existing]);
      conversations.value = [newItem, ...(conversations.value || [])];
      await openConversation(data.id);
      return;
    }
    await loadConversations();
    if (data && data.id) await openConversation(data.id);
    else if (conversations.value.length) await openConversation(conversations.value[0].id);
  } catch (e) { console.error('create conversation failed', e); } finally { creating.value = false; }
}

function applyFilter() { /* computed handles filtering */ }

function formatTime(t) {
  if (!t) return '';
  try { const d = new Date(t); return d.toLocaleString(); } catch (e) { return t; }
}

async function renameConversation(c) {
  const nv = prompt('输入新会话标题', c.title || '');
  if (!nv || nv.trim() === '') return;
  try {
    await apiClient.patch(`/mapcoder/conversation/${c.id}`, { title: nv });
    await loadConversations();
    await openConversation(c.id);
  } catch (e) { console.error('rename failed', e); }
}

function confirmDelete(c) { deleting.value = c; showDeleteConfirm.value = true; }
function cancelDelete() { deleting.value = null; showDeleteConfirm.value = false; }

async function doDelete() {
  if (!deleting.value) return; const id = deleting.value.id; showDeleteConfirm.value = false;
  try {
    await apiClient.delete(`/mapcoder/session/${id}`);
    // Immediately remove from local lists to avoid showing stale item
    conversationStore.removeConversationById(id);
    conversations.value = (conversations.value || []).filter(c => Number(c.id) !== Number(id));
    await loadConversations();
    const qv = route.query?.session_id; if (qv && parseInt(Array.isArray(qv) ? qv[0] : qv) === id) {
      // open latest if exists
      if (conversations.value.length) await openConversation(conversations.value[0].id);
      else await router.push({ path: '/overview' });
    }
  } catch (e) { console.error('delete failed', e); }
}

onMounted(() => {
  const savedState = localStorage.getItem('sidebarCollapsed');
  if (savedState !== null) isCollapsed.value = savedState === 'true';
  applySidebarWidthVar(isCollapsed.value ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_EXPANDED_WIDTH);
  try { if (authStore && (authStore.accessToken || authStore.user)) loadConversations(); } catch (e) {}
});

watch(() => authStore.accessToken, (token) => { if (token) loadConversations(); }, {immediate: true});
watch(() => authStore.user, (u) => { if (u) loadConversations(); }, {immediate: true});

onUnmounted(() => { try { document.documentElement.style.removeProperty('--sidebar-width'); } catch (e) {} });
</script>

<style scoped>
.siderbar { position: fixed; top: 0; left: 0; bottom: 0; width: var(--sidebar-width, 10%); min-height: calc(100vh - var(--navbar-height, 70px)); /* improved background for contrast */ background: linear-gradient(180deg, #071227 0%, #071a2a 100%); color: #e6eef8; box-shadow: 2px 0 10px rgba(0, 0, 0, 0.12); transition: width 0.25s ease; z-index: 998; overflow: auto; }
.siderbar.collapsed { width: 45px; }
.toggle-icon { display: flex; justify-content: flex-end; padding: 10px; margin-top: 70px; cursor: pointer; color: rgba(230,238,248,0.85); transition: all 0.3s ease; }
.toggle-icon:hover { color: #ffffff; }
.conv-section { padding: 12px; display: flex; flex-direction: column; height: calc(100vh - 170px); }
.conv-header { display: flex; flex-direction: column; align-items: center; margin-bottom: 8px; }
.conv-search { margin-left:8px; padding:6px 8px; border-radius:6px; border: 1px solid rgba(255,255,255,0.06); background: rgba(255,255,255,0.02); color: #e6eef8; }
.conv-search::placeholder { color: rgba(230,238,248,0.6); }
.btn-new { padding:8px 12px; border-radius:8px; background:linear-gradient(90deg,#ffd86b,#f6d709); color:#081023; font-weight:700; border:none; cursor:pointer; box-shadow:0 6px 18px rgba(0,0,0,0.08); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; display:inline-flex; align-items:center; justify-content:center; height:36px; }
.btn-new:disabled { opacity:0.6; cursor:not-allowed; }
.btn-new:hover { transform: translateY(-1px); box-shadow:0 8px 20px rgba(0,0,0,0.12); }
.conv-list { list-style:none; padding:0; margin:0; overflow:auto; flex:1 1 auto; }
.conv-item { display:flex; flex-direction: column; align-items:flex-start; padding:10px 8px; border-radius:6px; cursor:pointer; transition:background 0.18s ease, transform 0.08s ease; min-height:56px; }
.conv-item:hover { background: rgba(255,255,255,0.02); transform: translateY(-1px); }
.conv-item.active { background: rgba(59,130,246,0.08); border-left:4px solid #3b82f6; padding-left:6px; }
.conv-main { flex:1; padding-right:8px; }
.conv-title-row { font-size:0.96rem; font-weight:700; color:#f1f5f9; line-height:1.2; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.conv-sub { font-size:12px; color:rgba(230,238,248,0.72); margin-top:6px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.conv-meta { width:86px; display:flex; flex-direction:row; align-items:flex-end; gap:6px; }
.meta-top { font-size:12px; color:rgba(230,238,248,0.6); background: rgba(255,255,255,0.02); padding:2px 6px; border-radius:6px; }
.meta-bottom { font-size:11px; color:rgba(230,238,248,0.5); }
.actions { display:flex; gap:6px; }
.action { background:transparent; border:none; color:rgba(230,238,248,0.78); cursor:pointer; padding:6px; border-radius:6px; }
.action:hover { background: rgba(255,255,255,0.03); color:#ffffff; }
.modal-overlay { position:fixed; inset:0; background:rgba(0,0,0,0.6); display:flex; align-items:center; justify-content:center; z-index:2000; }
.modal { background:#fff; padding:16px; border-radius:8px; min-width:320px; }
.modal-body { margin-bottom:12px; }
.modal-actions { display:flex; justify-content:flex-end; gap:8px; }
.btn-small { padding:6px 8px; border-radius:6px; border:none; background:#e6eef8; color:#071227; cursor:pointer; }
.btn-danger { background:#ef4444; color:#fff; border:none; padding:8px 12px; border-radius:6px; cursor:pointer; }
.conv-footer { display:flex; justify-content:space-between; align-items:center; padding:12px 0 6px 0; color:rgba(230,238,248,0.85); }
</style>