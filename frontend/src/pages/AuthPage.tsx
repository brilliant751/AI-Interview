import { useCallback, useEffect, useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Button, Card, Form, Input, Segmented, Typography, message } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'

import { forgotPassword, login, register } from '../api/auth'
import { parseApiError } from '../api/client'
import { useAuthStore } from '../stores/authStore'

type AuthMode = 'login' | 'register' | 'forgot'

const modeByPath: Record<string, AuthMode> = {
  '/login': 'login',
  '/register': 'register',
  '/forgot-password': 'forgot',
}

const pathByMode: Record<AuthMode, string> = {
  login: '/login',
  register: '/register',
  forgot: '/forgot-password',
}

const titleByMode: Record<AuthMode, string> = {
  login: '登录账号',
  register: '注册账号',
  forgot: '找回密码',
}

const introByMode: Record<AuthMode, { kicker: string; titleLines: string[]; body: string; tags: string[] }> = {
  login: {
    kicker: '模拟 · 练习 · 复盘',
    titleLines: ['用一次登录，', '进入完整的 AI 面试训练台。'],
    body: '从岗位准备、简历匹配到实时面试和报告复盘，把练习过程集中在一个清爽的工作区里。',
    tags: ['智能追问', '简历联动', '复盘报告'],
  },
  register: {
    kicker: '创建 · 训练 · 成长',
    titleLines: ['注册账号，', '建立你的专属面试成长档案。'],
    body: '系统会保存你的练习记录、岗位目标和复盘报告，帮助你持续追踪每一次模拟面试的提升。',
    tags: ['账号档案', '训练记录', '能力追踪'],
  },
  forgot: {
    kicker: '验证 · 重置 · 回到训练',
    titleLines: ['找回密码后，', '继续你的 AI 模拟面试计划。'],
    body: '输入注册邮箱，如果账号存在，系统会发送密码重置链接，帮助你安全恢复访问。',
    tags: ['邮箱验证', '安全重置', '快速恢复'],
  },
}

