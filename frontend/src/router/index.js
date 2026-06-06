import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '@/views/Dashboard.vue'

const routes = [
  {
    path: '/',
    name: 'dashboard',
    component: Dashboard,
    meta: { title: '仪表盘', icon: 'Odometer' },
  },
  {
    path: '/channels',
    name: 'channels',
    component: () => import('@/views/Channels.vue'),
    meta: { title: '频道管理', icon: 'Monitor' },
  },
  {
    path: '/sources',
    name: 'sources',
    component: () => import('@/views/Sources.vue'),
    meta: { title: '源管理', icon: 'Connection' },
  },
  {
    path: '/search',
    name: 'search',
    component: () => import('@/views/SearchTask.vue'),
    meta: { title: '搜索任务', icon: 'Search' },
  },
  {
    path: '/export',
    name: 'export',
    component: () => import('@/views/Export.vue'),
    meta: { title: '导出管理', icon: 'Download' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
