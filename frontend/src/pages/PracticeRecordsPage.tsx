import { useQuery } from '@tanstack/react-query'
import { Card, Space, Table, Tag, Typography } from 'antd'
import { useParams } from 'react-router-dom'

import { fetchPracticeSessionRecords } from '../api/practice'

/** 题库练习记录页。 */
export function PracticeRecordsPage() {
  const { practiceId = '' } = useParams<{ practiceId: string }>()

  /** 查询单场练习记录。 */
  const recordsQuery = useQuery({
    queryKey: ['practice-session-records', practiceId],
    queryFn: () => fetchPracticeSessionRecords(practiceId),
    enabled: Boolean(practiceId),
  })

  return (
    <Card title="练习记录">
      {recordsQuery.isLoading ? <Typography.Text>加载中...</Typography.Text> : null}
      {recordsQuery.data ? (
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Space wrap>
            <Tag color="blue">岗位：{recordsQuery.data.job_role}</Tag>
            <Tag color="gold">模式：{recordsQuery.data.mode}</Tag>
            <Tag color={recordsQuery.data.status === 'FINISHED' ? 'success' : 'processing'}>
              状态：{recordsQuery.data.status}
            </Tag>
            <Tag color="purple">
              完成：{recordsQuery.data.completed_count}/{recordsQuery.data.total_questions}
            </Tag>
          </Space>
          <Table
            rowKey="session_question_id"
            pagination={false}
            dataSource={recordsQuery.data.items}
            columns={[
              { title: '题号', dataIndex: 'question_order', width: 80 },
              { title: '类别', dataIndex: 'category', width: 120, render: (value?: string) => value || '-' },
              { title: '题目', dataIndex: 'stem' },
              { title: '回答', dataIndex: 'answer_text', render: (value?: string) => value || '未作答' },
            ]}
          />
        </Space>
      ) : null}
      {recordsQuery.isError ? <Typography.Text type="danger">练习记录加载失败</Typography.Text> : null}
    </Card>
  )
}
