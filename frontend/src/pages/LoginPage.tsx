import { useMutation } from '@tanstack/react-query'
import { Button, Card, Form, Input, Typography, message } from 'antd'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { login } from '../api/auth'
import { parseApiError } from '../api/client'
import { useAuthStore } from '../stores/authStore'

/** 登录页面。 */
export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const setSession = useAuthStore((state) => state.setSession)

  /** 提交登录。 */
  const loginMutation = useMutation({
    mutationFn: login,
    onSuccess: (data) => {
      setSession({
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        user: data.user,
      })
      const fallback = '/overview'
      const from = (location.state as { from?: string } | undefined)?.from ?? fallback
      message.success('登录成功')
      navigate(from, { replace: true })
    },
    onError: (error) => {
      const parsed = parseApiError(error)
      if (parsed.code === 'AUTH_401_INVALID_CREDENTIALS') {
        message.error('账号或密码错误')
        return
      }
      message.error(parsed.message)
    },
  })

  return (
    <Card title="登录" style={{ maxWidth: 460, margin: '40px auto' }}>
      <Form
        layout="vertical"
        initialValues={{ email: '', password: '' }}
        onFinish={(values: { email: string; password: string }) => loginMutation.mutate(values)}
      >
        <Form.Item
          name="email"
          label="邮箱"
          rules={[{ required: true, message: '请输入邮箱' }, { type: 'email', message: '邮箱格式不正确' }]}
        >
          <Input placeholder="name@example.com" />
        </Form.Item>
        <Form.Item name="password" label="密码" rules={[{ required: true, message: '请输入密码' }]}>
          <Input.Password placeholder="请输入密码" />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={loginMutation.isPending} block>
          登录
        </Button>
      </Form>
      <Typography.Paragraph style={{ marginTop: 16, marginBottom: 0 }}>
        没有账号？<Link to="/register">去注册</Link>
      </Typography.Paragraph>
      <Typography.Paragraph style={{ marginBottom: 0 }}>
        忘记密码？<Link to="/forgot-password">找回密码</Link>
      </Typography.Paragraph>
    </Card>
  )
}
