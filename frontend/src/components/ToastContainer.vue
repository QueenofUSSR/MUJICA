<template>
  <teleport to="body">
    <div class="toast-container">
      <transition-group name="toast" tag="div">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          :class="['toast']"
          :style="getToastStyle(toast.type)"
          @click="removeToast(toast.id)"
        >
          {{ toast.message }}
        </div>
      </transition-group>
    </div>
  </teleport>
</template>

<script setup>
import { getCurrentInstance, provide } from 'vue'
import { toasts, removeToast, showToast, showSuccess, showError, showWarning, showInfo } from '@/utils/toast'

// 获取不同类型Toast的内联样式
const getToastStyle = (type) => {
  const baseStyle = {
    padding: '12px 24px',
    marginBottom: '10px',
    borderRadius: '6px',
    color: 'white',
    fontSize: '14px',
    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
    cursor: 'pointer',
    pointerEvents: 'auto',
    minWidth: '200px',
    maxWidth: '400px',
    wordBreak: 'break-word',
    backdropFilter: 'blur(10px)',
    textAlign: 'center',
    border: 'none'
  }

  const gradientStyles = {
    success: {
      background: 'linear-gradient(135deg, #4caf50, #026205)'
    },
    error: {
      background: 'linear-gradient(120deg, #c01549, #7c0202)'
    },
    warning: {
      background: 'linear-gradient(120deg, #c2ad57, #ffd700)'
    },
    info: {
      background: 'linear-gradient(120deg, #1b7eda, #0414c0)'
    }
  }

  return {
    ...baseStyle,
    ...(gradientStyles[type] || gradientStyles.success)
  }
}

// 导出便捷方法到全局 (保持向后兼容)
const instance = getCurrentInstance()
if (instance) {
  const app = instance.appContext.app

  app.config.globalProperties.$showToast = showToast
  app.config.globalProperties.$showSuccess = showSuccess
  app.config.globalProperties.$showError = showError
  app.config.globalProperties.$showWarning = showWarning
  app.config.globalProperties.$showInfo = showInfo
}

provide('toast', {
  show: showToast,
  success: showSuccess,
  error: showError,
  warning: showWarning,
  info: showInfo
})
</script>

<style>
/* 使用全局样式而不是scoped，确保动态类名能正确应用 */
.toast-container {
  position: fixed;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 9999;
  pointer-events: none;
  display: flex;
  flex-direction: column;
  align-items: center;
}

/* Vue transition-group 过渡效果 - 从顶部滑入 */
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from,
.toast-leave-to {
  transform: translateY(-100%);
  opacity: 0;
}

.toast-move {
  transition: transform 0.3s ease;
}

/* 悬停效果 */
.toast:hover {
  transform: scale(1.02);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25);
}
</style>
