import { create } from 'zustand'

/** 认证用户信息模型。 */
export interface AuthUser {
  user_id: string
  email: string
  display_name: string
  role: 'user' | 'admin'
  status: 'active' | 'disabled'
}

/** 认证状态模型。 */
interface AuthState {
  accessToken: string
  refreshToken: string
  user: AuthUser | null
  isAuthenticated: boolean
}

/** 认证状态操作。 */
interface AuthActions {
  setSession: (payload: { accessToken: string; refreshToken: string; user: AuthUser }) => void
  updateAccessToken: (accessToken: string) => void
  clearSession: () => void
  hydrate: () => void
}

const ACCESS_TOKEN_KEY = 'ai_interview_access_token'
const REFRESH_TOKEN_KEY = 'ai_interview_refresh_token'
const USER_KEY = 'ai_interview_user'

// 认证状态持久化策略：
// 1. accessToken/refreshToken/user 三项必须同时存在，才认为当前用户已登录。
// 2. Zustand 保存运行时状态，localStorage 负责页面刷新后的恢复。
// 3. getStorage 会兼容测试环境和 SSR 场景，避免 window/localStorage 不存在时报错。
// 4. clearSession 同时清内存和本地缓存，确保退出后拦截器不会继续带旧 token。
// 5. hydrate 由应用启动阶段调用，把本地缓存恢复成全局状态。

/** 获取可用的本地存储对象。 */
function getStorage(): Storage | null {
  if (typeof window === 'undefined' || !window.localStorage) {
    return null
  }
  const storage = window.localStorage as Partial<Storage>
  if (
    typeof storage.getItem !== 'function' ||
    typeof storage.setItem !== 'function' ||
    typeof storage.removeItem !== 'function'
  ) {
    return null
  }
  return window.localStorage
}

/** 从本地存储读取会话。 */
function loadSession() {
  // 这里对 user JSON 做容错解析。
  // 如果用户对象损坏，就让 isAuthenticated=false，避免展示半登录状态。
  const storage = getStorage()
  if (!storage) {
    return {
      accessToken: '',
      refreshToken: '',
      user: null,
      isAuthenticated: false,
    }
  }
  const accessToken = storage.getItem(ACCESS_TOKEN_KEY) ?? ''
  const refreshToken = storage.getItem(REFRESH_TOKEN_KEY) ?? ''
  const rawUser = storage.getItem(USER_KEY)
  let user: AuthUser | null = null
  if (rawUser) {
    try {
      user = JSON.parse(rawUser) as AuthUser
    } catch {
      user = null
    }
  }
  return {
    accessToken,
    refreshToken,
    user,
    isAuthenticated: Boolean(accessToken && refreshToken && user),
  }
}

/** 持久化会话到本地存储。 */
function persistSession(session: { accessToken: string; refreshToken: string; user: AuthUser | null }) {
  const storage = getStorage()
  if (!storage) {
    return
  }
  storage.setItem(ACCESS_TOKEN_KEY, session.accessToken)
  storage.setItem(REFRESH_TOKEN_KEY, session.refreshToken)
  if (session.user) {
    storage.setItem(USER_KEY, JSON.stringify(session.user))
  } else {
    storage.removeItem(USER_KEY)
  }
}

/** 清理本地会话。 */
function clearPersistedSession() {
  const storage = getStorage()
  if (!storage) {
    return
  }
  storage.removeItem(ACCESS_TOKEN_KEY)
  storage.removeItem(REFRESH_TOKEN_KEY)
  storage.removeItem(USER_KEY)
}

/** 认证全局状态。 */
export const useAuthStore = create<AuthState & AuthActions>()((set) => ({
  accessToken: '',
  refreshToken: '',
  user: null,
  isAuthenticated: false,
  setSession: (payload) => {
    // 登录或刷新成功后同步写入 localStorage 和 Zustand。
    // 这样后续 API 拦截器可以立即读到最新 token。
    persistSession(payload)
    set({
      accessToken: payload.accessToken,
      refreshToken: payload.refreshToken,
      user: payload.user,
      isAuthenticated: true,
    })
  },
  updateAccessToken: (accessToken) => {
    // 只更新 access token 时保留 refresh token 和 user。
    // 该操作主要给自动续期流程使用。
    const current = useAuthStore.getState()
    persistSession({
      accessToken,
      refreshToken: current.refreshToken,
      user: current.user,
    })
    set({ accessToken, isAuthenticated: Boolean(accessToken && current.refreshToken && current.user) })
  },
  clearSession: () => {
    // 退出登录、refresh 失败、认证失效都会走这里。
    // 统一清理可以避免页面之间残留不一致的登录状态。
    clearPersistedSession()
    set({
      accessToken: '',
      refreshToken: '',
      user: null,
      isAuthenticated: false,
    })
  },
  hydrate: () => {
    const session = loadSession()
    set(session)
  },
}))
