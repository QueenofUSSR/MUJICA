import { reactive } from 'vue';

const themeStore = reactive({
  mode: localStorage.getItem('themeMode') || 'auto',
  setMode(mode) {
    this.mode = mode;
    localStorage.setItem('themeMode', mode);
    applyTheme(mode);
  }
});

function applyTheme(mode) {
  let theme = mode;
  if (mode === 'auto') {
    theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  document.documentElement.classList.remove('theme-light', 'theme-dark');
  document.documentElement.classList.add(`theme-${theme}`);
}

// 初始化
applyTheme(themeStore.mode);

// 监听系统主题变化
if (window.matchMedia) {
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
    if (themeStore.mode === 'auto') {
      applyTheme('auto');
    }
  });
}

export function useThemeStore() {
  return themeStore;
}

