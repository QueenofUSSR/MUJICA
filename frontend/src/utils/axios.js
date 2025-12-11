import axios from 'axios'
import { useAuthStore } from '@/stores/authStore'

// 创建axios实例
const apiClient = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器 - 自动添加token
apiClient.interceptors.request.use(
  (config) => {
    const authStore = useAuthStore()
    if (authStore.accessToken) {
      config.headers.Authorization = `Bearer ${authStore.accessToken}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器 - 处理 Token 过期
apiClient.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;
        const authStore = useAuthStore();
        if (error.response?.status === 401 && !originalRequest._retry) {
            originalRequest._retry = true;
            try {
                const newToken = await authStore.refreshToken();
                if (newToken) {
                    originalRequest.headers.Authorization = `Bearer ${newToken}`;
                    return apiClient(originalRequest);
                }
            } catch (refreshError) {
                console.error('刷新 Token 失败:', refreshError);
            }
            authStore.logout();
            window.location.href = '/login';
        }
        return Promise.reject(error);
    }
);


export default apiClient