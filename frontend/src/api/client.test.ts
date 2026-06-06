import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import axios from 'axios'
import { beforeEach, describe, expect, test, vi } from 'vitest'

import { apiClient, parseApiError } from './client'
import { useAuthStore } from '../stores/authStore'

/** 构造可用于 axios adapter 的最小响应。 */
function buildResponse(config: InternalAxiosRequestConfig): AxiosResponse {
  return {
    data: { ok: true },
    status: 200,
    statusText: 'OK',
    headers: {},
    config,
  }
}

describe('apiClient', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    useAuthStore.getState().clearSession()
  })

  test('injects bearer token and idempotency key', async () => {
    useAuthStore.getState().setSession({
      accessToken: 'access-token',
      refreshToken: 'refresh-token',
      user: {
        user_id: 'usr_test',
        email: 'user@example.com',
        display_name: '测试用户',
        role: 'user',
        status: 'active',
      },
    })
    const adapter = vi.fn(async (config: InternalAxiosRequestConfig) => buildResponse(config))
    apiClient.defaults.adapter = adapter

    await apiClient.post('/practice/sessions', { job_role: 'java' })

    const config = adapter.mock.calls[0][0]
    const headers = config.headers as unknown as Record<string, string>
    expect(headers.Authorization).toBe('Bearer access-token')
    expect(headers['X-Idempotency-Key']).toBeTruthy()
  })

  test('parses backend unified error payload', () => {
    const error = {
      isAxiosError: true,
      message: 'Request failed',
      response: {
        data: {
          error: {
            code: 'STATE_409',
            message: '状态冲突',
          },
        },
      },
    }
    vi.spyOn(axios, 'isAxiosError').mockReturnValue(true)

    expect(parseApiError(error)).toEqual({ code: 'STATE_409', message: '状态冲突' })
  })

  test('returns generic message for unknown non-axios error', () => {
    expect(parseApiError(new Error('boom'))).toEqual({
      code: 'UNKNOWN',
      message: '请求失败，请稍后重试',
    })
  })
})
