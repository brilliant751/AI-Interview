import { ArrowRightOutlined, TrophyOutlined } from '@ant-design/icons'
import { Button, Card, Col, Progress, Row, Space, Statistic, Table, Tag, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'

/** 首页概览页（mock 数据版）。 */
export function HomeOverviewPage() {
  const navigate = useNavigate()

  const kpiItems = [
    { title: '平均得分', value: 86, suffix: '分' },
    { title: '完成面试', value: 12, suffix: '场' },
    { title: '待提升能力', value: '项目表达', suffix: '' },
  ]

  const recentRecords = [
    { key: '1', role: '前端开发工程师', score: 88, level: '中级', suggestion: '建议加强性能优化案例讲解。' },
    { key: '2', role: 'Java 后端工程师', score: 85, level: '中级', suggestion: '建议补充系统设计思路表达。' },
    { key: '3', role: '产品经理', score: 82, level: '中级', suggestion: '建议提升数据驱动分析能力。' },
  ]

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card
        style={{
          background: 'linear-gradient(120deg, #e8f0ff 0%, #dbe8ff 60%, #f1f5ff 100%)',
          border: '1px solid #d3e3ff',
        }}
      >
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} xl={16}>
            <Typography.Title level={3} style={{ marginTop: 0 }}>
              你好，准备好开始今天的面试练习了吗？
            </Typography.Title>
            <Typography.Paragraph type="secondary">
              建议优先练习项目表达与技术方案讲解，保持连续练习会更快提升稳定性。
            </Typography.Paragraph>
            <Space wrap>
              <Button type="primary" size="large" onClick={() => navigate('/interview')}>
                开始新面试
              </Button>
              <Button size="large" onClick={() => navigate('/history')}>
                继续上次面试
              </Button>
              <Button size="large" onClick={() => navigate('/report')}>
                查看我的报告
              </Button>
            </Space>
          </Col>
          <Col xs={24} xl={8}>
            <Card size="small" style={{ borderRadius: 12 }}>
              <Space direction="vertical" size={8} style={{ width: '100%' }}>
                <Tag color="green">系统状态正常</Tag>
                <Typography.Text type="secondary">语音、模型、向量检索均可用，支持完整面试链路。</Typography.Text>
              </Space>
            </Card>
          </Col>
        </Row>
      </Card>

      <Row gutter={[16, 16]}>
        {kpiItems.map((item) => (
          <Col xs={24} sm={12} xl={6} key={item.title}>
            <Card>
              <Statistic title={item.title} value={item.value} suffix={item.suffix} />
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={14}>
          <Card
            title="最近面试记录"
            extra={
              <Button type="link" onClick={() => navigate('/history')}>
                查看全部 <ArrowRightOutlined />
              </Button>
            }
          >
            <Table
              rowKey="key"
              pagination={false}
              dataSource={recentRecords}
              columns={[
                { title: '岗位', dataIndex: 'role' },
                {
                  title: '得分',
                  dataIndex: 'score',
                  render: (value: number) => (
                    <Space>
                      <Typography.Text strong>{value}</Typography.Text>
                      <Tag color={value >= 85 ? 'green' : 'gold'}>{value >= 85 ? '良好' : '可提升'}</Tag>
                    </Space>
                  ),
                },
                { title: '难度', dataIndex: 'level' },
                { title: '建议', dataIndex: 'suggestion' },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} xl={10}>
          <Card title="能力分析">
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <Space style={{ justifyContent: 'center', width: '100%' }}>
                <Progress type="circle" percent={86} format={(percent) => `${percent}分`} />
              </Space>
              <div>
                <Typography.Text>表达能力</Typography.Text>
                <Progress percent={85} showInfo={false} />
              </div>
              <div>
                <Typography.Text>逻辑思维</Typography.Text>
                <Progress percent={88} showInfo={false} />
              </div>
              <div>
                <Typography.Text>专业知识</Typography.Text>
                <Progress percent={90} showInfo={false} />
              </div>
              <Tag icon={<TrophyOutlined />} color="blue">
                你的专业知识表现优秀，建议重点提升抗压与表达稳定性。
              </Tag>
            </Space>
          </Card>
        </Col>
      </Row>
    </Space>
  )
}
