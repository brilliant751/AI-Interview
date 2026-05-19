import { act, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, test } from 'vitest'

import { AppLayout } from './AppLayout'
import { useAuthStore } from '../stores/authStore'

/** AppLayout 渲染测试。 */
describe('AppLayout', () => {
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
      <MemoryRouter>
        <AppLayout>
          <div>content</div>
        </AppLayout>
      </MemoryRouter>,
    )

    expect(screen.getByText('AI Interview')).toBeInTheDocument()
    expect(screen.getByText('简历管理')).toBeInTheDocument()
    expect(screen.getByText('岗位管理')).toBeInTheDocument()
    expect(screen.getByText('模拟面试')).toBeInTheDocument()
    expect(screen.getByText('历史记录')).toBeInTheDocument()
    act(() => {
      useAuthStore.getState().clearSession()
    })
  })
})
