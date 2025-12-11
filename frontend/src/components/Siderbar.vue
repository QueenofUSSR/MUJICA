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
        <span class="conv-title">历史对话</span>
      </div>
      <ul class="conv-list">
        <li v-for="c in conversations" :key="c.id" :class="['conv-item', {active: isActiveConversation(c.id)}]"
            @click="openConversation(c.id)">
          <div class="conv-title-row">{{ c.title || ('对话 ' + c.id) }}</div>
          <div class="conv-sub">
            {{ c.last_message ? (c.last_message.slice(0, 60) + (c.last_message.length > 60 ? '...' : '')) : '' }}
          </div>
        </li>
      </ul>
      <div class="conv-footer">
        <button class="btn-new" @click="onCreateNew" :disabled="creating">＋ 新建对话</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import {useRoute, useRouter} from 'vue-router';
import {onMounted, onUnmounted, ref, watch} from 'vue';
import apiClient from "@/utils/axios.js";
import {useAuthStore} from '@/stores/authStore';
import {useConversationStore} from '@/stores/conversationStore';

const route = useRoute();
const router = useRouter();
const isCollapsed = ref(false);
const authStore = useAuthStore();
const conversationStore = useConversationStore();
const conversations = ref([]);

const SIDEBAR_EXPANDED_WIDTH = '15%'; // when expanded (keep consistent with :root default)
const SIDEBAR_COLLAPSED_WIDTH = '45px'; // when collapsed

// helper to update CSS variable used by App.vue
const applySidebarWidthVar = (width) => {
  try {
    document.documentElement.style.setProperty('--sidebar-width', width);
  } catch (e) {
    // ignore in non-browser environments
  }
};

const isActiveConversation = (convId) => {
  const q = route.query?.conversation_id;
  const id = q ? parseInt(Array.isArray(q) ? q[0] : q) : null;
  if (id && !isNaN(id)) return id === convId;
  if (!id && conversations.value && conversations.value.length) return conversations.value[0].id === convId;
  return false;
};

const toggleCollapse = () => {
  isCollapsed.value = !isCollapsed.value;
  localStorage.setItem('sidebarCollapsed', isCollapsed.value);
  applySidebarWidthVar(isCollapsed.value ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_EXPANDED_WIDTH);
};

// Conversation list state & functions
const creating = ref(false);

async function loadConversations() {
  try {
    const payload = await conversationStore.fetchConversations();
    conversations.value = payload.conversations || [];
  } catch (e) {
    console.error('loadConversations failed', e);
  }
}

// keep local ref in sync with store changes
watch(() => conversationStore.conversations, (list) => {
  conversations.value = list || [];
}, { immediate: true });

async function openConversation(id) {
  try {
    await router.push({path: '/ai-chat', query: {conversation_id: id}});
  } catch (e) {
    console.error('openConversation router push failed', e);
  }
}

async function onCreateNew() {
  if (creating.value) return;
  creating.value = true;
  try {
    const res = await apiClient.post('/agent/conversation', { title: '新对话' });
    const data = res.data || {};
    await loadConversations();
    if (data && data.conversation_id) {
      await openConversation(data.conversation_id);
    } else if (conversations.value.length) {
      await openConversation(conversations.value[0].id);
    }
  } catch (e) {
    console.error('create conversation failed', e);
  } finally {
    creating.value = false;
  }
}

onMounted(() => {
  const savedState = localStorage.getItem('sidebarCollapsed');
  if (savedState !== null) {
    isCollapsed.value = savedState === 'true';
  }
  applySidebarWidthVar(isCollapsed.value ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_EXPANDED_WIDTH);
  // If already authenticated, load conversations now
  try {
    if (authStore && (authStore.accessToken || authStore.user)) {
      loadConversations();
    }
  } catch (e) {
    // ignore
  }
});

// Reload conversations when authentication becomes available
watch(() => authStore.accessToken, (token) => {
  if (token) loadConversations();
}, {immediate: true});

watch(() => authStore.user, (u) => {
  if (u) loadConversations();
}, {immediate: true});

onUnmounted(() => {
  try {
    document.documentElement.style.removeProperty('--sidebar-width');
  } catch (e) {
    // ignore in non-browser environments
  }
});
</script>

<style scoped>
.siderbar {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: var(--sidebar-width, 10%);
  min-height: calc(100vh - var(--navbar-height, 70px));
  background: linear-gradient(135deg, #3e1616 0%, #171616 100%);
  color: #ffffff;
  box-shadow: 2px 0 10px rgba(0, 0, 0, 0.1);
  transition: width 0.25s ease;
  z-index: 998; /* below navbar (1000) */
  overflow: auto; /* allow internal scrolling if content taller than viewport */
}

.siderbar.collapsed {
  width: 45px; /* keep collapsed width small */
}

.toggle-icon {
  display: flex;
  justify-content: flex-end;
  padding: 10px;
  margin-top: 70px;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.8);
  transition: all 0.3s ease;
}

.toggle-icon:hover {
  color: #ffffff;
}

.toggle-icon i {
  font-size: 1.2rem;
}

/* styling for the plain-text toggle symbol */
.toggle-symbol {
  font-size: 1.2rem;
  font-weight: 700;
  color: inherit;
  line-height: 1;
  user-select: none;
}

.menu-list {
  list-style: none;
  padding: 8px 0 6px 0;
}

.menu-list li {
  margin: 5px 0;
}

.menu-list a {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  color: rgba(255, 255, 255, 0.85);
  text-decoration: none;
  transition: all 0.3s ease;
}

.siderbar.collapsed .menu-list a {
  padding: 12px 8px;
}

.menu-list a:hover {
  background: rgba(255, 255, 255, 0.03);
  color: rgba(184, 212, 243, 0.95);
}

.menu-list a.active {
  background: rgba(255, 255, 255, 0.06);
  color: #f6d709;
}

.menu-list i {
  margin-right: 10px;
  font-size: 1.2rem;
}


.ai-conv-item .conv-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.ai-conv-item.active .conv-title {
  color: #2563eb;
}


.btn-new {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 10px;
  border: none;
  background: #f6d709;
  color: #4f4f4f;
  font-weight: 600;
  box-shadow: 0 6px 18px rgba(37,99,235,0.12);
  cursor: pointer;
  transition: transform 140ms cubic-bezier(.2,.9,.2,1), box-shadow 140ms ease, filter 140ms ease;
}

.conv-section {
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  height: calc(100vh - 170px); /* allow the section to use available vertical space */
}

.conv-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.conv-list {
  list-style: none;
  padding: 0;
  margin: 0;
  overflow: auto;
  flex: 1 1 auto;
}

.conv-footer {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 12px 0 6px 0;
}

.conv-item {
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.3s ease;
}

.conv-item:hover {
  background: rgba(255, 255, 255, 0.03);
}

/* Active conversation style: match menu-list a.active */
.conv-item.active {
  background: rgba(255, 255, 255, 0.06);
}

.conv-item.active .conv-title-row {
  color: #f6d709;
}

.conv-title-row {
  font-size: 0.95rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

.conv-sub {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.65);
  margin-top: 2px;
}

.btn-new:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.btn-new:hover {
  transform: translateY(-3px);
  background: #ffed75;
}

</style>