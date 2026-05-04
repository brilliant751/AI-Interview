import { useQuery } from '@tanstack/react-query'
import { Card, Descriptions, Space, Tag, Timeline, Typography } from 'antd'
import { useParams } from 'react-router-dom'

import { fetchInterviewPlayback } from '../api/interview'

/** 面试回放详情页。 */
export function InterviewPlaybackPage() {
  const { interviewId = '' } = useParams()

  /** 查询回放详情。 */
  const playbackQuery = useQuery({
    queryKey: ['playback', interviewId],
    queryFn: () => fetchInterviewPlayback(interviewId),
    enabled: Boolean(interviewId),
  })

  if (!interviewId) {
    return (
      <Card>
        <Typography.Text>缺少会话 ID。</Typography.Text>
      </Card>
    )
  }

  if (playbackQuery.isLoading) {
    return <Card loading title="面试回放" />
  }

  if (playbackQuery.isError || !playbackQuery.data) {
    return (
      <Card title="面试回放">
        <Typography.Text type="danger">回放加载失败</Typography.Text>
      </Card>
    )
  }

  const data = playbackQuery.data

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card title="面试回放">
        <Descriptions column={1} size="small">
          <Descriptions.Item label="会话 ID">{data.interview_id}</Descriptions.Item>
          <Descriptions.Item label="简历">{data.resume.file_name}</Descriptions.Item>
          <Descriptions.Item label="岗位">{data.meta.job_role}</Descriptions.Item>
          <Descriptions.Item label="难度">{data.meta.difficulty}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color="blue">{data.meta.status}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="开始时间">{data.meta.started_at}</Descriptions.Item>
          <Descriptions.Item label="结束时间">{data.meta.finished_at || '-'}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="问答回放">
        <Timeline
          items={data.turns.map((turn) => ({
            children: (
              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                <Typography.Text strong>第 {turn.sequence} 轮</Typography.Text>
                <Typography.Text>问题：{turn.question}</Typography.Text>
                <Typography.Text>回答：{turn.answer || '（空）'}</Typography.Text>
                <Typography.Text type="secondary">时间：{turn.question_ts}</Typography.Text>
              </Space>
            ),
          }))}
        />
      </Card>
    </Space>
  )
}
