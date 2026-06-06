import request from './request'

/**
 * 搜索任务相关 API
 */
export const searchApi = {
  // 获取搜索任务列表
  getTasks(params) {
    return request.get('/search/tasks', { params })
  },

  // 获取任务详情
  getTaskDetail(id) {
    return request.get(`/search/tasks/${id}`)
  },

  // 启动自动搜索
  startAutoSearch(data) {
    return request.post('/search/auto', data)
  },

  // 启动自定义搜索
  startCustomSearch(data) {
    return request.post('/search/custom', data)
  },

  // 停止搜索任务
  stopTask(id) {
    return request.post(`/search/tasks/${id}/stop`)
  },

  // 暂停搜索任务
  pauseTask(id) {
    return request.post(`/search/tasks/${id}/pause`)
  },

  // 恢复搜索任务
  resumeTask(id) {
    return request.post(`/search/tasks/${id}/resume`)
  },

  // 获取实时进度
  getProgress(id) {
    return request.get(`/search/tasks/${id}/progress`)
  },

  // 获取进度日志
  getProgressLogs(id, params) {
    return request.get(`/search/tasks/${id}/logs`, { params })
  },

  // 获取搜索结果
  getResults(id, params) {
    return request.get(`/search/tasks/${id}/results`, { params })
  },

  // 获取内置源列表
  getBuiltInSources() {
    return request.get('/search/builtin-sources')
  },

  // 启用/禁用内置源
  toggleBuiltInSource(id, enabled) {
    return request.post(`/search/builtin-sources/${id}/toggle`, { enabled })
  },

  // 添加自定义搜索源
  addSearchSource(data) {
    return request.post('/search/builtin-sources', data)
  },

  // 删除自定义搜索源
  deleteSearchSource(id) {
    return request.delete(`/search/builtin-sources/${id}`)
  },

  // 获取热门关键词
  getHotKeywords() {
    return request.get('/search/hot-keywords')
  },

  // 导出搜索结果
  exportResults(id, format) {
    return request.get(`/search/tasks/${id}/export`, {
      params: { format },
      responseType: 'blob',
    })
  },
}
