import { Button, Layout, Typography } from 'antd'
import type { ReactNode } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { logout } from '../api/auth'
import { useAuthStore } from '../stores/authStore'

const { Header, Content } = Layout

/** 应用布局组件。 */
export function AppLayout(props: { children: ReactNode }) {
  const location = useLocation()
  const navigate = useNavigate()
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const user = useAuthStore((state) => state.user)
  const refreshToken = useAuthStore((state) => state.refreshToken)
  const clearSession = useAuthStore((state) => state.clearSession)

  const links = isAuthenticated
    ? [
        { to: '/interview', label: '模拟面试' },
        { to: '/resumes', label: '简历管理' },
        { to: '/history', label: '历史记录' },
      ]
    : [
        { to: '/login', label: '登录' },
        { to: '/register', label: '注册' },
      ]

  if (user?.role === 'admin') {
    links.push({ to: '/admin/imports', label: '知识库重建' })
  }

  /** 执行退出登录。 */
  const handleLogout = async () => {
    try {
      if (refreshToken) {
        await logout(refreshToken)
      }
    } finally {
      clearSession()
      navigate('/login', { replace: true })
    }
  }

  return (
    <Layout style={{ minHeight: '100vh', background: 'linear-gradient(180deg, #f9fafb 0%, #f2f6ff 100%)' }}>
      <Header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: '#10243f',
          color: '#fff',
          gap: 16,
        }}
      >
        <Typography.Title level={4} style={{ margin: 0, color: '#fff' }}>
          AI Interview
        </Typography.Title>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          {links.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              style={{
                color: location.pathname.startsWith(item.to) ? '#ffd666' : '#d6e4ff',
                textDecoration: 'none',
              }}
            >
              {item.label}
            </Link>
          ))}
          {isAuthenticated ? (
            <Button size="small" onClick={handleLogout}>
              退出登录
            </Button>
          ) : null}
        </div>
      </Header>
      <Content style={{ padding: '24px 16px', maxWidth: 980, margin: '0 auto', width: '100%' }}>
        {props.children}
      </Content>
    </Layout>
  )
}
