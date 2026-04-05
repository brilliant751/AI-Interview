import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Card, List, Spin, Tag, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'

import { fetchReport, retryReport } from '../api/interview'
import { useInterviewStore } from '../stores/interviewStore'

/** 报告页面。 */
export function ReportPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const interviewId = useInterviewStore((state) => state.interviewId)

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

  if (!interviewId) {
    return (
      <Card>
        <Typography.Text>暂无报告，请先完成一次面试。</Typography.Text>
        <div style={{ marginTop: 12 }}>
          <Button type="primary" onClick={() => navigate('/upload')}>
            开始面试
          </Button>
        </div>
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
    </Card>
  )
}