/** 登录、注册、找回密码共用的认证入口。 */
export function AuthPage(props: { initialMode?: AuthMode }) {
  const navigate = useNavigate()
  const location = useLocation()
  const setSession = useAuthStore((state) => state.setSession)
  const [mode, setMode] = useState<AuthMode>(() => props.initialMode ?? modeByPath[location.pathname] ?? 'login')
  const intro = introByMode[mode]

  useEffect(() => {
    const nextMode = props.initialMode ?? modeByPath[location.pathname] ?? 'login'
    setMode(nextMode)
  }, [location.pathname, props.initialMode])

  const switchMode = useCallback((nextMode: AuthMode) => {
    setMode(nextMode)
    navigate(pathByMode[nextMode], { replace: true, state: location.state })
  }, [location.state, navigate])

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

  const registerMutation = useMutation({
    mutationFn: register,
    onSuccess: () => {
      message.success('注册成功，请登录')
      switchMode('login')
    },
    onError: (error) => {
      const parsed = parseApiError(error)
      message.error(parsed.message)
    },
  })

  const forgotMutation = useMutation({
    mutationFn: async (payload: { email: string }) => forgotPassword(payload.email),
    onSuccess: () => {
      message.success('如果邮箱存在，我们已发送重置邮件')
    },
    onError: (error) => {
      const parsed = parseApiError(error)
      message.error(parsed.message)
    },
  })

  const cardExtra = useMemo(
    () => (
      <Segmented
        className="auth-mode-tabs"
        value={mode}
        onChange={(value) => switchMode(value as AuthMode)}
        options={[
          { label: '登录', value: 'login' },
          { label: '注册', value: 'register' },
          { label: '找回密码', value: 'forgot' },
        ]}
      />
    ),
    [mode, switchMode],
  )

  return (
    <div className="login-garden-shell auth-static is-ready">
      <section className="login-panel-stage auth-panel-stage" aria-label="AI 模拟面试系统认证入口">
        <div className="auth-branch-scene" aria-hidden="true">
          <span className="auth-branch auth-branch-left" />
          <span className="auth-branch auth-branch-right" />
          <span className="auth-leaf auth-leaf-left-a" />
          <span className="auth-leaf auth-leaf-left-b" />
          <span className="auth-leaf auth-leaf-right-a" />
          <span className="auth-leaf auth-leaf-right-b" />
        </div>

        <div className="login-brand-panel">
          <Typography.Text className="login-brand-kicker">{intro.kicker}</Typography.Text>
          <Typography.Title level={2} className="login-brand-title">
            {intro.titleLines.map((line) => (
              <span key={line}>{line}</span>
            ))}
          </Typography.Title>
          <Typography.Paragraph>{intro.body}</Typography.Paragraph>
          <div className="login-signal-row" aria-label="系统能力">
            {intro.tags.map((tag) => (
              <span key={tag}>{tag}</span>
            ))}
          </div>
        </div>

        <Card className="login-garden-card auth-garden-card" title={titleByMode[mode]} extra={cardExtra}>
          {mode === 'login' ? (
            <Form
              key="login"
              layout="vertical"
              initialValues={{ email: '', password: '' }}
              onFinish={(values: { email: string; password: string }) => loginMutation.mutate(values)}
            >
              <Form.Item
                name="email"
                label="邮箱"
                rules={[
                  { required: true, message: '请输入邮箱' },
                  { type: 'email', message: '邮箱格式不正确' },
                ]}
              >
                <Input size="large" placeholder="name@example.com" autoComplete="email" />
              </Form.Item>
              <Form.Item name="password" label="密码" rules={[{ required: true, message: '请输入密码' }]}>
                <Input.Password size="large" placeholder="请输入密码" autoComplete="current-password" />
              </Form.Item>
              <Button type="primary" htmlType="submit" loading={loginMutation.isPending} block size="large">
                登录
              </Button>
            </Form>
          ) : null}

          {mode === 'register' ? (
            <Form
              key="register"
              layout="vertical"
              initialValues={{ email: '', password: '', display_name: '' }}
              onFinish={(values: { email: string; password: string; display_name: string }) =>
                registerMutation.mutate(values)
              }
            >
              <Form.Item
                name="display_name"
                label="昵称"
                rules={[
                  { required: true, message: '请输入昵称' },
                  { min: 2, message: '昵称至少 2 个字符' },
                ]}
              >
                <Input size="large" placeholder="请输入昵称" autoComplete="name" />
              </Form.Item>
              <Form.Item
                name="email"
                label="邮箱"
                rules={[
                  { required: true, message: '请输入邮箱' },
                  { type: 'email', message: '邮箱格式不正确' },
                ]}
              >
                <Input size="large" placeholder="name@example.com" autoComplete="email" />
              </Form.Item>
              <Form.Item
                name="password"
                label="密码"
                rules={[
                  { required: true, message: '请输入密码' },
                  { min: 8, message: '密码至少 8 位' },
                  {
                    pattern: /^(?=.*[A-Za-z])(?=.*\d).+$/,
                    message: '密码需要同时包含字母和数字',
                  },
                ]}
              >
                <Input.Password size="large" placeholder="请输入密码" autoComplete="new-password" />
              </Form.Item>
              <Button type="primary" htmlType="submit" loading={registerMutation.isPending} block size="large">
                注册
              </Button>
            </Form>
          ) : null}

          {mode === 'forgot' ? (
            <Form
              key="forgot"
              layout="vertical"
              initialValues={{ email: '' }}
              onFinish={(values: { email: string }) => forgotMutation.mutate(values)}
            >
              <Form.Item
                name="email"
                label="邮箱"
                rules={[
                  { required: true, message: '请输入邮箱' },
                  { type: 'email', message: '邮箱格式不正确' },
                ]}
              >
                <Input size="large" placeholder="name@example.com" autoComplete="email" />
              </Form.Item>
              <Button type="primary" htmlType="submit" loading={forgotMutation.isPending} block size="large">
                发送重置链接
              </Button>
            </Form>
          ) : null}
        </Card>
      </section>
    </div>
  )
}
