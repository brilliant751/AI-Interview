import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Card, Popconfirm, Select, Space, Table, Typography, message } from 'antd'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { deleteInterviewHistory, fetchHistory } from '../api/interview'

/** 历史记录页面。 */
export function HistoryPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [jobRole, setJobRole] = useState<string | undefined>(undefined)
  const [page, setPage] = useState(1)

  /** 获取分页历史记录。 */
  const historyQuery = useQuery({
    queryKey: ['history', page, jobRole],
    queryFn: () => fetchHistory({ page, page_size: 10, job_role: jobRole }),
  })

  /** 删除历史面试记录。 */
  const deleteMutation = useMutation({
    mutationFn: (interviewId: string) => deleteInterviewHistory(interviewId),
    onSuccess: () => {
      message.success('面试记录已删除')
      void queryClient.invalidateQueries({ queryKey: ['history'] })
    },
    onError: () => {
      message.error('删除失败，请重试')
    },
  })

  return (
    <Card title="历史记录">
      <Select
        allowClear
        placeholder="按岗位筛选"
        style={{ width: 180, marginBottom: 16 }}
        options={[
          { label: 'Java', value: 'java' },
          { label: 'Web', value: 'web' },
        ]}
        onChange={(value) => {
          setPage(1)
          setJobRole(value)
        }}
      />

      <Table
        rowKey="interview_id"
        loading={historyQuery.isLoading}
        dataSource={historyQuery.data?.items ?? []}
        pagination={{
          current: page,
          pageSize: 10,
          total: historyQuery.data?.total ?? 0,
          onChange: (nextPage) => setPage(nextPage),
        }}
        columns={[
          { title: '会话 ID', dataIndex: 'interview_id' },
          { title: '简历 ID', dataIndex: 'resume_id' },
          { title: '岗位', dataIndex: 'job_role' },
          { title: '状态', dataIndex: 'status' },
          { title: '轮次数', dataIndex: 'turn_count' },
          { title: '开始时间', dataIndex: 'started_at' },
          {
            title: '操作',
            key: 'actions',
            render: (_, row: { interview_id: string }) => (
              <Space>
                <Button size="small" onClick={() => navigate(`/history/${row.interview_id}`)}>
                  回放
                </Button>
                <Button size="small" onClick={() => navigate(`/report/${row.interview_id}`)}>
                  查看报告
                </Button>
                <Popconfirm
                  title="确认删除该面试记录？"
                  okText="删除"
                  cancelText="取消"
                  onConfirm={() => deleteMutation.mutate(row.interview_id)}
                >
                  <Button size="small" danger loading={deleteMutation.isPending}>
                    删除
                  </Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />
      {historyQuery.isError && <Typography.Text type="danger">历史记录加载失败</Typography.Text>}
    </Card>
  )
}
