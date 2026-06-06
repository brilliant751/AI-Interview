import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, test, vi } from 'vitest'

import { AppLayout } from './AppLayout'
import { useAuthStore } from '../stores/authStore'

const mockFetchInterviewSchedules = vi.fn()

vi.mock('../api/interview', () => ({
  fetchInterviewSchedules: (...args: unknown[]) => mockFetchInterviewSchedules(...args),
}))

/** AppLayout 渲染测试。 */
describe('AppLayout', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockFetchInterviewSchedules.mockResolvedValue({ items: [] })
  })

  test('should render navigation labels', () => {
    act(() => {
      useAuthStore.getState().setSession({
        accessToken: 'test-access',
        refreshToken: 'test-refresh',
        user: {
          user_id: 'usr_test',
          email: 'test@example.com',
          display_name: '测试用户',
          role: 'user',
          status: 'active',
        },
      })
    })

    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <AppLayout>
            <div>content</div>
          </AppLayout>
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(screen.getByText('AI Interview')).toBeInTheDocument()
    expect(screen.getByText('简历管理')).toBeInTheDocument()
    expect(screen.getByText('岗位库')).toBeInTheDocument()
    expect(screen.getByText('AI 面试')).toBeInTheDocument()
    expect(screen.getByText('面试记录')).toBeInTheDocument()
    act(() => {
      useAuthStore.getState().clearSession()
    })
  })
})
