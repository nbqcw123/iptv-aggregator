import request from './request'

/**
 * 源相关 API
 */
export const sourcesApi = {
  // 获取源列表
  getList(params) {
    return request.get('/sources', { params })
  },

  // 获取源详情
  getById(id) {
    return request.get(`/sources/${id}`)
  },

  // 新增源
  create(data) {
    return request.post('/sources', data)
  },

  // 更新源
  update(id, data) {
    return request.put(`/sources/${id}`, data)
  },

  // 删除源
  delete(id) {
    return request.delete(`/sources/${id}`)
  },

  // 批量删除
  batchDelete(ids) {
    return request.post('/sources/batch-delete', { ids })
  },

  // 验证单个源
  validate(id) {
    return request.post(`/sources/${id}/validate`)
  },

  // 批量验证源
  batchValidate(ids) {
    return request.post('/sources/batch-validate', { ids })
  },

  // 导入源（URL 或文本）
  import(data) {
    return request.post('/sources/import', data)
  },

  // 导入源（上传文件）
  importFile(file) {
    const formData = new FormData()
    formData.append('file', file)
    return request.post('/sources/import-file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // 获取源验证状态
  getValidationStatus(id) {
    return request.get(`/sources/${id}/validation-status`)
  },

  // 获取源统计
  getStats() {
    return request.get('/sources/stats')
  },

  // 刷新源
  refresh(id) {
    return request.post(`/sources/${id}/refresh`)
  },
}
