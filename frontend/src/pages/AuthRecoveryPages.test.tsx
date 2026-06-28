import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, test, vi } from 'vitest'

import { ForgotPasswordPage } from './ForgotPasswordPage'
import { ResetPasswordPage } from './ResetPasswordPage'

const mockForgotPassword = vi.fn()
const mockResetPassword = vi.fn()
const mockNavigate = vi.fn()

vi.mock('../api/auth', () => ({
  forgotPassword: (email: string) => mockForgotPassword(email),
  login: vi.fn(),
  register: vi.fn(),
  resetPassword: (payload: unknown) => mockResetPassword(payload),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

// 认证找回页面测试覆盖忘记密码和重置密码两条低频但关键的用户路径。
// 接口全部 mock，测试重点是表单字段、提交 payload 和成功跳转。

function renderWithClient(element: JSX.Element, initialEntries = ['/']) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>{element}</MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('auth recovery pages', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockForgotPassword.mockResolvedValue({ accepted: true, message: 'ok' })
    mockResetPassword.mockResolvedValue(undefined)
  })

  test('ForgotPasswordPage submits email to forgot password API', async () => {
    renderWithClient(<ForgotPasswordPage />)

    fireEvent.change(screen.getByPlaceholderText('name@example.com'), {
      target: { value: 'user@example.com' },
    })
    fireEvent.click(screen.getByRole('button', { name: '发送重置链接' }))

    await waitFor(() => {
      expect(mockForgotPassword).toHaveBeenCalledWith('user@example.com')
    })
  })

  test('ResetPasswordPage reads token from URL and submits new password', async () => {
    renderWithClient(
      <Routes>
        <Route path="/reset-password" element={<ResetPasswordPage />} />
      </Routes>,
      ['/reset-password?token=reset-token-001'],
    )

    expect(screen.getByDisplayValue('reset-token-001')).toBeInTheDocument()
    fireEvent.change(screen.getByPlaceholderText('请输入新密码'), {
      target: { value: 'Password123' },
    })
    fireEvent.click(screen.getByRole('button', { name: '确认重置' }))

    await waitFor(() => {
      expect(mockResetPassword).toHaveBeenCalledWith({
        reset_token: 'reset-token-001',
        new_password: 'Password123',
      })
    })
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/login', { replace: true })
    })
  })
})
