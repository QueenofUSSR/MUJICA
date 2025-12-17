<template>
  <NavBar v-if="isAuthedPage" ref="navBar"/>
  <div class="app-layout">
    <Siderbar v-if="isAuthedPage" ref="siderBar"/>
    <div
        class="content-wrapper"
        :style="{
        marginLeft: isAuthedPage ? 'var(--sidebar-width)' : '0',
        paddingTop: '0',
        height: '100%'
      }"
    >
    <router-view v-slot="{ Component }">
      <component :is="Component" ref="currentComponent"/>
    </router-view>
    </div>
    <ToastContainer/>
  </div>
</template>

<script setup>
import {RouterView, useRoute} from 'vue-router';
import NavBar from '@/components/NavBar.vue';
import Siderbar from '@/components/Siderbar.vue';
import ToastContainer from '@/components/ToastContainer.vue';
import {computed, ref, watch} from 'vue';

const navBar = ref(null);
const isEditing = ref(false);
const currentComponent = ref(null);
const route = useRoute();
const isAuthedPage = computed(() => route.path !== '/' && route.path !== '/login');

watch(() => route.path, () => {
  isEditing.value = false;
  setTimeout(() => {
    if (currentComponent.value) {
      if (typeof currentComponent.value.fetchData === 'function') {
        try {
          currentComponent.value.fetchData();
        } catch (error) {
          console.error('调用 fetchData 时出错：', error);
        }
      }
    }
  }, 10);
}, {immediate: false});


</script>


<style>
@import url('https://fonts.googleapis.com/css2?family=Lora:wght@500;700&family=Playfair+Display:wght@600;800&display=swap');

:root {
  /* default width so CSS variables resolve during build/lint */
  --sidebar-width: 10%;
  --navbar-height: 70px; /* 默认导航栏高度 */
}

/* Ensure the document and root app element fill the viewport so children using 100vh/dvh behave correctly */
html, body, #app {
  height: 100%;
  width: 100vw;
  overflow-x: hidden;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: 'Lora', serif;
  font-weight: 500;
  font-size: 1.2rem;
  line-height: 1.6;
  color: #ffffff;
  background: linear-gradient(180deg, #0a0a23 0%, #1b1b4f 100%);
  overflow-x: hidden;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
}

.app-layout {
  display: block; /* let sidebar be fixed; content wrapper will be positioned */
  min-height: 100%;
  width: 100%;
  margin: 0;
  padding: 0;
  position: relative;
  background: linear-gradient(120deg, #f8f1f1 0%, #fadcb3 100%);

}

.dark-theme .app-layout {
  background: linear-gradient(120deg, #3e1617 0%, #1a1542 100%);
}

.content-wrapper {
  margin-left: var(--sidebar-width, 0);
  transition: margin-left 0.25s ease;
  box-sizing: border-box;
  height: 100%;
}

main {
  flex: 1;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 10px;
  position: relative;
  width: 100%;
  max-width: 1200px; /* keep content centered and readable */
}

/* 表格样式（保持不变） */
table {
  width: 100%;
  border-collapse: collapse;
  background: #ffffff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
}

th, td {
  padding: 0.8rem;
  text-align: left;
  color: #333333;
  font-family: 'Lora', serif;
  font-weight: 500;
  font-size: 1.1rem;
  text-shadow: none;
}

th {
  background: #e0e0e0;
  font-weight: 700;
}

tr:nth-child(even) {
  background: #f9f9f9;
}

tr:hover {
  background: #e6f0fa;
}

td {
  border-bottom: 1px solid #ddd;
}

/* 响应式调整 */
@media (max-width: 768px) {
  body {
    font-size: 1rem;
  }

  h1 {
    font-size: 2rem;
  }

  .content-wrapper {
    margin-left: 0; /* on small screens let the sidebar overlay or be hidden */
    padding-top: 60px;
  }
}
</style>