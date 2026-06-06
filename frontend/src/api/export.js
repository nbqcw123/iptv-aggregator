import request from './request'

/**
 * 导出相关 API
 */
export const exportApi = {
  // 导出 M3U
  exportM3U(params) {
    return request.get('/export/m3u', {
      params,
      responseType: 'blob',
    })
  },

  // 导出 TXT
  exportTXT(params) {
    return request.get('/export/txt', {
      params,
      responseType: 'blob',
    })
  },

  // 导出 JSON
  exportJSON(params) {
    return request.get('/export/json', {
      params,
      responseType: 'blob',
    })
  },

  // 获取可导出的分组列表
  getExportGroups() {
    return request.get('/export/groups')
  },

  // 获取可导出的地区列表
  getExportRegions() {
    return request.get('/export/regions')
  },

  // 获取导出历史
  getHistory(params) {
    return request.get('/export/history', { params })
  },

  // 下载导出文件
  downloadFile(filename) {
    return request.get(`/export/download/${filename}`, {
      responseType: 'blob',
    })
  },

  // 生成预览（返回文本内容）
  preview(params) {
    return request.get('/export/preview', { params })
  },
}
