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
  if (!config.headers['X-Idempotency-Key']) {
    config.headers['X-Idempotency-Key'] = idempotencyKey
  }
  return config
})

/** 解析后端统一错误码。 */
export function parseApiError(error: unknown): { code: string; message: string } {
  if (!axios.isAxiosError(error)) {
    return { code: 'UNKNOWN', message: '请求失败，请稍后重试' }
  }
  const payload = error.response?.data as { error?: { code?: string; message?: string } } | undefined
  return {
    code: payload?.error?.code ?? 'UNKNOWN',
    message: payload?.error?.message ?? error.message ?? '请求失败，请稍后重试',
  }
}
