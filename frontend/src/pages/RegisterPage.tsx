import { useMutation } from '@tanstack/react-query'
import { Button, Card, Form, Input, Typography, message } from 'antd'
import { Link, useNavigate } from 'react-router-dom'

import { register } from '../api/auth'
import { parseApiError } from '../api/client'

// 注册页：
// 1. 只负责提交账号信息并展示后端校验结果。
// 2. 注册成功后跳转登录页，由用户再完成登录获取 token。
// 3. 表单校验覆盖昵称、邮箱和密码的基础规则，复杂唯一性由后端判断。

/** 注册页面。 */
export function RegisterPage() {
  const navigate = useNavigate()

  /** 提交注册。 */
  const registerMutation = useMutation({
    mutationFn: register,
    onSuccess: () => {
      message.success('注册成功，请登录')
      navigate('/login', { replace: true })
    },
    onError: (error) => {
      const parsed = parseApiError(error)
      message.error(parsed.message)
    },
  })

  return (
    <Card title="注册" style={{ maxWidth: 460, margin: '40px auto' }}>
      <Form
        layout="vertical"
        initialValues={{ email: '', password: '', display_name: '' }}
        onFinish={(values: { email: string; password: string; display_name: string }) => registerMutation.mutate(values)}
      >
        <Form.Item
          name="display_name"
          label="昵称"
          rules={[{ required: true, message: '请输入昵称' }, { min: 2, message: '昵称至少 2 个字符' }]}
        >
          <Input placeholder="请输入昵称" />
        </Form.Item>
        <Form.Item
          name="email"
          label="邮箱"
          rules={[{ required: true, message: '请输入邮箱' }, { type: 'email', message: '邮箱格式不正确' }]}
        >
          <Input placeholder="name@example.com" />
        </Form.Item>
        <Form.Item
          name="password"
          label="密码"
          rules={[
            { required: true, message: '请输入密码' },
            { min: 8, message: '密码至少 8 位' },
            {
              pattern: /^(?=.*[A-Za-z])(?=.*\d).+$/,
              message: '密码需同时包含字母和数字',
            },
          ]}
        >
          <Input.Password placeholder="请输入密码" />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={registerMutation.isPending} block>
          注册
        </Button>
      </Form>
      <Typography.Paragraph style={{ marginTop: 16, marginBottom: 0 }}>
        已有账号？<Link to="/login">去登录</Link>
      </Typography.Paragraph>
    </Card>
  )
}
