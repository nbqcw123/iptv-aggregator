import axios from 'axios'
const request = axios.create({ baseURL: '/api', timeout: 300000 })
request.interceptors.response.use(res => res.data, err => Promise.reject(err.response?.data || err))
export default request
