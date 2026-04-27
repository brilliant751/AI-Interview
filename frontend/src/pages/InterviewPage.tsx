import { useMutation, useQuery } from '@tanstack/react-query'
import { Button, Card, Input, Space, Tag, Typography, Upload, message } from 'antd'
import type { UploadFile } from 'antd/es/upload/interface'
import { AxiosError } from 'axios'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { fetchProviderHealth } from '../api/admin'
import { ProviderHealthBanner } from '../components/ProviderHealthBanner'
import { fetchInterviewStatus, finishInterview, submitAudioTurn, submitTurn } from '../api/interview'
import { useInterviewStore } from '../stores/interviewStore'

/** 面试答题页面。 */
export function InterviewPage() {
  const navigate = useNavigate()
  const [answer, setAnswer] = useState('')
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [audioUploadFile, setAudioUploadFile] = useState<UploadFile | null>(null)
  const {
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
            navigate('/report')
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
      navigate('/report')
    },
    onError: () => message.error('结束面试失败'),
  })

  if (!interviewId) {
    return (
      <Card>
        <Typography.Text>尚未创建会话，请先完成简历上传和准备步骤。</Typography.Text>
        <div style={{ marginTop: 12 }}>
          <Button type="primary" onClick={() => navigate('/upload')}>
            去上传
          </Button>
        </div>
      </Card>
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
