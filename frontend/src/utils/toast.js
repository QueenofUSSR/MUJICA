// Toast工具函数 - 提供简洁的Toast调用方式
import { ref } from 'vue'

// 全局的Toast状态
export const toasts = ref([])
let toastId = 0

// 添加提示的核心函数
const addToast = (message, type = 'success', duration = 2000) => {
  const id = toastId++
  const toast = {
    id,
    message,
    type
  }

  toasts.value.push(toast)

  // 自动移除
  setTimeout(() => {
    removeToast(id)
  }, duration)

  return id
}

// 移除提示
export const removeToast = (id) => {
  const index = toasts.value.findIndex(toast => toast.id === id)
  if (index > -1) {
    toasts.value.splice(index, 1)
  }
}

// 导出便捷方法 - 可以直接导入使用
export const showToast = (message, type = 'success', duration = 2000) => {
  return addToast(message, type, duration)
}

export const showSuccess = (message, duration = 1500) => {
  return addToast(message, 'success', duration)
}

export const showError = (message, duration = 4000) => {
  return addToast(message, 'error', duration)
}

export const showWarning = (message, duration = 3000) => {
  return addToast(message, 'warning', duration)
}

export const showInfo = (message, duration = 2000) => {
  return addToast(message, 'info', duration)
}
export const handleError = (error)=>{
    console.error('操作失败:', error);
    const detail  = error.response?.data?.detail || error.message;
    if (error.response?.status === 404) {
        showInfo(detail || '请求的资源不存在');
    } else if (error.response?.status >= 500) {
        showError(detail || '服务器内部错误，请联系管理员');
    } else if (error.response?.status === 403) {
        showWarning(detail || '权限不足，请检查您的操作权限');
    } else if (error.code === 'NETWORK_ERROR') {
        showWarning(detail || '网络连接异常，请检查网络后重试');
    } else {
        showError(`操作失败: ${error.response?.data?.detail || error.message}`);
    }
}
