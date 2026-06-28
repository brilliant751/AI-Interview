import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Card, List, Select, Space, Spin, Table, Tag, Typography } from 'antd'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { fetchReport, fetchReportList, retryReport } from '../api/interview'
import { useInterviewStore } from '../stores/interviewStore'

// 报告页支持两种入口：
// 1. /report 展示当前用户报告列表，并可选择某一场报告。
// 2. /report/:interviewId 直接打开指定面试报告。
// 3. 报告可能处于 GENERATING/FAILED/SUCCESS，页面根据状态展示等待、失败或结果。
// 4. retryReport 只负责重新触发后台任务，页面随后通过查询刷新结果。
// 5. 雷达图使用本地 SVG 绘制，避免引入额外图表库。

/** 六维雷达图。 */
function RadarHexagon(props: { dimensions: Array<{ dimension: string; capability_score: number }> }) {
  const dimensions = props.dimensions.slice(0, 6)
  const size = 320
  const center = size / 2
  const maxRadius = 110
  const levels = [1, 2, 3, 4, 5]
  const angleStep = (Math.PI * 2) / Math.max(dimensions.length, 6)

  const toPoint = (index: number, score: number) => {
    const angle = -Math.PI / 2 + index * angleStep
    const radius = (Math.max(1, Math.min(5, score)) / 5) * maxRadius
    return {
      x: center + Math.cos(angle) * radius,
      y: center + Math.sin(angle) * radius,
    }
  }

  const polygonPoints = dimensions
    .map((item, index) => {
      const point = toPoint(index, item.capability_score)
      return `${point.x},${point.y}`
    })
    .join(' ')

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label="六维能力雷达图">
      {levels.map((level) => {
        const levelPoints = Array.from({ length: Math.max(dimensions.length, 6) }, (_, index) => {
          const point = toPoint(index, level)
          return `${point.x},${point.y}`
        }).join(' ')
        return <polygon key={level} points={levelPoints} fill="none" stroke="#d9d9d9" strokeWidth="1" />
      })}

      {Array.from({ length: Math.max(dimensions.length, 6) }, (_, index) => {
        const edge = toPoint(index, 5)
        return <line key={`axis-${index}`} x1={center} y1={center} x2={edge.x} y2={edge.y} stroke="#e5e7eb" />
      })}

      <polygon points={polygonPoints} fill="rgba(24, 144, 255, 0.25)" stroke="#1677ff" strokeWidth="2" />

      {dimensions.map((item, index) => {
        const labelPoint = toPoint(index, 5.6)
        const valuePoint = toPoint(index, item.capability_score)
        return (
          <g key={item.dimension}>
            <circle cx={valuePoint.x} cy={valuePoint.y} r="3" fill="#1677ff" />
            <text x={labelPoint.x} y={labelPoint.y} fontSize="12" textAnchor="middle" fill="#1f2937">
              {item.dimension}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

/** 报告页面。 */
export function ReportPage() {
  const navigate = useNavigate()
  const params = useParams<{ interviewId?: string }>()
  const queryClient = useQueryClient()
  const storeInterviewId = useInterviewStore((state) => state.interviewId)
  const interviewId = params.interviewId || storeInterviewId
  const [statusFilter, setStatusFilter] = useState<'GENERATING' | 'READY' | 'FAILED' | undefined>(undefined)
  const [listPage, setListPage] = useState(1)

  /** 轮询查询报告状态。 */
  const reportQuery = useQuery({
    queryKey: ['report', interviewId],
    queryFn: () => fetchReport(interviewId),
    enabled: Boolean(interviewId),
    refetchInterval: (query) => (query.state.data?.status === 'READY' ? false : 2000),
  })

  /** 触发报告重试。 */
  const retryMutation = useMutation({
    mutationFn: () => retryReport(interviewId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['report', interviewId] })
    },
  })

  /** 查询我的报告列表。 */
  const reportListQuery = useQuery({
    queryKey: ['report-list', listPage, statusFilter],
    queryFn: () => fetchReportList({ page: listPage, page_size: 10, status: statusFilter }),
    enabled: !interviewId,
  })

  if (!interviewId) {
    return (
      <Card title="我的报告">
        <Space style={{ marginBottom: 16 }}>
          <Select
            allowClear
            placeholder="按状态筛选"
            style={{ width: 180 }}
            options={[
              { label: '生成中', value: 'GENERATING' },
              { label: '已完成', value: 'READY' },
              { label: '生成失败', value: 'FAILED' },
            ]}
            onChange={(value) => {
              setListPage(1)
              setStatusFilter(value)
            }}
          />
          <Button type="primary" onClick={() => navigate('/upload')}>
            开始新面试
          </Button>
        </Space>
        <Table
          rowKey="interview_id"
          loading={reportListQuery.isLoading}
          dataSource={reportListQuery.data?.items ?? []}
          pagination={{
            current: listPage,
            pageSize: 10,
            total: reportListQuery.data?.total ?? 0,
            onChange: (page) => setListPage(page),
          }}
          columns={[
            { title: '面试名称', dataIndex: 'session_name', render: (value?: string) => value || '-' },
            { title: '岗位', dataIndex: 'job_role' },
            { title: '难度', dataIndex: 'difficulty' },
            {
              title: '状态',
              dataIndex: 'status',
              render: (value: 'GENERATING' | 'READY' | 'FAILED') => (
                <Tag color={value === 'READY' ? 'green' : value === 'FAILED' ? 'red' : 'blue'}>{value}</Tag>
              ),
            },
            { title: '总分', dataIndex: 'overall_score', render: (value?: number) => value ?? '--' },
            { title: '更新时间', dataIndex: 'updated_at' },
            {
              title: '操作',
              key: 'actions',
              render: (_, row: { interview_id: string }) => (
                <Button size="small" type="link" onClick={() => navigate(`/report/${row.interview_id}`)}>
                  查看详情
                </Button>
              ),
            },
          ]}
        />
        {reportListQuery.isError && <Typography.Text type="danger">报告列表加载失败，请稍后重试。</Typography.Text>}
      </Card>
    )
  }

  if (reportQuery.isLoading) {
    return (
      <Card>
        <Spin />
      </Card>
    )
  }

  const report = reportQuery.data
  if (!report) {
    return <Card>报告加载失败</Card>
  }

  return (
    <Card title="面试报告">
      <Tag color={report.status === 'READY' ? 'green' : report.status === 'FAILED' ? 'red' : 'blue'}>
        状态：{report.status}
      </Tag>
      {report.status === 'FAILED' && (
        <Button
          size="small"
          type="primary"
          style={{ marginLeft: 8 }}
          loading={retryMutation.isPending}
          onClick={() => retryMutation.mutate()}
        >
          重试生成
        </Button>
      )}
      <Typography.Paragraph style={{ marginTop: 12 }}>
        总分：{typeof report.overall_score === 'number' ? report.overall_score : '--'}
      </Typography.Paragraph>

      <Typography.Title level={5}>优势</Typography.Title>
      <List bordered dataSource={report.strengths} renderItem={(item) => <List.Item>{item}</List.Item>} />

      <Typography.Title level={5} style={{ marginTop: 16 }}>
        待改进
      </Typography.Title>
      <List bordered dataSource={report.weaknesses} renderItem={(item) => <List.Item>{item}</List.Item>} />

      <Typography.Title level={5} style={{ marginTop: 16 }}>
        建议
      </Typography.Title>
      <List bordered dataSource={report.suggestions} renderItem={(item) => <List.Item>{item}</List.Item>} />

      <Typography.Title level={5} style={{ marginTop: 16 }}>
        录用建议
      </Typography.Title>
      <Typography.Paragraph>{report.final_recommendation || '--'}</Typography.Paragraph>

      <Typography.Title level={5}>维度评分（能力分 + 匹配分）</Typography.Title>
      {report.dimension_scores.length >= 3 && (
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 12 }}>
          <RadarHexagon dimensions={report.dimension_scores} />
        </div>
      )}
      <Table
        size="small"
        rowKey={(item) => item.dimension}
        pagination={false}
        dataSource={report.dimension_scores}
        columns={[
          { title: '维度', dataIndex: 'dimension' },
          { title: '能力分', dataIndex: 'capability_score' },
          { title: '匹配分', dataIndex: 'match_score' },
          { title: '置信度', dataIndex: 'confidence' },
          { title: '关键证据', dataIndex: 'evidence' },
        ]}
      />

      <Typography.Title level={5} style={{ marginTop: 16 }}>
        JD-简历-回答对齐
      </Typography.Title>
      <Table
        size="small"
        rowKey={(item) => `${item.jd_skill}-${item.priority}`}
        pagination={false}
        dataSource={report.jd_resume_alignment}
        columns={[
          { title: 'JD能力项', dataIndex: 'jd_skill' },
          { title: '优先级', dataIndex: 'priority' },
          { title: '简历证据', dataIndex: 'resume_evidence' },
          { title: '回答证据', dataIndex: 'answer_evidence' },
          { title: '状态', dataIndex: 'status' },
          { title: '备注', dataIndex: 'note' },
        ]}
      />

      <Typography.Title level={5} style={{ marginTop: 16 }}>
        关键问题深度分析
      </Typography.Title>
      <List
        bordered
        dataSource={report.question_deep_dives}
        renderItem={(item) => (
          <List.Item>
            <div style={{ width: '100%' }}>
              <Typography.Text strong>
                Q{item.question_no}：{item.question}
              </Typography.Text>
              <Typography.Paragraph style={{ marginTop: 8, marginBottom: 4 }}>
                题目意图：{item.intent}
              </Typography.Paragraph>
              <Typography.Paragraph style={{ marginBottom: 4 }}>回答摘要：{item.answer_summary}</Typography.Paragraph>
              <Typography.Paragraph style={{ marginBottom: 4 }}>
                命中率：{item.hit_rate}% ｜ 深度层级：{item.depth_level} ｜ 简历关联：{item.resume_relevance} ｜ JD关联：
                {item.jd_relevance}
              </Typography.Paragraph>
              <Typography.Paragraph style={{ marginBottom: 4 }}>表现亮点：{item.strengths}</Typography.Paragraph>
              <Typography.Paragraph style={{ marginBottom: 8 }}>能力缺口：{item.gaps}</Typography.Paragraph>
              <List
                size="small"
                bordered
                dataSource={item.follow_up_questions}
                renderItem={(question) => <List.Item>{question}</List.Item>}
              />
            </div>
          </List.Item>
        )}
      />

      <Typography.Title level={5} style={{ marginTop: 16 }}>
        风险清单
      </Typography.Title>
      <List bordered dataSource={report.key_risks} renderItem={(item) => <List.Item>{item}</List.Item>} />
    </Card>
  )
}
