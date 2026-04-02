import { useQuery } from '@tanstack/react-query'
import { Card, Select, Table, Typography } from 'antd'
import { useState } from 'react'

import { fetchHistory } from '../api/interview'

/** 历史记录页面。 */
export function HistoryPage() {
  const [jobRole, setJobRole] = useState<string | undefined>(undefined)
  const [page, setPage] = useState(1)

  /** 获取分页历史记录。 */
  const historyQuery = useQuery({
    queryKey: ['history', page, jobRole],
    queryFn: () => fetchHistory({ page, page_size: 10, job_role: jobRole }),
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
          { title: '岗位', dataIndex: 'job_role' },
          { title: '时间', dataIndex: 'created_at' },
        ]}
      />
      {historyQuery.isError && <Typography.Text type="danger">历史记录加载失败</Typography.Text>}
    </Card>
  )
}

