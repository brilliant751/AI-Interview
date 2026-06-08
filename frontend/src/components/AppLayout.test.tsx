import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, test, vi } from 'vitest'

import { AppLayout } from './AppLayout'
import { useAuthStore } from '../stores/authStore'

const mockFetchInterviewSchedules = vi.fn()

vi.mock('../api/interview', () => ({
  fetchScheduledInterviews: (...args: unknown[]) => mockFetchInterviewSchedules(...args),
}))

/** AppLayout 渲染测试。 */
describe('AppLayout', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })
  })

  beforeEach(() => {
    vi.clearAllMocks()
    useAuthStore.getState().clearSession()
    mockFetchInterviewSchedules.mockResolvedValue({ items: [] })
  })

  test('should render public home link when unauthenticated', () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <AppLayout>
            <div>content</div>
          </AppLayout>
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(screen.getByText('首页')).toBeInTheDocument()
    expect(screen.getByText('登录')).toBeInTheDocument()
    expect(screen.getByText('注册')).toBeInTheDocument()
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
