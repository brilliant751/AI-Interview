import { apiClient } from './client'
import type { AuthUser } from '../stores/authStore'

/** 注册请求。 */
export interface RegisterPayload {
  email: string
  password: string
  display_name: string
}

/** 登录请求。 */
export interface LoginPayload {
  email: string
  password: string
}

/** 重置密码请求。 */
export interface ResetPasswordPayload {
  reset_token: string
  new_password: string
}

/** 认证令牌响应。 */
export interface AuthTokenResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  refresh_token: string
  user: AuthUser
}

/** 注册新账号。 */
export async function register(payload: RegisterPayload): Promise<{ user: AuthUser }> {
  const { data } = await apiClient.post('/auth/register', payload)
  return data
}

/** 账号密码登录。 */
export async function login(payload: LoginPayload): Promise<AuthTokenResponse> {
  const { data } = await apiClient.post<AuthTokenResponse>('/auth/login', payload)
  return data
}

/** 刷新令牌。 */
export async function refreshToken(refreshTokenValue: string): Promise<AuthTokenResponse> {
  const { data } = await apiClient.post<AuthTokenResponse>('/auth/refresh', {
    refresh_token: refreshTokenValue,
  })
  return data
}

/** 注销会话。 */
export async function logout(refreshTokenValue: string): Promise<void> {
  await apiClient.post('/auth/logout', {
    refresh_token: refreshTokenValue,
  })
}

/** 发起忘记密码。 */
export async function forgotPassword(email: string): Promise<{ accepted: boolean; message: string }> {
  const { data } = await apiClient.post('/auth/forgot-password', { email })
  return data
}

/** 执行密码重置。 */
export async function resetPassword(payload: ResetPasswordPayload): Promise<void> {
  await apiClient.post('/auth/reset-password', payload)
}

/** 获取当前用户信息。 */
export async function fetchMe(): Promise<{ user: AuthUser }> {
  const { data } = await apiClient.get('/auth/me')
  return data
}
