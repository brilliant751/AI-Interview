import {
  BellOutlined,
  BookOutlined,
  FileTextOutlined,
  FormOutlined,
  HomeOutlined,
  LogoutOutlined,
  ReadOutlined,
  ScheduleOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { Badge, Button, Dropdown, Grid, Layout, Menu, Space, Typography } from 'antd'
import type { ReactNode } from 'react'
import type { MenuProps } from 'antd'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { logout } from '../api/auth'
import { useAuthStore } from '../stores/authStore'

const { Header, Content, Sider } = Layout

/** 应用布局组件。 */
export function AppLayout(props: { children: ReactNode }) {
  const screens = Grid.useBreakpoint()
  const isMobile = !screens.md
  const location = useLocation()
  const navigate = useNavigate()
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const user = useAuthStore((state) => state.user)
  const refreshToken = useAuthStore((state) => state.refreshToken)
  const clearSession = useAuthStore((state) => state.clearSession)
  const isInterviewSessionPage = /^\/interview\/[^/]+/.test(location.pathname)

  const sideMenuItems: MenuProps['items'] = [
    { key: '/overview', icon: <HomeOutlined />, label: <Link to="/overview">首页概览</Link> },
    { key: '/interview', icon: <FormOutlined />, label: <Link to="/interview">AI 面试</Link> },
    { key: '/practice', icon: <ReadOutlined />, label: <Link to="/practice">题库练习</Link> },
    { key: '/history', icon: <ScheduleOutlined />, label: <Link to="/history">面试记录</Link> },
    { key: '/report', icon: <FileTextOutlined />, label: <Link to="/report">我的报告</Link> },
    { key: '/jobs', icon: <BookOutlined />, label: <Link to="/jobs">岗位库</Link> },
    { key: '/resumes', icon: <TeamOutlined />, label: <Link to="/resumes">简历管理</Link> },
  ]
  if (user?.role === 'admin') {
    sideMenuItems.push({ key: '/admin/imports', icon: <UserOutlined />, label: <Link to="/admin/imports">知识库重建</Link> })
    sideMenuItems.push({ key: '/admin/questions', icon: <UserOutlined />, label: <Link to="/admin/questions">题库管理</Link> })
  }

  /** 根据当前路径选中侧边栏菜单。 */
  const selectedMenuKey = () => {
    const pathName = location.pathname
    const allKeys = sideMenuItems?.map((item) => String(item?.key || '')) || []
    const matched = allKeys.find((key) => pathName.startsWith(key))
    return matched ? [matched] : ['/overview']
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

  const userMenuItems: MenuProps['items'] = [
    { key: 'email', label: <Typography.Text type="secondary">{user?.email || '未登录'}</Typography.Text>, disabled: true },
    { type: 'divider' },
    {
      key: 'logout',
      label: '退出登录',
      icon: <LogoutOutlined />,
      onClick: () => {
        void handleLogout()
      },
    },
  ]

  return (
    <Layout
      style={{
        minHeight: '100dvh',
        height: '100dvh',
        overflow: 'hidden',
        background: 'linear-gradient(180deg, #f9fafb 0%, #f2f6ff 100%)',
      }}
    >
      <Header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: '#10243f',
          color: '#fff',
          gap: 12,
          paddingInline: isMobile ? 12 : 20,
        }}
      >
        <Space size={10}>
          <Typography.Title level={4} style={{ margin: 0, color: '#fff' }}>
            AI Interview
          </Typography.Title>
          {isAuthenticated ? <Typography.Text style={{ color: '#9ec5ff' }}>面试训练工作台</Typography.Text> : null}
        </Space>
        {isAuthenticated ? (
          <Space size={14}>
            <Badge count={2} size="small">
              <Button shape="circle" icon={<BellOutlined />} />
            </Badge>
            <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
              <Button icon={<UserOutlined />}>{user?.display_name || user?.email?.split('@')[0] || '用户'}</Button>
            </Dropdown>
          </Space>
        ) : (
          <Space size={10}>
            <Button type="link">
              <Link to="/login">登录</Link>
            </Button>
            <Button>
              <Link to="/register">注册</Link>
            </Button>
          </Space>
        )}
      </Header>
      <Layout style={{ minHeight: 0, overflow: 'hidden' }}>
        {isAuthenticated ? (
          <Sider
            width={220}
            collapsedWidth={0}
            breakpoint="lg"
            theme="light"
            style={{
              borderRight: '1px solid #e5e7eb',
              background: '#f7faff',
              paddingTop: 8,
            }}
          >
            <Menu mode="inline" selectedKeys={selectedMenuKey()} items={sideMenuItems} style={{ borderInlineEnd: 0, background: '#f7faff' }} />
          </Sider>
        ) : null}
        <Content
          style={{
            padding: isMobile ? '14px 10px' : '24px 16px',
            maxWidth: 1380,
            margin: '0 auto',
            width: '100%',
            minHeight: 0,
            height: '100%',
            overflow: isInterviewSessionPage ? 'hidden' : 'auto',
          }}
        >
          {props.children}
        </Content>
      </Layout>
    </Layout>
  )
}
