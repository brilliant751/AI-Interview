import axios from 'axios'

import { useAuthStore } from '../stores/authStore'

/** API 基础地址。 */
const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api/v1'

/** 统一 HTTP 客户端。 */
export const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
})

let isRefreshing = false
let queuedRequests: Array<(token: string | null) => void> = []

/** 广播 refresh 结果给排队请求。 */
function flushQueue(token: string | null) {
  queuedRequests.forEach((cb) => cb(token))
  queuedRequests = []
}

/** 请求拦截器：注入鉴权与幂等头。 */
apiClient.interceptors.request.use((config) => {
  const { accessToken } = useAuthStore.getState()
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  const idempotencyKey = crypto.randomUUID()
  if (!config.headers['X-Idempotency-Key']) {
    config.headers['X-Idempotency-Key'] = idempotencyKey
  }
  return config
})

/** 响应拦截器：处理 401 自动刷新与请求重放。 */
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as (typeof error.config & { _retry?: boolean }) | undefined
    if (!originalRequest || error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error)
    }

    const authState = useAuthStore.getState()
    if (!authState.refreshToken) {
      authState.clearSession()
      return Promise.reject(error)
    }

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        queuedRequests.push((token) => {
          if (!token) {
            reject(error)
            return
          }
          originalRequest.headers.Authorization = `Bearer ${token}`
          resolve(apiClient(originalRequest))
        })
      })
    }

    originalRequest._retry = true
    isRefreshing = true

    try {
      const { data } = await axios.post(
        `${API_BASE}/auth/refresh`,
        { refresh_token: authState.refreshToken },
        { timeout: 10000 },
      )
      useAuthStore.getState().setSession({
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        user: data.user,
      })
      flushQueue(data.access_token)
      originalRequest.headers.Authorization = `Bearer ${data.access_token}`
      return apiClient(originalRequest)
    } catch (refreshError) {
      useAuthStore.getState().clearSession()
      flushQueue(null)
      if (typeof window !== 'undefined') {
        window.location.href = '/login'
      }
      return Promise.reject(refreshError)
    } finally {
      isRefreshing = false
    }
  },
)

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
