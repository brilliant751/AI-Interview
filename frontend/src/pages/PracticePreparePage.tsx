import { useMutation, useQuery } from '@tanstack/react-query'
import { Alert, Button, Card, Checkbox, Col, Radio, Row, Space, Statistic, Tag, Typography, message } from 'antd'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import {
  createPracticeSession,
  fetchPracticeOverview,
  fetchPracticeRecords,
  type PracticeOverviewRoleStats,
  type PracticeCategory,
  type PracticeMode,
} from '../api/practice'
import { parseApiError } from '../api/client'
import { usePracticeStore } from '../stores/practiceStore'

/** 题目类别选项。 */
const CATEGORY_OPTIONS: Array<{ label: string; value: PracticeCategory }> = [
  { label: '技术', value: 'technical' },
  { label: '项目', value: 'project' },
  { label: '场景', value: 'scenario' },
  { label: '行为', value: 'behavior' },
]

/** 岗位标签映射。 */
const JOB_ROLE_LABELS: Record<'java' | 'web', string> = {
  java: 'Java',
  web: 'Web',
}

/** 时间格式化。 */
function formatDateTime(value: string): string {
  const normalized = value.includes('T') ? value : value.replace(' ', 'T')
  const date = new Date(`${normalized}Z`)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString('zh-CN', { hour12: false })
}

