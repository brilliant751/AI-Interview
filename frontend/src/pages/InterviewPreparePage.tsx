import { useMutation, useQuery } from '@tanstack/react-query'
import { Button, Card, Checkbox, Form, Input, Modal, Radio, Select, Space, Table, Tag, Typography, message } from 'antd'
import { AxiosError } from 'axios'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { fetchProviderHealth } from '../api/admin'
import { ProviderHealthBanner } from '../components/ProviderHealthBanner'
import { createInterview, fetchHistory, fetchInterviewStatus, fetchResumes } from '../api/interview'
import { useInterviewStore } from '../stores/interviewStore'

/** 面试准备页面。 */
export function InterviewPreparePage() {
  const questionTypeOrder: Array<'project' | 'technical' | 'scenario'> = ['project', 'technical', 'scenario']
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

  /** 查询暂停中的面试。 */
  const pausedQuery = useQuery({
    queryKey: ['paused-interviews'],
    queryFn: () => fetchHistory({ page: 1, page_size: 20, status: 'PAUSED' }),
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
        ttsAudioUrl: data.tts_audio_url,
      })
      message.success('会话创建成功，进入面试页')
      navigate('/interview')
    },
    onError: () => {
      message.error('创建会话失败，请重试')
    },
  })

  /** 恢复暂停面试。 */
  const resumeMutation = useMutation({
    mutationFn: (interviewId: string) => fetchInterviewStatus(interviewId, { status: 'ACTIVE' }),
    onSuccess: (data) => {
      setSessionConfig({
        interviewId: data.interview_id,
        jobRole: data.job_role,
        difficulty: data.difficulty,
        inputMode: data.input_mode,
        outputMode: data.output_mode,
        stage: data.current_stage,
        firstQuestion: data.current_question,
        ttsAudioUrl: data.tts_audio_url,
      })
      message.success('已恢复暂停面试')
      navigate('/interview')
    },
    onError: () => {
      message.error('恢复面试失败，请重试')
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
      <Card title="继续暂停的面试" size="small" style={{ marginBottom: 16 }}>
        <Table
          rowKey="interview_id"
          loading={pausedQuery.isLoading}
          dataSource={pausedQuery.data?.items ?? []}
          pagination={false}
          columns={[
            { title: '会话ID', dataIndex: 'interview_id' },
            { title: '简历', dataIndex: 'resume_id' },
            { title: '岗位', dataIndex: 'job_role' },
            { title: '难度', dataIndex: 'difficulty' },
            { title: '状态', dataIndex: 'status' },
            {
              title: '操作',
              key: 'actions',
              render: (_, row: { interview_id: string }) => (
                <Button
                  size="small"
                  type="primary"
                  loading={resumeMutation.isPending}
                  onClick={() => resumeMutation.mutate(row.interview_id)}
                >
                  继续面试
                </Button>
              ),
            },
          ]}
          locale={{ emptyText: '暂无暂停中的面试，可直接创建新面试。' }}
        />
      </Card>
      <Form
        layout="vertical"
        initialValues={{
          job_role: 'java',
          difficulty: 'medium',
          input_mode: 'voice',
          output_mode: 'voice',
          session_name: '',
          question_types: ['project', 'technical', 'scenario'],
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
            session_name: values.session_name,
            question_types: questionTypeOrder.filter((item) => (values.question_types || []).includes(item)),
          })
        }}
      >
        <Form.Item name="session_name" label="面试名称">
          <Input placeholder="例如：Java后端一面（可选）" maxLength={128} />
        </Form.Item>
        <Form.Item name="question_types" label="题目类型">
          <Checkbox.Group
            options={[
              { label: '项目经历', value: 'project' },
              { label: '技术', value: 'technical' },
              { label: '场景', value: 'scenario' },
            ]}
          />
        </Form.Item>
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
          onRow={(record) => ({
            onClick: () => setPendingResumeId(record.resume_id),
          })}
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
