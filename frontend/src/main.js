import './assets/main.css'
import './assets/shared-form-styles.css'
import { library } from '@fortawesome/fontawesome-svg-core';
import { faHome, faBell, faCog, faUser, faSignOutAlt } from '@fortawesome/free-solid-svg-icons';
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome';
import { createApp } from 'vue'
import { createPinia } from 'pinia' // 导入 Pinia
import App from './App.vue'
import router from './router'


const app = createApp(App)
library.add(faHome, faBell, faCog, faUser, faSignOutAlt);

// 全局注册 FontAwesomeIcon 组件
app.component('font-awesome-icon', FontAwesomeIcon);

// 先安装 Pinia
export const pinia = createPinia()
app.use(pinia)

// 再启用路由
app.use(router)

app.mount('#app')