import { useMutation, useQuery } from '@tanstack/react-query'
import { Button, Card, Form, Modal, Radio, Select, Space, Table, Tag, Typography, message } from 'antd'
import { AxiosError } from 'axios'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { fetchProviderHealth } from '../api/admin'
import { ProviderHealthBanner } from '../components/ProviderHealthBanner'
import { createInterview, fetchResumes } from '../api/interview'
import { useInterviewStore } from '../stores/interviewStore'

/** 面试准备页面。 */
export function InterviewPreparePage() {
  const navigate = useNavigate()
  const resumeId = useInterviewStore((state) => state.resumeId)
  const setResumeId = useInterviewStore((state) => state.setResumeId)
  const setSessionConfig = useInterviewStore((state) => state.setSessionConfig)
  const setProviderHealth = useInterviewStore((state) => state.setProviderHealth)
  const [resumePickerOpen, setResumePickerOpen] = useState(false)
  const [pendingResumeId, setPendingResumeId] = useState('')

  /** 查询 provider 健康状态。 */
  const healthQuery = useQuery({
    queryKey: ['provider-health'],
    queryFn: fetchProviderHealth,
    retry: false,
  })
  const healthQueryError =
    (healthQuery.error as AxiosError<{ error?: { message?: string } }> | null)?.response?.data?.error
      ?.message ||
    (healthQuery.error as Error | null)?.message ||
    ''

  useEffect(() => {
    if (healthQuery.data) {
      setProviderHealth(healthQuery.data)
    }
  }, [healthQuery.data, setProviderHealth])

  useEffect(() => {
    setPendingResumeId(resumeId)
  }, [resumeId])

  /** 查询可选简历。 */
  const resumeQuery = useQuery({
    queryKey: ['resumes', 'prepare-picker'],
    queryFn: () => fetchResumes({ page: 1, page_size: 50 }),
    enabled: resumePickerOpen,
  })

  const selectedResumeName = useMemo(() => {
    const items = resumeQuery.data?.items ?? []
    const current = items.find((item) => item.resume_id === resumeId)
    return current?.file_name || ''
  }, [resumeId, resumeQuery.data])

  /** 创建面试会话。 */
  const createMutation = useMutation({
    mutationFn: createInterview,
    onSuccess: (data, variables) => {
      setSessionConfig({
        interviewId: data.interview_id,
        jobRole: variables.job_role,
        difficulty: variables.difficulty,
        inputMode: variables.input_mode,
        outputMode: variables.output_mode,
        stage: data.current_stage,
        firstQuestion: data.first_question,
      })
      message.success('会话创建成功，进入面试页')
      navigate('/interview')
    },
    onError: () => {
      message.error('创建会话失败，请重试')
    },
  })

  return (
    <Card title="面试准备" bordered={false}>
      <div style={{ marginBottom: 16 }}>
        <ProviderHealthBanner
          health={healthQuery.data ?? null}
          loading={healthQuery.isLoading}
          errorMessage={healthQueryError}
        />
      </div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space>
          <Typography.Text strong>已绑定简历：</Typography.Text>
          {resumeId ? (
            <Tag color="blue">{selectedResumeName ? `${selectedResumeName} (${resumeId})` : resumeId}</Tag>
          ) : (
            <Tag color="red">未选择</Tag>
          )}
          <Button
            onClick={() => {
              setResumePickerOpen(true)
            }}
          >
            选择简历
          </Button>
          <Button onClick={() => navigate('/resumes')}>去上传/管理简历</Button>
        </Space>
      </Card>
      <Form
        layout="vertical"
        initialValues={{
          job_role: 'java',
          difficulty: 'medium',
          input_mode: 'text',
          output_mode: 'text',
        }}
        onFinish={(values) => {
          if (!resumeId) {
            message.warning('请先在弹窗中选择简历')
            setResumePickerOpen(true)
            return
          }
          createMutation.mutate({
            resume_id: resumeId,
            job_role: values.job_role,
            difficulty: values.difficulty,
            input_mode: values.input_mode,
            output_mode: values.output_mode,
          })
        }}
      >
        <Form.Item name="job_role" label="岗位方向">
          <Select
            options={[
              { label: 'Java', value: 'java' },
              { label: 'Web', value: 'web' },
            ]}
          />
        </Form.Item>
        <Form.Item name="difficulty" label="难度">
          <Radio.Group
            options={[
              { label: '简单', value: 'easy' },
              { label: '中等', value: 'medium' },
              { label: '困难', value: 'hard' },
            ]}
          />
        </Form.Item>
        <Form.Item name="input_mode" label="输入模式">
          <Radio.Group
            options={[
              { label: '文本', value: 'text' },
              { label: '语音', value: 'voice' },
            ]}
          />
        </Form.Item>
        <Form.Item name="output_mode" label="输出模式">
          <Radio.Group
            options={[
              { label: '文本', value: 'text' },
              { label: '语音', value: 'voice' },
            ]}
          />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={createMutation.isPending}>
          创建会话
        </Button>
      </Form>
      <Modal
        title="选择本次面试简历"
        open={resumePickerOpen}
        onCancel={() => setResumePickerOpen(false)}
        onOk={() => {
          if (!pendingResumeId) {
            message.warning('请选择一份简历')
            return
          }
          setResumeId(pendingResumeId)
          setResumePickerOpen(false)
          message.success('已绑定简历')
        }}
        okText="确认绑定"
        cancelText="取消"
      >
        <Table
          rowKey="resume_id"
          loading={resumeQuery.isLoading}
          dataSource={resumeQuery.data?.items ?? []}
          pagination={false}
          rowSelection={{
            type: 'radio',
            selectedRowKeys: pendingResumeId ? [pendingResumeId] : [],
            onChange: (keys) => {
              setPendingResumeId(String(keys[0] || ''))
            },
          }}
          columns={[
            { title: '文件名', dataIndex: 'file_name' },
            { title: '状态', dataIndex: 'parse_status' },
            { title: '创建时间', dataIndex: 'created_at' },
          ]}
          locale={{ emptyText: '暂无简历，请先去简历管理页上传。' }}
        />
      </Modal>
    </Card>
  )
}
