import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import { pinia } from "../main";
import LoginView from "@/views/LoginView.vue";
import ProfileView from "@/views/ProfileView.vue";
import AIChatView from '@/views/AIChatView.vue';

// 1) 新增：导入 MCP 页面
import MCPView from "@/views/MCPView.vue";

const routes = [{ path: '/login', component: LoginView }, {
    path: '/profile', component: ProfileView
},
{ path: '/ai-chat', component: AIChatView },
// 2) 新增：MCP 路由
{ path: '/mcp', component: MCPView }
]

const router = createRouter({
    history: createWebHistory(import.meta.env.BASE_URL), routes
})
const publicRoutes = ['/login', '/docs']


// 路由守卫 - 保护需要认证的路由
router.beforeEach((to, from, next) => {
    const authStore = useAuthStore(pinia);
    if (to.path === '' || publicRoutes.includes(to.path)) {
        return next();
    }
    if (!authStore.isAuthenticated) {
        return next('/login');
    }
    next();
})

export default router