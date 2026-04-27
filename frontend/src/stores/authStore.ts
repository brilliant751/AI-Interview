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
    persistSession(payload)
    set({
      accessToken: payload.accessToken,
      refreshToken: payload.refreshToken,
      user: payload.user,
      isAuthenticated: true,
    })
  },
  updateAccessToken: (accessToken) => {
    const current = useAuthStore.getState()
    persistSession({
      accessToken,
      refreshToken: current.refreshToken,
      user: current.user,
    })
    set({ accessToken, isAuthenticated: Boolean(accessToken && current.refreshToken && current.user) })
  },
  clearSession: () => {
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
