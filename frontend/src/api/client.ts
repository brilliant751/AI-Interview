import axios from 'axios'

/** API 基础地址。 */
const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api/v1'

/** 统一 HTTP 客户端。 */
export const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
})

/** 请求拦截器：注入鉴权与幂等头。 */
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('ai_interview_token') ?? 'user-token'
  const idempotencyKey = crypto.randomUUID()
  config.headers.Authorization = `Bearer ${token}`
  config.headers['X-Idempotency-Key'] = idempotencyKey
  return config
})

