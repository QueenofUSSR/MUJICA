import {defineStore} from 'pinia'
import {nextTick, ref} from 'vue'
import router from '@/router'
import apiClient from '@/utils/axios';

export const useAuthStore = defineStore('auth', () => {
    const accessToken = ref(null);
    const user = ref(null);
    const isAuthenticated = ref(false);


    // 初始化认证信息
    const initAuth = async (token, userData) => {
        accessToken.value = token
        user.value = userData
        const avatarPath = userData.avatar ? userData.avatar : '/static/avatars/default-avatar.jpg';
        user.value.avatar = `${apiClient.defaults.baseURL}${avatarPath}?t=${new Date().getTime()}`;
        console.log("用户登录认证数据：", user);
        localStorage.setItem('access_token', token)
        localStorage.setItem('user', JSON.stringify(user.value))
        apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`
        isAuthenticated.value = true;
        try {
            await nextTick();
        } catch (e) {
            console.warn('initAuth: 下一帧触发计算失败', e);
        }
        await router.push('/overview');
    }

    // 更新头像
    const updateAvatar = (avatarPath) => {
        if (user.value) {
            user.value.avatar = `${apiClient.defaults.baseURL}${avatarPath}?t=${new Date().getTime()}`;
            localStorage.setItem('user', JSON.stringify(user.value));
        }
    }

    // 设置认证信息
    const setAuth = (token, userData) => {
        accessToken.value = token
        user.value = userData
        console.log("更新用户数据：", userData)
        if (userData && userData.avatar) {
            user.value.avatar = `${apiClient.defaults.baseURL}${userData.avatar}?t=${new Date().getTime()}`;
        } else if (userData) {
            user.value.avatar = `${apiClient.defaults.baseURL}/static/avatars/default-avatar.jpg?t=${new Date().getTime()}`;
        }
        localStorage.setItem('access_token', token)
        localStorage.setItem('user', JSON.stringify(user.value))
        apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`
    }

    // 检查token是否有效
    const checkTokenValid = () => {
        if (accessToken.value) {
            try {
                const payload = JSON.parse(atob(accessToken.value.split('.')[1]));
                if (!payload || !payload.exp) return 'expire';
                const expireTime = payload.exp * 1000; // 转换为毫秒
                const currentTime = Date.now();
                const remainingTime = expireTime - currentTime;
                return remainingTime > 0 ? 'valid' : 'expire';
            } catch (error) {
                console.error('解析 Token 失败:', error);
            }
        }
        return 'expire'
    }

    // 刷新token
    const refreshToken = async () => {
        if (!accessToken.value) {
            console.warn('已无有效的访问令牌，无法将其刷新');
            return null;
        }
        try {
            const response = await apiClient.post('/auth/refresh', {
                access_token: accessToken.value,
            });
            setAuth(response.data.new_token, user.value);
            if (response.data.new_token) {
                return response.data.new_token;
            }
        } catch (error) {
            console.error('Token刷新失败:', error);
        }
        return null;
    }

    // 登出
    const logout = async () => {
        isAuthenticated.value = false;
        accessToken.value = null;
        user.value = null;
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        delete apiClient.defaults.headers.common['Authorization'];
        await router.push('/login');
    }

    return {
        accessToken,
        user,
        isAuthenticated,
        initAuth,
        setAuth,
        checkTokenValid,
        refreshToken,
        logout,
        updateAvatar,
    }
})