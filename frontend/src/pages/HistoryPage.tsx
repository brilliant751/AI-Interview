import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Card, Modal, Popconfirm, Select, Space, Table, Typography, message } from 'antd'
import { AxiosError } from 'axios'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { deleteInterviewHistory, fetchHistory, fetchResumeFile } from '../api/interview'

// 历史记录页：
// 1. 按岗位和分页查询当前用户的面试会话。
// 2. 支持跳转回放、查看报告、预览关联简历和删除历史记录。
// 3. 简历预览同样使用 Blob URL，关闭或卸载时释放资源。
// 4. 删除成功后刷新对应分页，避免列表展示已删除项。

/** 历史记录页面。 */
export function HistoryPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [jobRole, setJobRole] = useState<string | undefined>(undefined)
  const [page, setPage] = useState(1)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewTitle, setPreviewTitle] = useState('')
  const [previewType, setPreviewType] = useState('')
  const [previewUrl, setPreviewUrl] = useState('')

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl)
      }
    }
  }, [previewUrl])

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

  /** 预览简历。 */
  const previewMutation = useMutation({
    mutationFn: async (payload: { resumeId: string; fileName: string }) => {
      const blob = await fetchResumeFile(payload.resumeId)
      return { blob, fileName: payload.fileName }
    },
    onSuccess: ({ blob, fileName }) => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl)
      }
      const objectUrl = URL.createObjectURL(blob)
      const ext = fileName.split('.').pop()?.toLowerCase() || ''
      setPreviewType(ext)
      setPreviewTitle(fileName)
      setPreviewUrl(objectUrl)
      setPreviewOpen(true)
    },
    onError: (error) => {
      const axiosError = error as AxiosError<{ error?: { message?: string } }>
      message.error(axiosError.response?.data?.error?.message || '加载简历失败')
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
        scroll={{ x: 1100 }}
        pagination={{
          current: page,
          pageSize: 10,
          total: historyQuery.data?.total ?? 0,
          onChange: (nextPage) => setPage(nextPage),
        }}
        columns={[
          {
            title: '面试名称',
            dataIndex: 'session_name',
            render: (value?: string) => value || '-',
          },
          { title: '会话 ID', dataIndex: 'interview_id' },
          {
            title: '简历',
            key: 'resume',
            render: (_, row: { resume_id: string; resume_file_name?: string }) => (
              <Space direction="vertical" size={2}>
                <Typography.Text>{row.resume_file_name || '简历文件名缺失'}</Typography.Text>
                <Typography.Text type="secondary">{row.resume_id}</Typography.Text>
              </Space>
            ),
          },
          { title: '岗位', dataIndex: 'job_role' },
          { title: '状态', dataIndex: 'status' },
          { title: '轮次数', dataIndex: 'turn_count' },
          { title: '开始时间', dataIndex: 'started_at' },
          {
            title: '操作',
            key: 'actions',
            render: (_, row: { interview_id: string; resume_id: string; resume_file_name?: string }) => (
              <Space>
                <Button
                  size="small"
                  loading={previewMutation.isPending}
                  onClick={() =>
                    previewMutation.mutate({
                      resumeId: row.resume_id,
                      fileName: row.resume_file_name || `${row.resume_id}.pdf`,
                    })
                  }
                >
                  预览简历
                </Button>
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
      <Modal
        title={`简历预览 - ${previewTitle}`}
        open={previewOpen}
        onCancel={() => setPreviewOpen(false)}
        footer={null}
        width="min(900px, 92vw)"
        destroyOnClose
      >
        {previewType === 'pdf' ? (
          <iframe title="resume-preview" src={previewUrl} style={{ width: '100%', height: '70vh', minHeight: 320, border: 0 }} />
        ) : (
          <Space direction="vertical">
            <Typography.Text>当前文件类型暂不支持在线渲染，可下载后查看。</Typography.Text>
            <a href={previewUrl} download={previewTitle}>
              下载简历文件
            </a>
          </Space>
        )}
      </Modal>
    </Card>
  )
}
