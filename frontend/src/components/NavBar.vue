<template>
  <div class="navbar-wrapper">
    <!-- inline style ensures the transform is always applied even if CSS specificity varies -->
    <nav class="navbar" :class="{ 'navbar-hidden': isNavbarHidden }" :style="{ transform: isNavbarHidden ? 'translateY(-100%)' : 'translateY(0)' }">
      <div class="system-logo" @click="navigateToDashboard">
        Multi-Agent
      </div>
      <ul class="nav-list">
        <li v-for="route in menuItems" :key="route.name">
          <template  v-if="!route.children">
            <router-link :to="route.path" :class="{ 'router-link-active': isActive(route.path)}" >
              <font-awesome-icon :icon="route.icon" :class="{'dark-icon': !isDarkTheme, 'light-icon': isDarkTheme }"/>
              <div class="link-hover-effect"></div>
            </router-link>
          </template>
        </li>
        <li>
          <a
            href="javascript:void(0)"
            class="logout-link"
            @click.prevent="handleLogout"
          >
            <font-awesome-icon :icon="'sign-out-alt'"  :class="{ 'dark-icon': !isDarkTheme, 'light-icon': isDarkTheme }" />
            <div class="link-hover-effect"></div>
          </a>
        </li>
      </ul>
    </nav>
  </div>
</template>

<script setup>
import {useRoute, useRouter} from 'vue-router'
import {computed, onMounted, onUnmounted, ref} from 'vue';
import {useAuthStore} from '@/stores/authStore';
import { useThemeStore } from '@/stores/themeStore';

const themeStore = useThemeStore();
const isDarkTheme = computed(() => {
  if (themeStore.mode === 'auto') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  }
  return themeStore.mode === 'dark';
});

const authStore = useAuthStore();
const showLogout = ref(false);
const isNavbarHidden = ref(false);
// Init from current scroll to avoid jump on mount
const lastScrollY = ref(typeof window !== 'undefined' ? window.scrollY : 0);

// helper to read the real scrollTop from common roots
const getScrollY = () => {
  if (typeof window === 'undefined') return 0;
  const se = document.scrollingElement || document.documentElement || document.body;
  return (se && se.scrollTop) || window.scrollY || 0;
};

// rAF 节流与阈值，防止频繁切换或抖动
const lastKnownScrollY = ref(lastScrollY.value);
const ticking = ref(false);
const SCROLL_THRESHOLD = 10; // 忽略小于此像素的抖动
const SHOW_AT_TOP = 80; // 当滚动到顶部附近时总是显示导航栏

// 更稳健的滚动处理器：使用 requestAnimationFrame 节流并检测方向
const onScroll = () => {
  lastKnownScrollY.value = getScrollY();
  if (!ticking.value) {
    ticking.value = true;
    window.requestAnimationFrame(() => {
      const current = lastKnownScrollY.value;
      console.debug('[NavBar] onScroll rAF current=', current, 'last=', lastScrollY.value);
      const delta = current - lastScrollY.value;

      if (Math.abs(delta) > SCROLL_THRESHOLD) {
        if (current <= SHOW_AT_TOP) {
          // 接近页面顶部时显示
          isNavbarHidden.value = false;
        } else if (delta > 0) {
          // 向下滚动，隐藏
          isNavbarHidden.value = true;
        } else if (delta < 0) {
          // 向上滚动，显示
          isNavbarHidden.value = false;
        }
        lastScrollY.value = current;
      }

      ticking.value = false;
    });
  }
};

// 新增：右上角区域检测逻辑
function handleMouseMove(e) {
  const {clientX, clientY} = e;
  const w = window.innerWidth;
  const h = window.innerHeight;
  // 当鼠标靠近页面顶部时自动显示导航栏，避免用户找不到导航
  if (clientY < 60) {
    isNavbarHidden.value = false;
  }
  showLogout.value = clientX > w * 0.7 && clientY < h * 0.3;
}

// 触摸设备上的初始滚动记录（用于避免刚进入页面时导航栏跳动）
const handleTouchStart = () => {
  lastScrollY.value = getScrollY() || 0;
};

// 更稳健的滚轮处理器，补充在某些页面只触发 wheel 事件的情况
const onWheel = (e) => {
  const dy = e.deltaY || 0;
  console.debug('[NavBar] onWheel dy=', dy);
  if (Math.abs(dy) < 5) return; // 忽略微小滚动
  if (dy > 0) {
    // 向下滚，隐藏
    isNavbarHidden.value = true;
  } else {
    // 向上滚，显示
    isNavbarHidden.value = false;
  }
  // 保持 lastScrollY 与当前位置一致，避免后续 scroll 处理抖动
  lastScrollY.value = getScrollY() || lastScrollY.value;
};

