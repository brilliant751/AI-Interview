import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Card, Modal, Popconfirm, Space, Table, Typography, Upload, message } from 'antd'
import { AxiosError } from 'axios'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { deleteResume, fetchResumeFile, fetchResumes, uploadResume } from '../api/interview'
import { useInterviewStore } from '../stores/interviewStore'

// 简历管理页：
// 1. 支持上传、列表、预览、删除和选择用于面试。
// 2. 文件预览通过 Blob URL 创建，组件卸载时必须 revoke 防止内存泄漏。
// 3. 删除后刷新列表，选择简历后写入 interviewStore 并跳转面试准备流程。
// 4. 上传错误兼容 AxiosError，用后端 message 给用户更准确反馈。

/** 简历管理页面。 */
export function ResumeManagePage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewTitle, setPreviewTitle] = useState('')
  const [previewType, setPreviewType] = useState('')
  const [previewUrl, setPreviewUrl] = useState('')
  const setResumeId = useInterviewStore((state) => state.setResumeId)

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl)
      }
    }
  }, [previewUrl])

  /** 查询简历列表。 */
  const resumeQuery = useQuery({
    queryKey: ['resumes', page],
    queryFn: () => fetchResumes({ page, page_size: 10 }),
  })

  /** 上传简历。 */
  const uploadMutation = useMutation({
    mutationFn: uploadResume,
    onSuccess: async (data) => {
      setResumeId(data.resume_id)
      await queryClient.invalidateQueries({ queryKey: ['resumes'] })
      message.success('简历上传成功')
    },
    onError: (error: Error) => {
      message.error(error.message || '简历上传失败')
    },
  })

  /** 删除简历。 */
  const deleteMutation = useMutation({
    mutationFn: deleteResume,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['resumes'] })
      message.success('简历已删除')
    },
    onError: (error) => {
      const axiosError = error as AxiosError<{ error?: { code?: string; message?: string } }>
      const apiError = axiosError.response?.data?.error
      if (apiError?.code === 'RESUME_409_IN_USE') {
        message.warning(apiError.message || '该简历存在进行中的面试，暂不可删除')
        return
      }
      message.error(apiError?.message || '删除简历失败')
    },
  })

  /** 查看简历。 */
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
    <Card title="简历管理" bordered={false}>
      <Typography.Paragraph>在此上传、选择并删除你的简历。开始面试前请先选择一份简历。</Typography.Paragraph>
      <Space style={{ marginBottom: 16 }}>
        <Upload
          showUploadList={false}
          accept=".pdf,.doc,.docx"
          beforeUpload={(file) => {
            if (uploadMutation.isPending) {
              return false
            }
            uploadMutation.mutate(file)
            return false
          }}
        >
          <Button type="primary" loading={uploadMutation.isPending}>
            上传简历
          </Button>
        </Upload>
        <Button onClick={() => navigate('/interview')}>去面试</Button>
      </Space>

      <Table
        rowKey="resume_id"
        loading={resumeQuery.isLoading}
        dataSource={resumeQuery.data?.items ?? []}
        scroll={{ x: 980 }}
        pagination={{
          current: page,
          pageSize: 10,
          total: resumeQuery.data?.total ?? 0,
          onChange: (nextPage) => setPage(nextPage),
        }}
        columns={[
          { title: '简历 ID', dataIndex: 'resume_id' },
          { title: '文件名', dataIndex: 'file_name' },
          { title: '解析状态', dataIndex: 'parse_status' },
          { title: '创建时间', dataIndex: 'created_at' },
          { title: '最近使用时间', dataIndex: 'last_used_at', render: (value: string | undefined) => value || '-' },
          {
            title: '操作',
            key: 'actions',
            render: (_, row: { resume_id: string; file_name: string }) => (
              <Space>
                <Button
                  size="small"
                  loading={previewMutation.isPending}
                  onClick={() => previewMutation.mutate({ resumeId: row.resume_id, fileName: row.file_name })}
                >
                  查看
                </Button>
                <Popconfirm
                  title="确认删除该简历？"
                  description="删除后不可在新面试中使用。"
                  okText="删除"
                  cancelText="取消"
                  onConfirm={() => deleteMutation.mutate(row.resume_id)}
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

      {resumeQuery.isError ? <Typography.Text type="danger">简历列表加载失败</Typography.Text> : null}
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
