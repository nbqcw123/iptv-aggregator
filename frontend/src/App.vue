<template>
  <el-container class="app-container">
    <!-- 左侧菜单 -->
    <el-aside :width="sidebarWidth" class="sidebar">
      <div class="logo-area">
        <div class="logo-icon">
          <el-icon :size="28" color="#06b6d4"><Monitor /></el-icon>
        </div>
        <transition name="fade">
          <div v-if="!sidebarCollapsed" class="logo-text">
            <span class="logo-title">IPTV</span>
            <span class="logo-sub">聚合管理系统</span>
          </div>
        </transition>
      </div>
      <el-menu
        :default-active="activeRoute"
        :collapse="sidebarCollapsed"
        :collapse-transition="false"
        router
        class="side-menu"
      >
        <el-menu-item
          v-for="route in menuRoutes"
          :key="route.path"
          :index="route.path"
        >
          <el-icon><component :is="route.meta.icon" /></el-icon>
          <template #title>{{ route.meta.title }}</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 主内容区 -->
    <el-container class="main-container">
      <!-- 顶部导航栏 -->
      <el-header class="top-header">
        <div class="header-left">
          <el-button
            text
            class="collapse-btn"
            @click="appStore.toggleSidebar"
          >
            <el-icon :size="20">
              <Fold v-if="!sidebarCollapsed" />
              <Expand v-else />
            </el-icon>
          </el-button>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="currentTitle !== '仪表盘'">
              {{ currentTitle }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-tooltip content="刷新" placement="bottom">
            <el-button text class="header-btn" @click="handleRefresh">
              <el-icon :size="18"><Refresh /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip content="设置" placement="bottom">
            <el-button text class="header-btn">
              <el-icon :size="18"><Setting /></el-icon>
            </el-button>
          </el-tooltip>
          <div class="user-info">
            <el-avatar :size="32" icon="UserFilled" />
            <span v-if="!sidebarCollapsed" class="user-name">{{ appStore.userInfo.name }}</span>
          </div>
        </div>
      </el-header>

      <!-- 内容区 -->
      <el-main class="content-main">
        <router-view v-slot="{ Component }">
          <transition name="fade-slide" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/store'

const appStore = useAppStore()
const route = useRoute()

const sidebarWidth = computed(() => appStore.sidebarWidth)

const menuRoutes = [
  { path: '/', meta: { title: '仪表盘', icon: 'Odometer' } },
  { path: '/channels', meta: { title: '频道管理', icon: 'Monitor' } },
  { path: '/sources', meta: { title: '源管理', icon: 'Connection' } },
  { path: '/search', meta: { title: '搜索任务', icon: 'Search' } },
  { path: '/export', meta: { title: '导出管理', icon: 'Download' } },
]

const activeRoute = computed(() => route.path)
const currentTitle = computed(() => route.meta?.title || '')

const handleRefresh = () => {
  window.location.reload()
}
</script>

<style scoped>
.app-container {
  height: 100vh;
}

.sidebar {
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.logo-area {
  height: 60px;
  display: flex;
  align-items: center;
  padding: 0 16px;
  border-bottom: 1px solid var(--border-color);
  gap: 12px;
  flex-shrink: 0;
}

.logo-icon {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, rgba(6, 182, 212, 0.2), rgba(59, 130, 246, 0.2));
  border: 1px solid rgba(6, 182, 212, 0.3);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.logo-text {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.logo-title {
  font-size: 18px;
  font-weight: 700;
  background: linear-gradient(135deg, #06b6d4, #3b82f6);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  line-height: 1.2;
}

.logo-sub {
  font-size: 10px;
  color: var(--text-muted);
  letter-spacing: 1px;
  white-space: nowrap;
}

.side-menu {
  padding: 8px 0;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
}

.side-menu :deep(.el-menu-item) {
  height: 48px;
  line-height: 48px;
  margin: 2px 8px;
  border-radius: 8px;
}

.side-menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(135deg, rgba(6, 182, 212, 0.15), rgba(59, 130, 246, 0.1)) !important;
  border-left: 3px solid var(--accent-cyan);
  border-radius: 8px 0 0 8px;
}

.main-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.top-header {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: var(--bg-secondary) !important;
  border-bottom: 1px solid var(--border-color) !important;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-left :deep(.el-breadcrumb__inner) {
  color: var(--text-secondary) !important;
}

.header-left :deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner) {
  color: var(--text-primary) !important;
}

.collapse-btn {
  color: var(--text-secondary) !important;
}

.collapse-btn:hover {
  color: var(--accent-cyan) !important;
  background-color: var(--glow-cyan) !important;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-btn {
  color: var(--text-secondary) !important;
  width: 36px;
  height: 36px;
}

.header-btn:hover {
  color: var(--accent-cyan) !important;
  background-color: var(--glow-cyan) !important;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-left: 8px;
  margin-left: 8px;
  border-left: 1px solid var(--border-color);
}

.user-name {
  font-size: 14px;
  color: var(--text-secondary);
}

.content-main {
  padding: 20px;
  overflow-y: auto;
  background: var(--bg-primary) !important;
}

/* 过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.2s ease;
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateX(10px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateX(-10px);
}
</style>