onMounted(() => {
  // 初始化 scroll 位置，避免挂载时出现闪动
  lastScrollY.value = getScrollY() || 0;

  // determine best scroll container
  scrollContainer = findScrollableContainer();
  console.debug('[NavBar] detected scroll container:', scrollContainer);

  // 使用 passive listener 并绑定到常见滚动根，便于在容器滚动时也能捕获
  window.addEventListener('scroll', onScroll, {passive: true});
  document.addEventListener('scroll', onScroll, {passive: true});
  // also attach to documentElement and body to be robust across apps
  if (document.documentElement) document.documentElement.addEventListener('scroll', onScroll, {passive: true});
  if (document.body) document.body.addEventListener('scroll', onScroll, {passive: true});

  if (scrollContainer && scrollContainer !== document && scrollContainer !== window) {
    try {
      scrollContainer.addEventListener('scroll', onScroll, {passive: true});
    } catch (e) {
      console.debug('[NavBar] failed to attach to scrollContainer', e);
    }
  }

  // 监听 wheel（鼠标滚轮）来补充 scroll
  try {
    window.addEventListener('wheel', onWheel, {passive: true});
    document.addEventListener('wheel', onWheel, {passive: true});
    if (document.documentElement) document.documentElement.addEventListener('wheel', onWheel, {passive: true});
    if (document.body) document.body.addEventListener('wheel', onWheel, {passive: true});
    if (scrollContainer && scrollContainer !== document && scrollContainer !== window) {
      scrollContainer.addEventListener('wheel', onWheel, {passive: true});
    }
  } catch (e) {
    console.debug('[NavBar] wheel listener attach failed', e);
  }

  window.addEventListener('touchstart', handleTouchStart, {passive: true});
  window.addEventListener('touchmove', onScroll, {passive: true});
  window.addEventListener('mousemove', handleMouseMove);
});

onUnmounted(() => {
  window.removeEventListener('scroll', onScroll);
  document.removeEventListener('scroll', onScroll);
  if (document.documentElement) document.documentElement.removeEventListener('scroll', onScroll);
  if (scrollContainer && scrollContainer !== document && scrollContainer !== window && scrollContainer.removeEventListener) {
    try {
      scrollContainer.removeEventListener('scroll', onScroll);
    } catch (e) {
      console.debug('[NavBar] failed to remove from scrollContainer', e);
    }
  }

  // 移除 wheel 监听
  try {
    window.removeEventListener('wheel', onWheel);
    document.removeEventListener('wheel', onWheel);
    if (scrollContainer && scrollContainer !== document && scrollContainer !== window && scrollContainer.removeEventListener) {
      scrollContainer.removeEventListener('wheel', onWheel);
    }
  } catch (e) {
    console.debug('[NavBar] wheel listener remove failed', e);
  }

  window.removeEventListener('touchstart', handleTouchStart);
  window.removeEventListener('touchmove', onScroll);
  window.removeEventListener('mousemove', handleMouseMove);

  console.debug('[NavBar] unmounted');
});

// helper to find a likely scrollable container in the app
const findScrollableContainer = () => {
  if (typeof document === 'undefined') return null;
  const candidates = ['#app', '.app', '#root', '#main', '.main'];
  for (const sel of candidates) {
    const el = document.querySelector(sel);
    if (el) return el;
  }
  // fallback: check document.scrollingElement
  if (document.scrollingElement) return document.scrollingElement;
  // otherwise find first child of body that actually scrolls
  for (const child of Array.from(document.body.children)) {
    try {
      if (child.scrollHeight > child.clientHeight) return child;
    } catch (e) {
      // ignore
    }
  }
  // ultimate fallback: body
  return document.body;
};

let scrollContainer = null;

const route = useRoute()
const router = useRouter();

const navigateToDashboard = () => {
  router.push('/ai-chat');
};

const isActive = (path) => {
  return route.path === path || route.path.startsWith(path + '/');
}

const handleLogout = async () => {
  try {
    await authStore.logout();
  } catch (e) {
    console.error('退出登录过程中出错：', e);
    router.push('/login').catch(() => {});
  }
};

const menuItems = computed(() => {
  return [
    { name: 'profile', path: '/profile', label: '个人中心', icon: 'user' },

    // 新增：MCP 配置入口
    // icon 建议先用你已确认存在的 'user'，避免 fontawesome 没注册导致不显示
    { name: 'mcp', path: '/mcp', label: 'MCP', icon: 'user' },
  ];
})



</script>

<style scoped>
.navbar-wrapper {
  position: relative;
  height: 70px;
}

