import { useMutation } from '@tanstack/react-query'
import { Button, Card, Form, Input, Typography, message } from 'antd'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { resetPassword } from '../api/auth'
import { parseApiError } from '../api/client'

/** 邮件重置链接进入后的密码重置页。 */
export function ResetPasswordPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const initialToken = searchParams.get('token') ?? ''

  const resetMutation = useMutation({
    mutationFn: resetPassword,
    onSuccess: () => {
      message.success('密码重置成功，请重新登录')
      navigate('/login', { replace: true })
    },
    onError: (error) => {
      const parsed = parseApiError(error)
      message.error(parsed.message)
    },
  })

  return (
    <div className="login-garden-shell auth-static is-ready">
      <section className="login-panel-stage auth-panel-stage" aria-label="重置 AI 模拟面试系统密码">
        <div className="auth-branch-scene" aria-hidden="true">
          <span className="auth-branch auth-branch-left" />
          <span className="auth-branch auth-branch-right" />
          <span className="auth-leaf auth-leaf-left-a" />
          <span className="auth-leaf auth-leaf-left-b" />
          <span className="auth-leaf auth-leaf-right-a" />
          <span className="auth-leaf auth-leaf-right-b" />
        </div>

        <div className="login-brand-panel">
          <Typography.Text className="login-brand-kicker">安全 · 恢复 · 继续训练</Typography.Text>
          <Typography.Title level={2}>设置新密码，回到你的模拟面试训练节奏。</Typography.Title>
          <Typography.Paragraph>
            使用邮件中的重置令牌完成验证。新密码会立即生效，之后你可以用新密码重新登录系统。
          </Typography.Paragraph>
          <div className="login-signal-row" aria-label="重置密码能力">
            <span>令牌验证</span>
            <span>新密码保护</span>
            <span>安全登录</span>
          </div>
        </div>

        <Card className="login-garden-card auth-garden-card" title="重置密码">
          <Form
            layout="vertical"
            initialValues={{ reset_token: initialToken, new_password: '' }}
            onFinish={(values: { reset_token: string; new_password: string }) => resetMutation.mutate(values)}
          >
            <Form.Item name="reset_token" label="重置令牌" rules={[{ required: true, message: '请输入重置令牌' }]}>
              <Input size="large" placeholder="请输入重置令牌" />
            </Form.Item>
            <Form.Item
              name="new_password"
              label="新密码"
              rules={[
                { required: true, message: '请输入新密码' },
                { min: 8, message: '密码至少 8 位' },
                { pattern: /^(?=.*[A-Za-z])(?=.*\d).+$/, message: '密码需要同时包含字母和数字' },
              ]}
            >
              <Input.Password size="large" placeholder="请输入新密码" autoComplete="new-password" />
            </Form.Item>
            <Button type="primary" htmlType="submit" loading={resetMutation.isPending} block size="large">
              确认重置
            </Button>
          </Form>
        </Card>
      </section>
    </div>
  )
}
