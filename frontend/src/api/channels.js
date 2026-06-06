import request from './request'

/**
 * 频道相关 API
 */
export const channelsApi = {
  // 获取频道列表
  getList(params) {
    return request.get('/channels', { params })
  },

  // 获取频道详情
  getById(id) {
    return request.get(`/channels/${id}`)
  },

  // 新增频道
  create(data) {
    return request.post('/channels', data)
  },

  // 更新频道
  update(id, data) {
    return request.put(`/channels/${id}`, data)
  },

  // 删除频道
  delete(id) {
    return request.delete(`/channels/${id}`)
  },

  // 批量删除
  batchDelete(ids) {
    return request.post('/channels/batch-delete', { ids })
  },

  // 搜索频道
  search(params) {
    return request.get('/channels/search', { params })
  },

  // 获取频道分组
  getGroups() {
    return request.get('/channels/groups')
  },

  // 获取地区列表
  getRegions() {
    return request.get('/channels/regions')
  },

  // 获取运营商列表
  getIsps() {
    return request.get('/channels/isps')
  },

  // 批量更新频道
  batchUpdate(data) {
    return request.post('/channels/batch-update', data)
  },

  // 获取频道总数
  getTotal() {
    return request.get('/channels/total')
  },

  // 按条件统计
  getStats() {
    return request.get('/channels/stats')
  },
}
