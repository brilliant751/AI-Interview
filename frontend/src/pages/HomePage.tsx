import { Button, Card, Col, Row, Space, Typography } from 'antd'
import { Link } from 'react-router-dom'

import { useAuthStore } from '../stores/authStore'

const preparationSteps = [
  {
    title: '整理简历',
    description: '上传简历，保留一份可复用的面试上下文。',
  },
  {
    title: '选择岗位',
    description: '按目标岗位和难度，确定本轮准备范围。',
  },
  {
    title: '模拟作答',
    description: '围绕当前问题回答，保留每一轮记录。',
  },
  {
    title: '复盘报告',
    description: '回看历史记录，整理下一次要改的地方。',
  },
]

const entryCards = [
  {
    title: '模拟面试',
    description: '进入大厅，创建或恢复一场面试。',
    to: '/interview',
  },
  {
    title: '题库练习',
    description: '按方向练习，补齐薄弱题型。',
    to: '/practice',
  },
  {
    title: '历史记录',
    description: '集中查看面试和练习结果。',
    to: '/history',
  },
]

/** 网站首页。 */
export function HomePage() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)

  return (
    <Space direction="vertical" size={24} style={{ width: '100%' }}>
      <Card styles={{ body: { padding: 32 } }}>
        <Row gutter={[32, 32]} align="middle">
          <Col xs={24} lg={14}>
            <Space direction="vertical" size={20} style={{ width: '100%' }}>
              <Space direction="vertical" size={8}>
                <Typography.Title level={1} style={{ margin: 0 }}>
                  面试准备，从流程开始
                </Typography.Title>
                <Typography.Paragraph style={{ margin: 0, fontSize: 16, maxWidth: 660 }} type="secondary">
                  上传简历，选择岗位，完成一轮模拟面试，再根据记录复盘。页面只保留常用入口和准备路径。
                </Typography.Paragraph>
              </Space>
              <Space wrap>
                <Button type="primary" size="large">
                  <Link to={isAuthenticated ? '/interview' : '/login'}>开始面试</Link>
                </Button>
                <Button size="large">
                  <Link to={isAuthenticated ? '/resumes' : '/register'}>{isAuthenticated ? '管理简历' : '创建账号'}</Link>
                </Button>
              </Space>
            </Space>
          </Col>
          <Col xs={24} lg={10}>
            <Card title="今日准备" styles={{ body: { padding: 16 } }}>
              <Space direction="vertical" size={14} style={{ width: '100%' }}>
                {preparationSteps.slice(0, 3).map((item, index) => (
                  <div
                    key={item.title}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '32px 1fr',
                      gap: 12,
                      alignItems: 'start',
                      paddingBottom: index === 2 ? 0 : 14,
                      borderBottom: index === 2 ? undefined : '1px solid #f0f0f0',
                    }}
                  >
                    <Typography.Text strong>{index + 1}</Typography.Text>
                    <Space direction="vertical" size={2}>
                      <Typography.Text strong>{item.title}</Typography.Text>
                      <Typography.Text type="secondary">{item.description}</Typography.Text>
                    </Space>
                  </div>
                ))}
              </Space>
            </Card>
          </Col>
        </Row>
      </Card>

      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          准备路径
        </Typography.Title>
        <Row gutter={[16, 16]}>
          {preparationSteps.map((item, index) => (
            <Col xs={24} md={12} xl={6} key={item.title}>
              <Card style={{ height: '100%' }}>
                <Space direction="vertical" size={8}>
                  <Typography.Text type="secondary">0{index + 1}</Typography.Text>
                  <Typography.Title level={4} style={{ margin: 0 }}>
                    {item.title}
                  </Typography.Title>
                  <Typography.Text type="secondary">{item.description}</Typography.Text>
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
      </Space>

      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          常用入口
        </Typography.Title>
        <Row gutter={[16, 16]}>
          {entryCards.map((item) => (
            <Col xs={24} md={8} key={item.title}>
              <Card
                title={item.title}
                extra={<Link to={isAuthenticated ? item.to : '/login'}>进入</Link>}
                style={{ height: '100%' }}
              >
                <Typography.Text type="secondary">{item.description}</Typography.Text>
              </Card>
            </Col>
          ))}
        </Row>
      </Space>
    </Space>
  )
}
