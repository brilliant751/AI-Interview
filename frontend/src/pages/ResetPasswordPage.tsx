import { useMutation } from '@tanstack/react-query'
import { Button, Card, Form, Input, Typography, message } from 'antd'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { resetPassword } from '../api/auth'
import { parseApiError } from '../api/client'

/** 重置密码页面。 */
export function ResetPasswordPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const initialToken = searchParams.get('token') ?? ''

  /** 提交重置密码。 */
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
    <Card title="重置密码" style={{ maxWidth: 460, margin: '40px auto' }}>
      <Form
        layout="vertical"
        initialValues={{ reset_token: initialToken, new_password: '' }}
        onFinish={(values: { reset_token: string; new_password: string }) => resetMutation.mutate(values)}
      >
        <Form.Item name="reset_token" label="重置令牌" rules={[{ required: true, message: '请输入重置令牌' }]}>
          <Input placeholder="请输入重置令牌" />
        </Form.Item>
        <Form.Item
          name="new_password"
          label="新密码"
          rules={[
            { required: true, message: '请输入新密码' },
            { min: 8, message: '密码至少 8 位' },
            { pattern: /^(?=.*[A-Za-z])(?=.*\d).+$/, message: '密码需同时包含字母和数字' },
          ]}
        >
          <Input.Password placeholder="请输入新密码" />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={resetMutation.isPending} block>
          确认重置
        </Button>
      </Form>
      <Typography.Paragraph style={{ marginTop: 16, marginBottom: 0 }}>
        返回<Link to="/login">登录页</Link>
      </Typography.Paragraph>
    </Card>
  )
}