.navbar {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 60px;
  background: linear-gradient(135deg, #b1bfe5 0%, #fffcfc 50%, #e8e0ae 100%);
  z-index: 1000;
  overflow: visible;
  transform: translateY(0);
  transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  align-items: center;
}
.dark-theme .navbar {
  background: linear-gradient(135deg, #3e1617 0%, #1a1542 50%, #052142 100%);
}

  /* NavBar隐藏状态 */
.navbar-hidden {
  transform: translateY(-100%);
}

.system-logo {
  font-family: 'Playfair Display', serif;
  font-weight: 750;
  font-size: 1.4rem;
  color: #141415;
  cursor: pointer;
  margin-left: 2rem;
  transition: all 0.3s ease;
  text-shadow: 0 0 20px rgba(255, 255, 255, 0.5);
  height: fit-content;
  width: 240px;
}
.dark-theme .system-logo {
  color: #ffffff;
}

.system-logo:hover {
  transform: scale(1.05);
  text-shadow: 0 0 30px rgba(255, 255, 255, 0.8);
}

.nav-list {
  list-style: none;
  display: flex;
  justify-content: flex-end;
  flex-grow: 1;
  margin: 0;
  padding: 0;
  width: 100%;
  height: 100%;
}

.nav-list li {
  position: relative;
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 45px;
  max-width: 60px;
}

.nav-list a {
  display: flex;
  justify-content: center;
  align-items: center;
  color: rgba(255, 255, 255, 0.9);
  text-decoration: none;
  font-weight: 500;
  padding: 0 15px;
  height: 100%;
  transition: all 0.3s ease;
  font-size: 1rem;
  position: relative;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(10px);
  width: 100%;
  box-sizing: border-box;
}

.nav-list a:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.15);
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.2);
}
.dark-icon {
  color: #333; /* 浅色模式下的深色图标 */
}

.light-icon {
  color: #fff; /* 深色模式下的浅色图标 */
}


.dropdown-menu li {
  padding: 0;
  margin: 0;
  width: 100%;
}

.dropdown-menu li:first-child a {
  border-radius: 0 0 0 0;

}

.dropdown-menu li:last-child a {
  border-bottom: none;
  border-radius: 0 0 0 0;

}

.dropdown-menu a {
  display: block;
  color: rgba(255, 255, 255, 0.8);
  text-decoration: none;
  font-weight: 500;
  padding: 14px 20px; /* 增加左右内边距 */
  transition: all 0.3s ease;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  position: relative;
  overflow: hidden;
  width: 100%;
  box-sizing: border-box;
  text-align: left;
  white-space: nowrap;
  text-overflow: ellipsis;
  margin: 0;
}

.dropdown-menu a:hover {
  color: #fff;
  background: linear-gradient(90deg, rgba(138, 43, 226, 0.2), rgba(75, 0, 130, 0.2));
  padding: 14px 0;
}

.dropdown-menu a::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  width: 4px; /* 增加紫色条的宽度 */
  background: linear-gradient(180deg, #8a2be2, #4b0082);
  transform: scaleY(0);
  transition: transform 0.3s ease;
}

.dropdown-menu a:hover::before {
  transform: scaleY(1);
}

.dropdown-menu a .link-text {
  display: inline-block;
  width: 100%;
  padding-left: 10px;
  box-sizing: border-box;
  position: relative;
  z-index: 1;
  word-break: break-all;
}

.dropdown-menu a:hover .link-text {
  padding-left: 20px;
}

.link-text {
  color: #000;
  text-shadow: none;
  transition: all 0.3s ease;
  overflow: hidden;
  word-break: break-all;
  white-space: normal
}
.dark-theme .link-text {
  color: #fff;
}

.nav-list a.router-link-active .link-text {
  color: #2b084d;
  text-shadow: 0 0 15px rgba(138, 43, 226, 0.5);
}
.dark-theme .nav-list a.router-link-active .link-text {
  color: #e5d56d;
}


.link-hover-effect {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.1), transparent);
  transform: translateX(-100%);
  opacity: 0;
  transition: all 0.2s ease;
}

.nav-list a:hover .link-hover-effect,
.dropdown-trigger:hover .link-hover-effect {
  transform: translateX(100%);
  opacity: 1;
}


@media (max-width: 576px) {
  .navbar {
    padding: 0 0.5rem;
  }

  .system-logo {
    font-size: 1.1rem;
    margin-right: 0.5rem;
  }

  .nav-list li {
    min-width: 75px;
  }

  .dropdown-menu a {
    padding: 10px 15px;
    font-size: 0.8rem;
  }
}
</style>