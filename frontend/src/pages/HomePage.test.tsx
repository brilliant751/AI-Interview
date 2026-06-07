import { act, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeAll, describe, expect, test, vi } from 'vitest'

import { useAuthStore } from '../stores/authStore'
import { HomePage } from './HomePage'

/** 首页渲染测试。 */
describe('HomePage', () => {
  beforeAll(() => {
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

  afterEach(() => {
    act(() => {
      useAuthStore.getState().clearSession()
    })
  })

  test('should render public home page with practical preparation sections', () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    )

    expect(screen.getByText('面试准备，从流程开始')).toBeInTheDocument()
    expect(screen.getByText('准备路径')).toBeInTheDocument()
    expect(screen.getByText('常用入口')).toBeInTheDocument()
    expect(screen.getAllByText('模拟面试').length).toBeGreaterThan(0)
    expect(screen.queryByText(/AI 驱动|智能赋能|未来感/)).not.toBeInTheDocument()
    expect(screen.queryByText('上传简历，选择岗位，完成一轮模拟面试，再根据记录复盘。页面只保留常用入口和准备路径。')).not.toBeInTheDocument()
    expect(screen.queryByText('进入大厅，创建或恢复一场面试。')).not.toBeInTheDocument()
  })

  test('should point primary action to interview when authenticated', () => {
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
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: '开始面试' })).toHaveAttribute('href', '/interview')
    expect(screen.getByRole('link', { name: '管理简历' })).toHaveAttribute('href', '/resumes')
  })
})
