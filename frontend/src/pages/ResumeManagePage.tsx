import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Card, Popconfirm, Space, Table, Typography, Upload, message } from 'antd'
import type { UploadFile } from 'antd'
import { AxiosError } from 'axios'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { deleteResume, fetchResumes, uploadResume } from '../api/interview'
import { useInterviewStore } from '../stores/interviewStore'

/** 简历管理页面。 */
export function ResumeManagePage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const setResumeId = useInterviewStore((state) => state.setResumeId)

  /** 查询简历列表。 */
  const resumeQuery = useQuery({
    queryKey: ['resumes', page],
    queryFn: () => fetchResumes({ page, page_size: 10 }),
  })

  /** 上传简历。 */
  const uploadMutation = useMutation({
    mutationFn: async () => {
      const currentFile = fileList[0]?.originFileObj
      if (!currentFile) {
        throw new Error('请先选择简历文件')
      }
      return uploadResume(currentFile)
    },
    onSuccess: async (data) => {
      setResumeId(data.resume_id)
      setFileList([])
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

  return (
    <Card title="简历管理" bordered={false}>
      <Typography.Paragraph>在此上传、选择并删除你的简历。开始面试前请先选择一份简历。</Typography.Paragraph>
      <Space style={{ marginBottom: 16 }}>
        <Upload
          beforeUpload={() => false}
          fileList={fileList}
          onChange={(event) => setFileList(event.fileList.slice(-1))}
          accept=".pdf,.doc,.docx"
        >
          <Button>选择简历</Button>
        </Upload>
        <Button type="primary" loading={uploadMutation.isPending} onClick={() => uploadMutation.mutate()}>
          上传简历
        </Button>
        <Button onClick={() => navigate('/prepare')}>去面试准备</Button>
      </Space>

      <Table
        rowKey="resume_id"
        loading={resumeQuery.isLoading}
        dataSource={resumeQuery.data?.items ?? []}
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
            render: (_, row: { resume_id: string }) => (
              <Space>
                <Button
                  size="small"
                  onClick={() => {
                    setResumeId(row.resume_id)
                    message.success('已选择该简历，可前往面试准备')
                  }}
                >
                  选择
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
    </Card>
  )
}
