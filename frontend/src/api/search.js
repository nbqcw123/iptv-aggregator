import axios from 'axios'

const request = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

request.interceptors.response.use(
  res => res.data,
  err => Promise.reject(err.response?.data || err)
)

export default request

// ============ 搜索 ============
export function apiSearch(data) {
  return request.post('/search', data)
}

export function apiValidate(data) {
  return request.post('/validate', data)
}

export function apiValidateSingle(url) {
  return request.get('/validate/single', { params: { url } })
}

// ============ 导出 ============
export function apiExportM3u() {
  return request.get('/export/m3u')
}

export function apiExportTxt() {
  return request.get('/export/txt')
}

export function apiExportFull(format, params = {}) {
  return request.get(`/export/${format}/full`, { params })
}

// ============ 内置源 ============
export function apiGetBuiltins() {
  return request.get('/sources/builtin')
}

export function apiAddBuiltin(data) {
  return request.post('/sources/builtin/add', null, { params: data })
}

// ============ 统计 ============
export function apiGetStats() {
  return request.get('/stats')
}
