import { useMutation, useQuery } from '@tanstack/react-query'
import { Button, Card, Form, Input, Modal, Radio, Select, Space, Table, Tag, Typography, Upload, message } from 'antd'
import type { UploadFile } from 'antd/es/upload/interface'
import { AxiosError } from 'axios'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { fetchProviderHealth } from '../api/admin'
import { ProviderHealthBanner } from '../components/ProviderHealthBanner'
import {
  createInterview,
  fetchInterviewStatus,
  fetchResumeFile,
  fetchResumes,
  finishInterview,
  submitAudioTurn,
  submitTurn,
} from '../api/interview'
import { useInterviewStore } from '../stores/interviewStore'

/** 面试答题页面。 */
export function InterviewPage() {
  const navigate = useNavigate()
  const [answer, setAnswer] = useState('')
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [audioUploadFile, setAudioUploadFile] = useState<UploadFile | null>(null)
  const [resumePickerOpen, setResumePickerOpen] = useState(false)
  const [pendingResumeId, setPendingResumeId] = useState('')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewTitle, setPreviewTitle] = useState('')
  const [previewType, setPreviewType] = useState('')
  const [previewUrl, setPreviewUrl] = useState('')
  const {
    resumeId,
    interviewId,
    currentStage,
    currentQuestion,
    liveScore,
    followUpCount,
    inputMode,
    outputMode,
    ttsAudioUrl,
    pipelineMeta,
    generationMode,
    providerHealth,
    updateTurnResult,
    setProviderHealth,
    syncSessionStatus,
    setResumeId,
    setSessionConfig,
  } = useInterviewStore((state) => state)

  /** 面试页主动拉取 provider 健康状态，避免仅依赖准备页缓存。 */
  const healthQuery = useQuery({
    queryKey: ['provider-health', 'interview-page'],
    queryFn: fetchProviderHealth,
    retry: false,
    refetchInterval: 15000,
  })

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
    queryKey: ['resumes', 'interview-picker'],
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
      message.success('会话创建成功')
    },
    onError: () => {
      message.error('创建会话失败，请重试')
    },
  })

  /** 预览简历文件。 */
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

  /** 提交轮次。 */
  const submitMutation = useMutation({
    mutationFn: async () =>
      inputMode === 'voice' && audioFile
        ? submitAudioTurn(interviewId, {
            stage: currentStage,
            file: audioFile,
          })
        : submitTurn(interviewId, {
            stage: currentStage,
            answer_text: answer,
          }),
    onSuccess: (data) => {
      updateTurnResult({
        stage: data.stage,
        question: data.next_question,
        score: data.live_score,
        followUpCount: data.follow_up_count,
        ttsAudioUrl: data.tts_audio_url,
        pipelineMeta: data.pipeline_meta,
      })
      setAnswer('')
      setAudioFile(null)
      setAudioUploadFile(null)
      message.success('已生成下一题')
    },
    onError: async (error) => {
      const axiosError = error as AxiosError<{ error?: { code?: string; message?: string } }>
      const apiError = axiosError.response?.data?.error
      const errorCode = apiError?.code || ''
      const errorMessage = apiError?.message || '提交失败，请重试'

      if (errorCode === 'STATE_409') {
        try {
          const sessionStatus = await fetchInterviewStatus(interviewId)
          syncSessionStatus({
            stage: sessionStatus.current_stage,
            followUpCount: sessionStatus.follow_up_count,
          })
          if (sessionStatus.status === 'FINISHED' || sessionStatus.current_stage === 'END') {
            message.warning('当前会话已结束，正在跳转报告页')
            navigate(`/report/${interviewId}`)
            return
          }
          message.warning(`${errorMessage}，已同步到最新阶段：${sessionStatus.current_stage}`)
          return
        } catch {
          message.error(`${errorMessage}，同步阶段失败，请刷新页面`)
          return
        }
      }
      message.error(errorMessage)
    },
  })

  /** 结束面试。 */
  const finishMutation = useMutation({
    mutationFn: () => finishInterview(interviewId),
    onSuccess: () => {
      message.success('面试已结束，正在生成报告')
      navigate(`/report/${interviewId}`)
    },
    onError: () => message.error('结束面试失败'),
  })

  if (!interviewId) {
    return (
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <ProviderHealthBanner health={providerHealth} />
        <Card title="创建面试">
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Space>
              <Typography.Text strong>简历：</Typography.Text>
              {resumeId ? (
                <Tag color="blue">{selectedResumeName ? `${selectedResumeName} (${resumeId})` : resumeId}</Tag>
              ) : (
                <Tag color="red">未选择</Tag>
              )}
              <Button onClick={() => setResumePickerOpen(true)}>选择简历</Button>
            </Space>
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
          </Space>
        </Card>
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
          okText="确认"
          cancelText="取消"
          footer={(_, { OkBtn, CancelBtn }) => (
            <Space style={{ width: '100%', justifyContent: 'space-between' }}>
              <Button onClick={() => navigate('/resumes')}>去上传简历管理</Button>
              <Space>
                <CancelBtn />
                <OkBtn />
              </Space>
            </Space>
          )}
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
              {
                title: '操作',
                key: 'actions',
                render: (_, row: { resume_id: string; file_name: string }) => (
                  <Button
                    size="small"
                    loading={previewMutation.isPending}
                    onClick={() => previewMutation.mutate({ resumeId: row.resume_id, fileName: row.file_name })}
                  >
                    预览
                  </Button>
                ),
              },
            ]}
            locale={{ emptyText: '暂无简历，请先去简历管理页上传。' }}
          />
        </Modal>
        <Modal
          title={`简历预览 - ${previewTitle}`}
          open={previewOpen}
          onCancel={() => setPreviewOpen(false)}
          footer={null}
          width={900}
          destroyOnClose
        >
          {previewType === 'pdf' ? (
            <iframe title="resume-preview" src={previewUrl} style={{ width: '100%', height: 600, border: 0 }} />
          ) : (
            <Space direction="vertical">
              <Typography.Text>当前文件类型暂不支持在线渲染，可下载后查看。</Typography.Text>
              <a href={previewUrl} download={previewTitle}>
                下载简历文件
              </a>
            </Space>
          )}
        </Modal>
      </Space>
    )
  }

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card>
        <Space wrap>
          <Tag color="blue">阶段：{currentStage}</Tag>
          <Tag color="cyan">模式：{generationMode}</Tag>
          <Tag color="green">实时分：{liveScore}</Tag>
          <Tag color="gold">追问次数：{followUpCount}</Tag>
          <Tag color="magenta">输入模式：{inputMode}</Tag>
          <Tag color="purple">输出模式：{outputMode}</Tag>
        </Space>
      </Card>
      <ProviderHealthBanner health={providerHealth} />
      <Card title="当前问题">
        <Typography.Paragraph style={{ marginBottom: 0 }}>{currentQuestion || '等待题目生成...'}</Typography.Paragraph>
      </Card>
      <Card title="你的回答">
        {inputMode === 'voice' ? (
          <Upload
            beforeUpload={(file) => {
              setAudioFile(file)
              setAudioUploadFile({
                uid: file.uid,
                name: file.name,
                status: 'done',
              })
              return false
            }}
            maxCount={1}
            fileList={audioUploadFile ? [audioUploadFile] : []}
            onRemove={() => {
              setAudioFile(null)
              setAudioUploadFile(null)
            }}
          >
            <Button>选择音频文件</Button>
          </Upload>
        ) : null}
        <Input.TextArea
          rows={6}
          value={answer}
          onChange={(event) => setAnswer(event.target.value)}
          placeholder="输入你的回答"
        />
        <Space style={{ marginTop: 12 }}>
          <Button
            type="primary"
            loading={submitMutation.isPending}
            disabled={submitMutation.isPending || currentStage === 'END'}
            onClick={() => {
              if (submitMutation.isPending || currentStage === 'END') {
                return
              }
              submitMutation.mutate()
            }}
          >
            提交回答
          </Button>
          <Button danger loading={finishMutation.isPending} onClick={() => finishMutation.mutate()}>
            结束面试
          </Button>
        </Space>
      </Card>
      {pipelineMeta ? (
        <Card title="链路信息">
          <Space wrap>
            <Tag color="geekblue">trace_id: {pipelineMeta.trace_id}</Tag>
            <Tag color="cyan">输入来源：{pipelineMeta.input_source}</Tag>
            <Tag color="processing">耗时：{pipelineMeta.latency_ms}ms</Tag>
            <Tag color="lime">ASR: {pipelineMeta.providers.asr || 'N/A'}</Tag>
            <Tag color="lime">LLM: {pipelineMeta.providers.llm || 'N/A'}</Tag>
            <Tag color="lime">TTS: {pipelineMeta.providers.tts || 'N/A'}</Tag>
            <Tag color="blue">ASR状态: {pipelineMeta.provider_status.asr}</Tag>
            <Tag color="blue">LLM状态: {pipelineMeta.provider_status.llm}</Tag>
            <Tag color="blue">TTS状态: {pipelineMeta.provider_status.tts}</Tag>
            <Tag color="geekblue">生成模式: {pipelineMeta.generation_mode}</Tag>
            <Tag color="orange">
              降级标记：{pipelineMeta.degrade_flags.length ? pipelineMeta.degrade_flags.join(', ') : '无'}
            </Tag>
          </Space>
        </Card>
      ) : null}
      {ttsAudioUrl ? (
        <Card title="语音输出">
          <audio controls src={ttsAudioUrl} style={{ width: '100%' }}>
            您的浏览器不支持音频播放。
          </audio>
          <div style={{ marginTop: 12 }}>
            <Button type="link" href={ttsAudioUrl} target="_blank">
              下载语音
            </Button>
          </div>
        </Card>
      ) : null}
    </Space>
  )
}
