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

const renderAppLayout = (children = <div>content</div>) => {
  const queryClient = new QueryClient()

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AppLayout>{children}</AppLayout>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const signInTestUser = () => {
  act(() => {
    useAuthStore.getState().setSession({
      accessToken: 'test-access',
      refreshToken: 'test-refresh',
      user: {
        user_id: 'usr_test',
        email: 'test@example.com',
        display_name: '娴嬭瘯鐢ㄦ埛',
        role: 'user',
        status: 'active',
      },
    })
  })
}

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
    renderAppLayout()

    expect(screen.getByText('首页')).toBeInTheDocument()
    expect(screen.getByText('登录')).toBeInTheDocument()
    expect(screen.getByText('注册')).toBeInTheDocument()
  })

  test('should mark public content as the main landmark', () => {
    renderAppLayout(<section>public content</section>)

    expect(screen.getByRole('main', { name: 'Public page content' })).toHaveTextContent('public content')
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

    renderAppLayout()

    expect(screen.getByText('AI Interview')).toBeInTheDocument()
    expect(screen.getByText('简历管理')).toBeInTheDocument()
    expect(screen.getByText('岗位库')).toBeInTheDocument()
    expect(screen.getByText('AI 面试')).toBeInTheDocument()
    expect(screen.getByText('面试记录')).toBeInTheDocument()
    act(() => {
      useAuthStore.getState().clearSession()
    })
  })
  test('should mark authenticated content as the main landmark', () => {
    signInTestUser()

    renderAppLayout(<section>authenticated content</section>)

    expect(screen.getByRole('main', { name: 'Authenticated page content' })).toHaveTextContent('authenticated content')

    act(() => {
      useAuthStore.getState().clearSession()
    })
  })
})
