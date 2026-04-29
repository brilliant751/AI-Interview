import { useMutation } from '@tanstack/react-query'
import { Button, Card, Form, Input, Typography, message } from 'antd'
import { Link } from 'react-router-dom'

import { forgotPassword } from '../api/auth'
import { parseApiError } from '../api/client'

/** 忘记密码页面。 */
export function ForgotPasswordPage() {
  /** 提交找回密码请求。 */
  const forgotMutation = useMutation({
    mutationFn: async (payload: { email: string }) => forgotPassword(payload.email),
    onSuccess: () => {
      message.success('如邮箱存在，我们已发送重置邮件')
    },
    onError: (error) => {
      const parsed = parseApiError(error)
      message.error(parsed.message)
    },
  })

  return (
    <Card title="找回密码" style={{ maxWidth: 460, margin: '40px auto' }}>
      <Form
        layout="vertical"
        initialValues={{ email: '' }}
        onFinish={(values: { email: string }) => forgotMutation.mutate(values)}
      >
        <Form.Item
          name="email"
          label="邮箱"
          rules={[{ required: true, message: '请输入邮箱' }, { type: 'email', message: '邮箱格式不正确' }]}
        >
          <Input placeholder="name@example.com" />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={forgotMutation.isPending} block>
          发送重置链接
        </Button>
      </Form>
      <Typography.Paragraph style={{ marginTop: 16, marginBottom: 0 }}>
        已想起密码？<Link to="/login">返回登录</Link>
      </Typography.Paragraph>
    </Card>
  )
}
