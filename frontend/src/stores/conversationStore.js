import { defineStore } from 'pinia';
import apiClient from '@/utils/axios';

export const useConversationStore = defineStore('conversation', {
  state: () => ({
    conversations: [],
    loading: false,
    error: null
  }),
  actions: {
    setConversations(list) {
      this.conversations = Array.isArray(list) ? list : [];
    },
    removeConversationById(id) {
      const numericId = Number(id);
      if (Number.isNaN(numericId)) return;
      this.conversations = (this.conversations || []).filter(c => Number(c.id) !== numericId);
    },
    async fetchConversations() {
      this.loading = true;
      this.error = null;
      try {
        const res = await apiClient.get('/agent');
        const payload = res.data || {};
        this.setConversations(payload.conversations || []);
        return payload;
      } catch (err) {
        this.error = err;
        throw err;
      } finally {
        this.loading = false;
      }
    }
  }
});