/** 题库练习准备页。 */
export function PracticePreparePage() {
  const navigate = useNavigate()
  const setSession = usePracticeStore((state) => state.setSession)
  const [selectedRole, setSelectedRole] = useState<'java' | 'web' | 'all'>('all')
  const [mode, setMode] = useState<PracticeMode>('sequence')
  const [questionCount, setQuestionCount] = useState(10)
  const [categoryFilters, setCategoryFilters] = useState<PracticeCategory[]>([])

  /** 查询题库首页聚合信息。 */
  const overviewQuery = useQuery({
    queryKey: ['practice-overview'],
    queryFn: fetchPracticeOverview,
  })

  /** 查询当前用户练习记录，用于继续练习提醒。 */
  const recordsQuery = useQuery({
    queryKey: ['practice-records'],
    queryFn: fetchPracticeRecords,
  })

  /** 提取未结束会话。 */
  const activeRecord = useMemo(
    () => recordsQuery.data?.items.find((item) => item.status === 'ACTIVE') || null,
    [recordsQuery.data?.items],
  )

  /** 构建岗位卡片列表。 */
  const roleCards = useMemo(() => {
    const roles = overviewQuery.data?.role_stats || []
    if (selectedRole === 'all') {
      return roles
    }
    return roles.filter((item) => item.job_role === selectedRole)
  }, [overviewQuery.data?.role_stats, selectedRole])

  /** 创建练习会话。 */
  const createMutation = useMutation({
    mutationFn: createPracticeSession,
    onSuccess: (data) => {
      setSession(data)
      message.success('练习已开始')
      navigate(`/practice/${data.practice_id}`)
    },
    onError: (error) => {
      const parsed = parseApiError(error)
      message.error(parsed.message)
    },
  })

  /** 处理开始练习动作。 */
  const handleStart = (roleItem: PracticeOverviewRoleStats) => {
    if (roleItem.latest_active_practice_id) {
      navigate(`/practice/${roleItem.latest_active_practice_id}`)
      return
    }
    createMutation.mutate({
      job_role: roleItem.job_role,
      mode,
      question_count: questionCount,
      category_filters: categoryFilters,
    })
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 14, width: '100%' }}>
      <Space direction="vertical" size={14} style={{ width: '100%' }}>
        <Card styles={{ body: { padding: 22 } }}>
          <Typography.Title level={2} style={{ marginTop: 0, marginBottom: 8 }}>
            题库练习
          </Typography.Title>
          <Typography.Paragraph style={{ marginBottom: 0, color: '#5e697a' }}>
            直接从真实题库抽题做练习，支持岗位筛选、固定题单和后续追问式模式扩展。
          </Typography.Paragraph>
          <Row gutter={12} style={{ marginTop: 18 }}>
            <Col span={6}>
              <Statistic title="题库总题量" value={overviewQuery.data?.total_questions || 0} />
            </Col>
            <Col span={6}>
              <Statistic title="累计作答" value={overviewQuery.data?.total_answered_questions || 0} />
            </Col>
            <Col span={6}>
              <Statistic title="练习会话" value={overviewQuery.data?.total_sessions || 0} />
            </Col>
            <Col span={6}>
              <Statistic title="进行中" value={overviewQuery.data?.active_sessions || 0} />
            </Col>
          </Row>
          {activeRecord ? (
            <Alert
              style={{ marginTop: 14 }}
              type="info"
              showIcon
              message="发现未结束练习"
              description={
                <Space direction="vertical" size={8}>
                  <Space wrap>
                    <Tag color="blue">岗位：{activeRecord.job_role}</Tag>
                    <Tag color="gold">模式：{activeRecord.mode}</Tag>
                    <Tag color="purple">
                      进度：{activeRecord.answered_count}/{activeRecord.total_questions}
                    </Tag>
                  </Space>
                  <Button type="link" style={{ paddingInline: 0 }} onClick={() => navigate(`/practice/${activeRecord.practice_id}`)}>
                    继续当前练习
                  </Button>
                </Space>
              }
            />
          ) : null}
        </Card>

        <Card styles={{ body: { padding: 16 } }}>
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Space wrap>
              <Tag color="processing">岗位方向</Tag>
              <Radio.Group
                value={selectedRole}
                onChange={(event) => setSelectedRole(event.target.value)}
                options={[
                  { label: '全部', value: 'all' },
                  { label: 'Java', value: 'java' },
                  { label: 'Web', value: 'web' },
                ]}
              />
            </Space>
            <Space wrap>
              <Tag color="processing">练习模式</Tag>
              <Radio.Group
                value={mode}
                onChange={(event) => setMode(event.target.value)}
                options={[
                  { label: '固定题单', value: 'sequence' },
                  { label: '追问式（预留）', value: 'followup' },
                ]}
              />
            </Space>
            <Space wrap>
              <Tag color="processing">题量</Tag>
              <Radio.Group
                value={questionCount}
                onChange={(event) => setQuestionCount(event.target.value)}
                options={[5, 10, 15, 20].map((item) => ({ label: `${item} 题`, value: item }))}
              />
            </Space>
            <Space wrap>
              <Tag color="processing">题目类别</Tag>
              <Checkbox.Group options={CATEGORY_OPTIONS} value={categoryFilters} onChange={(values) => setCategoryFilters(values as PracticeCategory[])} />
            </Space>
          </Space>
        </Card>

        <Card styles={{ body: { padding: 16 } }} loading={overviewQuery.isLoading}>
          <Row gutter={[12, 12]}>
            {roleCards.map((roleItem) => (
              <Col span={12} key={roleItem.job_role}>
                <Card
                  size="small"
                  title={`${JOB_ROLE_LABELS[roleItem.job_role]} 题库练习`}
                  extra={<Tag color={roleItem.active_sessions > 0 ? 'gold' : 'green'}>{roleItem.active_sessions > 0 ? '有进行中' : '可新开练习'}</Tag>}
                >
                  <Space direction="vertical" size={8} style={{ width: '100%' }}>
                    <Space wrap>
                      <Tag>单选题</Tag>
                      <Tag>题量 {roleItem.total_questions}</Tag>
                      <Tag>完成 {roleItem.finished_sessions}</Tag>
                    </Space>
                    <Typography.Text type="secondary">累计作答 {roleItem.answered_questions} 题</Typography.Text>
                    <Typography.Text type="secondary">覆盖率 {(roleItem.completion_rate * 100).toFixed(1)}%</Typography.Text>
                    <Button type="primary" block onClick={() => handleStart(roleItem)} loading={createMutation.isPending}>
                      {roleItem.active_sessions > 0 ? '继续该岗位练习' : '开始该岗位练习'}
                    </Button>
                  </Space>
                </Card>
              </Col>
            ))}
          </Row>
        </Card>
      </Space>

      <Space direction="vertical" size={14} style={{ width: '100%' }}>
        <Card title="练习历史" size="small">
          <Space direction="vertical" size={10} style={{ width: '100%' }}>
            {(overviewQuery.data?.recent_records || []).map((record) => (
              <Card key={record.practice_id} size="small" style={{ background: '#fafcff' }}>
                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  <Space wrap>
                    <Tag color="blue">{JOB_ROLE_LABELS[record.job_role]}</Tag>
                    <Tag color={record.status === 'ACTIVE' ? 'processing' : 'success'}>{record.status}</Tag>
                  </Space>
                  <Typography.Text>
                    进度 {record.answered_count}/{record.total_questions}
                  </Typography.Text>
                  <Typography.Text type="secondary">{formatDateTime(record.created_at)}</Typography.Text>
                  <Button type="link" style={{ paddingInline: 0 }} onClick={() => navigate(`/practice/${record.practice_id}`)}>
                    {record.status === 'ACTIVE' ? '继续作答' : '查看记录'}
                  </Button>
                </Space>
              </Card>
            ))}
            {(overviewQuery.data?.recent_records || []).length === 0 ? <Typography.Text type="secondary">暂无练习记录</Typography.Text> : null}
          </Space>
        </Card>
        <Card title="岗位统计" size="small">
          <Space direction="vertical" size={10} style={{ width: '100%' }}>
            {(overviewQuery.data?.role_stats || []).map((item) => (
              <Card key={item.job_role} size="small">
                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  <Typography.Text strong>{JOB_ROLE_LABELS[item.job_role]}</Typography.Text>
                  <Typography.Text type="secondary">题量 {item.total_questions} · 活跃 {item.active_sessions}</Typography.Text>
                  <Typography.Text type="secondary">累计作答 {item.answered_questions}</Typography.Text>
                </Space>
              </Card>
            ))}
          </Space>
        </Card>
      </Space>
    </div>
  )
}
