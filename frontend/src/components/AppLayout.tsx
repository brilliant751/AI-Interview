import { Layout, Typography } from 'antd'
import type { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'

const { Header, Content } = Layout

/** 应用布局组件。 */
export function AppLayout(props: { children: ReactNode }) {
  const location = useLocation()
  const links = [
    { to: '/upload', label: '上传简历' },
    { to: '/interview', label: '模拟面试' },
    { to: '/report', label: '面试报告' },
    { to: '/history', label: '历史记录' },
  ]

  return (
    <Layout style={{ minHeight: '100vh', background: 'linear-gradient(180deg, #f9fafb 0%, #f2f6ff 100%)' }}>
      <Header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: '#10243f',
          color: '#fff',
        }}
      >
        <Typography.Title level={4} style={{ margin: 0, color: '#fff' }}>
          AI Interview
        </Typography.Title>
        <div style={{ display: 'flex', gap: 16 }}>
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
        </div>
      </Header>
      <Content style={{ padding: '24px 16px', maxWidth: 980, margin: '0 auto', width: '100%' }}>
        {props.children}
      </Content>
    </Layout>
  )
}
