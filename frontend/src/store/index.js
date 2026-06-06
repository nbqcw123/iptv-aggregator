import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref(false)
  const theme = ref('dark')
  const userInfo = ref({
    name: 'Admin',
    avatar: '',
  })

  const sidebarWidth = computed(() => sidebarCollapsed.value ? '64px' : '220px')

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  return { sidebarCollapsed, theme, userInfo, sidebarWidth, toggleSidebar }
})

export const useChannelsStore = defineStore('channels', () => {
  const total = ref(0)
  const totalSources = ref(0)
  const validSources = ref(0)
  const todayAdded = ref(0)

  return { total, totalSources, validSources, todayAdded }
})
