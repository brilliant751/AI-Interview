import axios from 'axios'

import { useAuthStore } from '../stores/authStore'

/** API 基础地址。 */
const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:18500/api/v1'

// 前端 API 层统一约定：
// 1. 所有业务请求都走 apiClient，方便统一注入 token、超时和错误处理。
// 2. access token 过期时只允许一个 refresh 请求在飞，其他请求排队等待新 token。
// 3. 每个请求默认带 X-Idempotency-Key，后端可用它抵消重复点击和网络重试。
// 4. parseApiError 把后端统一错误结构转换成页面可直接展示的文案。
// 5. 这里不依赖 React 组件上下文，因此使用 useAuthStore.getState() 读取状态。

/** 统一 HTTP 客户端。 */
export const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
})

let isRefreshing = false
let queuedRequests: Array<(token: string | null) => void> = []

/** 广播 refresh 结果给排队请求。 */
function flushQueue(token: string | null) {
  // refresh 成功时把新 token 分发给所有等待重放的请求。
  // refresh 失败时传 null，让每个等待请求都按原始 401 失败处理。
  queuedRequests.forEach((cb) => cb(token))
  queuedRequests = []
}

/** 请求拦截器：注入鉴权与幂等头。 */
apiClient.interceptors.request.use((config) => {
  // 拦截器里读取最新 store 状态，避免闭包捕获旧 token。
  // 如果调用方已经显式设置幂等键，就尊重调用方提供的 key。
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
      // 已经有 refresh 在进行时，当前请求不再重复刷新。
      // 通过队列等待刷新结果，成功后使用新 token 自动重放原请求。
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
      // 刷新 token 使用裸 axios，避免 refresh 请求自身再次触发 apiClient 的响应拦截器。
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
