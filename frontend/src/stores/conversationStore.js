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
        // ensure Authorization header present (fallback to localStorage token)
        try {
          const token = localStorage.getItem('access_token');
          if (token && !apiClient.defaults.headers.Authorization && !apiClient.defaults.headers.common?.Authorization) {
            apiClient.defaults.headers.common = apiClient.defaults.headers.common || {};
            apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`;
          }
        } catch (e) {}
        const tokenParam = (typeof window !== 'undefined' && localStorage.getItem('access_token')) ? localStorage.getItem('access_token') : null;
        const url = tokenParam ? `/mapcoder/session?token=${encodeURIComponent(tokenParam)}` : '/mapcoder/session';
        const res = await apiClient.get(url);
        const payload = res.data || [];
        const normalized = (Array.isArray(payload) ? payload : []).sort((a,b) => Number(b.id) - Number(a.id));
        this.setConversations(normalized);
        return { conversations: normalized };
      } catch (err) {
        this.error = err;
        throw err;
      } finally {
        this.loading = false;
      }
    }
  }
});
