import { beforeEach, describe, expect, test } from 'vitest'

import { useAuthStore, type AuthUser } from './authStore'

// authStore 负责登录态内存状态与 localStorage 持久化。
// 这里直接调用 store action，不渲染页面，确保登录、刷新 token、退出和 hydrate 行为稳定。

const user: AuthUser = {
  user_id: 'usr_001',
  email: 'user@example.com',
  display_name: '测试用户',
  role: 'user',
  status: 'active',
}

describe('authStore', () => {
  beforeEach(() => {
    window.localStorage.clear()
    useAuthStore.getState().clearSession()
  })

  test('setSession stores runtime and persisted session state', () => {
    useAuthStore.getState().setSession({
      accessToken: 'access-1',
      refreshToken: 'refresh-1',
      user,
    })

    const state = useAuthStore.getState()
    expect(state.isAuthenticated).toBe(true)
    expect(state.accessToken).toBe('access-1')
    expect(window.localStorage.getItem('ai_interview_access_token')).toBe('access-1')
    expect(window.localStorage.getItem('ai_interview_refresh_token')).toBe('refresh-1')
    expect(window.localStorage.getItem('ai_interview_user')).toContain('user@example.com')
  })

  test('updateAccessToken keeps refresh token and user unchanged', () => {
    useAuthStore.getState().setSession({
      accessToken: 'old-access',
      refreshToken: 'refresh-keep',
      user,
    })

    useAuthStore.getState().updateAccessToken('new-access')

    const state = useAuthStore.getState()
    expect(state.accessToken).toBe('new-access')
    expect(state.refreshToken).toBe('refresh-keep')
    expect(state.user?.user_id).toBe('usr_001')
    expect(window.localStorage.getItem('ai_interview_access_token')).toBe('new-access')
  })

  test('clearSession removes persisted values and resets auth flags', () => {
    useAuthStore.getState().setSession({
      accessToken: 'access',
      refreshToken: 'refresh',
      user,
    })

    useAuthStore.getState().clearSession()

    const state = useAuthStore.getState()
    expect(state.isAuthenticated).toBe(false)
    expect(state.user).toBeNull()
    expect(window.localStorage.getItem('ai_interview_access_token')).toBeNull()
    expect(window.localStorage.getItem('ai_interview_refresh_token')).toBeNull()
    expect(window.localStorage.getItem('ai_interview_user')).toBeNull()
  })

  test('hydrate restores complete persisted session', () => {
    window.localStorage.setItem('ai_interview_access_token', 'persisted-access')
    window.localStorage.setItem('ai_interview_refresh_token', 'persisted-refresh')
    window.localStorage.setItem('ai_interview_user', JSON.stringify(user))

    useAuthStore.getState().hydrate()

    const state = useAuthStore.getState()
    expect(state.isAuthenticated).toBe(true)
    expect(state.accessToken).toBe('persisted-access')
    expect(state.refreshToken).toBe('persisted-refresh')
    expect(state.user?.email).toBe('user@example.com')
  })

  test('hydrate treats malformed persisted user as unauthenticated', () => {
    window.localStorage.setItem('ai_interview_access_token', 'persisted-access')
    window.localStorage.setItem('ai_interview_refresh_token', 'persisted-refresh')
    window.localStorage.setItem('ai_interview_user', '{bad json')

    useAuthStore.getState().hydrate()

    const state = useAuthStore.getState()
    expect(state.isAuthenticated).toBe(false)
    expect(state.user).toBeNull()
  })
})
