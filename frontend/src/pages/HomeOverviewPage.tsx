import { useQuery } from '@tanstack/react-query'
import {
  ArrowRightOutlined,
  CalendarOutlined,
  CheckCircleOutlined,
  CheckCircleFilled,
  DotChartOutlined,
  FileTextOutlined,
  LineChartOutlined,
  RadarChartOutlined,
  PlayCircleOutlined,
  RightOutlined,
  RocketOutlined,
  SafetyCertificateOutlined,
  SearchOutlined,
  SoundOutlined,
  TrophyOutlined,
} from '@ant-design/icons'
import { Button, Card, Col, Progress, Row, Space, Table, Tag, Typography } from 'antd'
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'

import { fetchProviderHealth } from '../api/admin'
import { fetchInterviewSchedules } from '../api/interview'
import { buildCalendarDays, groupSchedulesByDate, isSameMonth, startOfMonth, toDateKey } from '../utils/scheduleCalendar'

/** 首页概览页（mock 数据版）。 */
export function HomeOverviewPage() {
  const navigate = useNavigate()
  const healthQuery = useQuery({
    queryKey: ['provider-health', 'overview-page'],
    queryFn: fetchProviderHealth,
    retry: false,
    refetchInterval: 20000,
  })
  const health = healthQuery.data
  const scheduleQuery = useQuery({
    queryKey: ['interview-schedules', 'overview-page'],
    queryFn: () => fetchInterviewSchedules({ page: 1, page_size: 50 }),
  })
  const overviewMonth = startOfMonth(new Date())
  const overviewMonthDays = buildCalendarDays(overviewMonth)
  const scheduleGroups = groupSchedulesByDate((scheduleQuery.data?.items ?? []).filter((item) => !['completed', 'missed', 'cancelled'].includes(item.status)))

  const kpiItems: Array<{ key: string; title: string; value: string; note: string; icon: ReactNode; color: string }> = [
    { key: 'score', title: '平均得分', value: '86 分', note: '较上次 +6 分', icon: <LineChartOutlined />, color: '#357ABD' },
    { key: 'finished', title: '完成面试', value: '12 场', note: '累计完成', icon: <CalendarOutlined />, color: '#4A9BE8' },
    { key: 'focus', title: '待提升能力', value: '项目表达', note: '优先提升方向', icon: <DotChartOutlined />, color: '#f59e0b' },
    { key: 'weekly', title: '本周练习', value: '5 场', note: '较上周 +2 场', icon: <RocketOutlined />, color: '#5B9BD5' },
  ]

  const recentRecords = [
    { key: '1', role: '前端开发工程师', score: 88, level: '中级', suggestion: '建议加强性能优化案例讲解。', status: '已完成' },
    { key: '2', role: 'Java 后端工程师', score: 85, level: '中级', suggestion: '建议补充系统设计思路表达。', status: '已完成' },
    { key: '3', role: '产品经理', score: 82, level: '中级', suggestion: '建议提升数据驱动分析能力。', status: '已完成' },
    { key: '4', role: '测试开发工程师', score: 78, level: '初级', suggestion: '建议强化测试框架使用经验。', status: '进行中' },
  ]

  return (
    <Space className="overview-page" direction="vertical" size={16} style={{ width: '100%' }}>
      <Card className="overview-hero-card">
        <Row gutter={[20, 20]} align="middle">
          <Col xs={24} xl={18}>
            <Typography.Title level={2} style={{ marginTop: 0, marginBottom: 8 }}>
              你好，准备好开始今天的面试练习了吗？
            </Typography.Title>
            <Typography.Paragraph type="secondary" style={{ marginBottom: 18 }}>
              建议优先练习项目表达与技术方案讲解，保持连续练习会更快提升稳定性。
            </Typography.Paragraph>
            <Space wrap>
              <Button type="primary" size="large" icon={<PlayCircleOutlined />} onClick={() => navigate('/interview')}>
                开始新面试
              </Button>
              <Button size="large" icon={<CalendarOutlined />} onClick={() => navigate('/schedules')}>
                预约面试
              </Button>
              <Button size="large" icon={<RocketOutlined />} onClick={() => navigate('/history')}>
                继续上次面试
              </Button>
              <Button size="large" icon={<FileTextOutlined />} onClick={() => navigate('/report')}>
                查看我的报告
              </Button>
            </Space>
          </Col>
          <Col xs={24} xl={6}>
            <Card className="overview-health-card" size="small">
              <Space direction="vertical" size={8} style={{ width: '100%' }}>
                <Space>
                  <CheckCircleFilled style={{ color: health?.overall === 'UP' ? '#4A9BE8' : '#d97706' }} />
                  <Typography.Text strong style={{ color: health?.overall === 'UP' ? '#4A9BE8' : '#d97706' }}>
                    {healthQuery.isLoading ? '系统状态获取中...' : health?.overall === 'UP' ? '系统状态正常' : '系统状态降级'}
                  </Typography.Text>
                </Space>
                <Space style={{ justifyContent: 'space-between', width: '100%' }}>
                  <Space>
                    <SoundOutlined style={{ color: '#357ABD' }} />
                    <Typography.Text type="secondary">语音识别</Typography.Text>
                  </Space>
                  <Typography.Text>{health?.providers?.asr?.status === 'UP' ? '正常' : '异常'}</Typography.Text>
                </Space>
                <Space style={{ justifyContent: 'space-between', width: '100%' }}>
                  <Space>
                    <SafetyCertificateOutlined style={{ color: '#357ABD' }} />
                    <Typography.Text type="secondary">模型服务</Typography.Text>
                  </Space>
                  <Typography.Text>{health?.providers?.llm?.status === 'UP' ? '正常' : '异常'}</Typography.Text>
                </Space>
                <Space style={{ justifyContent: 'space-between', width: '100%' }}>
                  <Space>
                    <SearchOutlined style={{ color: '#357ABD' }} />
                    <Typography.Text type="secondary">向量检索</Typography.Text>
                  </Space>
                  <Typography.Text>{health?.providers?.embed?.status === 'UP' ? '正常' : '异常'}</Typography.Text>
                </Space>
                <Button type="link" style={{ paddingInline: 0 }} onClick={() => navigate('/interview')}>
                  查看系统详情 <RightOutlined />
                </Button>
              </Space>
            </Card>
          </Col>
        </Row>
      </Card>

      <Row gutter={[16, 16]}>
        {kpiItems.map((item) => (
          <Col xs={24} sm={12} xl={6} key={item.title}>
            <Card className="overview-kpi-card">
              <Space>
                <div className="overview-kpi-icon" style={{ color: item.color, background: `${item.color}1A` }}>
                  {item.icon}
                </div>
                <div>
                  <Typography.Text type="secondary">{item.title}</Typography.Text>
                  <Typography.Title level={2} style={{ margin: '4px 0' }}>
                    {item.value}
                  </Typography.Title>
                  <Typography.Text type="secondary">{item.note}</Typography.Text>
                </div>
              </Space>
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={14}>
          <Card className="overview-record-card"
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
                {
                  title: '状态',
                  dataIndex: 'status',
                  render: (value: string) => (
                    <Tag color={value === '已完成' ? 'green' : 'processing'} icon={<CheckCircleOutlined />}>
                      {value}
                    </Tag>
                  ),
                },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} xl={10}>
          <Card
            className="overview-analysis-card"
            title="最近预约"
            extra={
              <Button type="link" onClick={() => navigate('/schedules')}>
                查看日程表 <ArrowRightOutlined />
              </Button>
            }
            style={{ marginBottom: 16 }}
          >
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <Typography.Text type="secondary">{`${overviewMonth.getFullYear()} 年 ${overviewMonth.getMonth() + 1} 月预约概览`}</Typography.Text>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, minmax(0, 1fr))', gap: 6 }}>
                {['一', '二', '三', '四', '五', '六', '日'].map((label) => (
                  <div key={label} style={{ textAlign: 'center', fontSize: 12, color: '#6b7280', fontWeight: 600 }}>
                    {label}
                  </div>
                ))}
                {overviewMonthDays.map((day) => {
                  const dayKey = toDateKey(day)
                  const daySchedules = scheduleGroups.get(dayKey) ?? []
                  const highlightColor = daySchedules.some((item) => item.status === 'ready')
                    ? '#4A9BE8'
                    : daySchedules.some((item) => item.status === 'in_progress')
                      ? '#d97706'
                      : '#1677ff'
                  return (
                    <button
                      key={dayKey}
                      type="button"
                      onClick={() => navigate('/schedules')}
                      style={{
                        minHeight: 54,
                        borderRadius: 12,
                        border: '1px solid #e5e7eb',
                        background: isSameMonth(day, overviewMonth) ? '#fff' : '#f8fafc',
                        padding: 6,
                        cursor: 'pointer',
                      }}
                    >
                      <Space direction="vertical" size={4} style={{ width: '100%', alignItems: 'center' }}>
                        <Typography.Text style={{ color: isSameMonth(day, overviewMonth) ? '#111827' : '#9ca3af', fontSize: 12 }}>
                          {day.getDate()}
                        </Typography.Text>
                        {daySchedules.length > 0 ? (
                          <Tag color={highlightColor} style={{ marginInlineEnd: 0, fontSize: 11 }}>
                            {daySchedules.length}
                          </Tag>
                        ) : null}
                      </Space>
                    </button>
                  )
                })}
              </div>
              <Typography.Text type="secondary">
                {scheduleGroups.size > 0 ? '点击日程表进入完整预约页查看详情。' : '还没有待进行的预约，先约一场更容易坚持练习。'}
              </Typography.Text>
            </Space>
          </Card>
          <Card className="overview-analysis-card" title="能力分析">
            <Row gutter={[16, 12]} align="middle">
              <Col xs={24} md={10}>
                <Space direction="vertical" style={{ width: '100%', alignItems: 'center' }}>
                  <Progress type="circle" percent={86} format={(percent) => `${percent}分`} />
                  <Space size={6}>
                    <RadarChartOutlined style={{ color: '#357ABD' }} />
                    <Typography.Text type="secondary">综合得分</Typography.Text>
                  </Space>
                </Space>
              </Col>
              <Col xs={24} md={14}>
                <Space direction="vertical" size={10} style={{ width: '100%' }}>
                  <div>
                    <Typography.Text>表达能力</Typography.Text>
                    <Progress percent={89} showInfo={false} />
                  </div>
                  <div>
                    <Typography.Text>逻辑思维</Typography.Text>
                    <Progress percent={86} showInfo={false} />
                  </div>
                  <div>
                    <Typography.Text>专业知识</Typography.Text>
                    <Progress percent={88} showInfo={false} />
                  </div>
                  <div>
                    <Typography.Text>沟通技巧</Typography.Text>
                    <Progress percent={82} showInfo={false} />
                  </div>
                  <div>
                    <Typography.Text>抗压能力</Typography.Text>
                    <Progress percent={75} showInfo={false} />
                  </div>
                </Space>
              </Col>
            </Row>
            <Tag icon={<TrophyOutlined />} color="blue" style={{ marginTop: 10 }}>
              你的专业知识表现优秀，建议重点提升抗压与表达稳定性。
            </Tag>
          </Card>
        </Col>
      </Row>
    </Space>
  )
}
