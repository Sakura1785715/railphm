import axios from 'axios'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 8000
})

http.interceptors.response.use(
  (response) => {
    const payload = response.data

    if (payload && typeof payload === 'object' && 'code' in payload && payload.code !== 200) {
      const error = new Error(payload.message || '接口请求失败')
      error.payload = payload
      throw error
    }

    return payload
  },
  (error) => {
    if (error.response?.data?.message) {
      error.message = error.response.data.message
    } else if (error.code === 'ECONNABORTED') {
      error.message = '请求超时，请稍后重试'
    } else if (error.message === 'Network Error') {
      error.message = '无法连接后端服务，请检查接口地址或后端是否已启动'
    }

    return Promise.reject(error)
  }
)

export default http
