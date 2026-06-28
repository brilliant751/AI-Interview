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
import { useQuery } from '@tanstack/react-query'
import { Badge, Button, Dropdown, Layout, Menu, Space, Typography, notification } from 'antd'
import type { MenuProps } from 'antd'
import type { ReactNode } from 'react'
import { useEffect, useMemo } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { logout } from '../api/auth'
import { fetchScheduledInterviews } from '../api/interview'
import { useAuthStore } from '../stores/authStore'

const { Header, Content, Sider } = Layout

// AppLayout 是登录后页面的共同外壳：
// 1. 负责顶部栏、侧边栏、移动端菜单和用户下拉菜单。
// 2. 登录态从 authStore 读取，退出登录时同步通知后端并清本地会话。
// 3. 今日面试提醒通过 React Query 定时刷新，避免用户错过预约。
// 4. 管理员菜单只在 user.role === 'admin' 时显示，和路由保护保持一致。
// 5. 面试进行页会隐藏或弱化部分导航，减少用户在会话中误操作跳出。

/** 应用主布局。 */
export function AppLayout(props: { children: ReactNode }) {
  const location = useLocation()
  const navigate = useNavigate()
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const user = useAuthStore((state) => state.user)
  const refreshToken = useAuthStore((state) => state.refreshToken)
  const clearSession = useAuthStore((state) => state.clearSession)
  const isInterviewSessionPage = /^\/interview\/[^/]+/.test(location.pathname)
  const [notificationApi, notificationContextHolder] = notification.useNotification()

  const buildTodayRange = () => {
    // 后端按 ISO 时间解析，前端用本地当天 00:00-23:59 覆盖“今天”的用户感知。
    // 这样跨时区浏览器也能明确告诉服务端本次查询的时间边界。
    const now = new Date()
    const start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0)
    const end = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59, 999)
    return {
      scheduled_from: start.toISOString(),
      scheduled_to: end.toISOString(),
    }
  }

  const todayScheduleQuery = useQuery({
    // 顶部提醒只需要今天的预约数据，且登录后才发起请求。
    // 60 秒刷新一次能兼顾实时性和接口压力。
    queryKey: ['today-interview-schedules', isAuthenticated],
    queryFn: () =>
      fetchScheduledInterviews({
        ...buildTodayRange(),
        statuses: ['SCHEDULED', 'ACTIVE', 'PAUSED'],
      }),
    enabled: isAuthenticated,
    refetchInterval: isAuthenticated ? 60000 : false,
  })
  const todayScheduleItems = useMemo(() => todayScheduleQuery.data?.items ?? [], [todayScheduleQuery.data?.items])
  const todayPendingCount = todayScheduleItems.length

  useEffect(() => {
    // 同一天同一批预约状态只提醒一次。
    // fingerprint 包含 interview_id 和 status，预约状态变化后允许再次提醒。
    if (!isAuthenticated || todayScheduleItems.length === 0) {
      return
    }
    const todayKey = new Date().toISOString().slice(0, 10)
    const reminderKey = `ai_interview_schedule_notice_${todayKey}`
    const currentFingerprint = todayScheduleItems.map((item) => `${item.interview_id}:${item.status}`).join('|')
    if (window.localStorage.getItem(reminderKey) === currentFingerprint) {
      return
    }
    notificationApi.open({
      key: reminderKey,
      message: `今天有 ${todayScheduleItems.length} 场面试安排`,
      description: '请前往 AI 面试大厅查看预约详情；到点后可直接开始面试。',
      duration: 6,
      btn: (
        <Button size="small" type="primary" onClick={() => navigate('/interview')}>
          查看安排
        </Button>
      ),
      onClose: () => {
        window.localStorage.setItem(reminderKey, currentFingerprint)
      },
    })
  }, [isAuthenticated, navigate, notificationApi, todayScheduleItems])

  const sideMenuItems: MenuProps['items'] = [
    { key: '/overview', icon: <HomeOutlined />, label: <Link to="/overview">首页概览</Link> },
    { key: '/schedules', icon: <ScheduleOutlined />, label: <Link to="/schedules">面试预约</Link> },
    { key: '/interview', icon: <FormOutlined />, label: <Link to="/interview">AI 面试</Link> },
    { key: '/practice', icon: <ReadOutlined />, label: <Link to="/practice">题库练习</Link> },
    { key: '/coding-practice', icon: <ReadOutlined />, label: <Link to="/coding-practice">编程练习</Link> },
    { key: '/history', icon: <FileTextOutlined />, label: <Link to="/history">面试记录</Link> },
    { key: '/report', icon: <FileTextOutlined />, label: <Link to="/report">我的报告</Link> },
    { key: '/jobs', icon: <BookOutlined />, label: <Link to="/jobs">岗位库</Link> },
    { key: '/resumes', icon: <TeamOutlined />, label: <Link to="/resumes">简历管理</Link> },
  ]
  if (user?.role === 'admin') {
    // 管理菜单在运行时追加，普通用户不会在侧边栏看到导入和题库维护入口。
    sideMenuItems.push({ key: '/admin/imports', icon: <UserOutlined />, label: <Link to="/admin/imports">知识库重建</Link> })
    sideMenuItems.push({ key: '/admin/questions', icon: <UserOutlined />, label: <Link to="/admin/questions">题库管理</Link> })
  }

  const selectedMenuKey = () => {
    const pathName = location.pathname
    const allKeys = sideMenuItems?.map((item) => String(item?.key || '')) || []
    const matched = allKeys.find((key) => pathName.startsWith(key))
    return matched ? [matched] : ['/overview']
  }

  const handleLogout = async () => {
    // logout 接口失败也要清理本地会话，因为用户已经明确选择退出。
    // 后端 refresh token 失效时，finally 仍会把前端状态恢复为未登录。
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
    <Layout className={`app-shell ${isAuthenticated ? 'is-authenticated' : 'is-public'}`}>
      {notificationContextHolder}
      {isAuthenticated ? (
        <Header className="app-header">
          <Space size={10}>
            <Typography.Title level={4} className="app-header-title">
              AI Interview
            </Typography.Title>
            <Typography.Text className="app-header-subtitle">面试训练工作台</Typography.Text>
          </Space>
          <Space size={14}>
            <Badge count={todayPendingCount} size="small">
              <Button shape="circle" icon={<BellOutlined />} onClick={() => navigate('/interview')} />
            </Badge>
            <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
              <Button icon={<UserOutlined />}>{user?.display_name || user?.email?.split('@')[0] || '用户'}</Button>
            </Dropdown>
          </Space>
        </Header>
      ) : null}
      <Layout className="app-body">
        {isAuthenticated ? (
          <Sider width={220} collapsedWidth={0} breakpoint="lg" theme="light" className="app-sider">
            <Menu mode="inline" selectedKeys={selectedMenuKey()} items={sideMenuItems} className="app-menu" />
          </Sider>
        ) : null}
        <Content className="app-content" data-interview-session={isInterviewSessionPage ? 'true' : 'false'}>
          {props.children}
        </Content>
      </Layout>
    </Layout>
  )
}
