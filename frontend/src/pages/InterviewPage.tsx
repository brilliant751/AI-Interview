import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarOutlined, ClockCircleOutlined, FilePdfOutlined, FlagOutlined, HourglassOutlined, UnorderedListOutlined, UserOutlined } from '@ant-design/icons'
import { Button, Card, Checkbox, Dropdown, Form, Input, Modal, Progress, Radio, Select, Space, Table, Tag, Typography, message } from 'antd'
import { AxiosError } from 'axios'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { fetchProviderHealth } from '../api/admin'
import { ProviderHealthBanner } from '../components/ProviderHealthBanner'
import {
  createInterview,
  fetchHistory,
  fetchInterviewPlayback,
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
  const AUTO_RECORD_COUNTDOWN_SECONDS = 10
  const MAX_RECORDING_SECONDS = 180
  const MAX_TEXT_ANSWER_SECONDS = 180
  const questionTypeOrder: Array<'project' | 'technical' | 'scenario'> = ['project', 'technical', 'scenario']
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { interviewId: routeInterviewId = '' } = useParams<{ interviewId?: string }>()
  const [answer, setAnswer] = useState('')
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [recording, setRecording] = useState(false)
  const [countdown, setCountdown] = useState(0)
  const [recordingElapsedSeconds, setRecordingElapsedSeconds] = useState(0)
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [resumePickerOpen, setResumePickerOpen] = useState(false)
  const [pendingResumeId, setPendingResumeId] = useState('')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewTitle, setPreviewTitle] = useState('')
  const [previewType, setPreviewType] = useState('')
  const [previewUrl, setPreviewUrl] = useState('')
  const [resumingInterviewId, setResumingInterviewId] = useState('')
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const countdownTimerRef = useRef<number | null>(null)
  const recordingProgressTimerRef = useRef<number | null>(null)
  const recordingLimitTimerRef = useRef<number | null>(null)
  const textAnswerTimerRef = useRef<number | null>(null)
  const suppressRecorderStopRef = useRef(false)
  const submitAfterStopRef = useRef(false)
  const lastQuestionKeyRef = useRef('')
  const pendingCountdownQuestionKeyRef = useRef('')
  const autoPlayAudioRef = useRef<HTMLAudioElement | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const lastRoundQuestionKeyRef = useRef('')
  const [questionRound, setQuestionRound] = useState(1)
  const [textAnswerRemainingSeconds, setTextAnswerRemainingSeconds] = useState(MAX_TEXT_ANSWER_SECONDS)
  const [interviewElapsedSeconds, setInterviewElapsedSeconds] = useState(0)
  const [audioInputDevices, setAudioInputDevices] = useState<Array<{ label: string; value: string }>>([])
  const [selectedAudioInputId, setSelectedAudioInputId] = useState('')
  const [audioDevicesLoading, setAudioDevicesLoading] = useState(false)
  const [resumeReplayTick, setResumeReplayTick] = useState(0)
  const [questionAudioPlaying, setQuestionAudioPlaying] = useState(false)
  const endRedirectedRef = useRef(false)
  const [historyCollapsed, setHistoryCollapsed] = useState(false)
  const lastTextQuestionKeyRef = useRef('')
  const parseBackendDate = (value?: string) => {
    if (!value) {
      return null
    }
    const normalized = value.includes('T') ? value : value.replace(' ', 'T')
    const withZone = /Z|[+-]\d{2}:\d{2}$/.test(normalized) ? normalized : `${normalized}Z`
    const parsed = new Date(withZone)
    if (Number.isNaN(parsed.getTime())) {
      return null
    }
    return parsed
  }
  /** 生成当前题目的稳定 key，避免受实时分/追问次数轮询抖动影响。 */
  const buildQuestionKey = () => pipelineMeta?.trace_id || `${currentStage}:${currentQuestion}`
  /** 计算麦克风优先级：优先本机内建麦克风，弱化 iPhone 连续互通设备。 */
  const scoreAudioInputLabel = (label: string) => {
    const lowerLabel = label.toLowerCase()
    let score = 0
    if (lowerLabel.includes('iphone')) {
      score -= 100
    }
    if (
      lowerLabel.includes('macbook') ||
      lowerLabel.includes('built-in') ||
      lowerLabel.includes('internal') ||
      lowerLabel.includes('内建') ||
      lowerLabel.includes('内置')
    ) {
      score += 50
    }
    if (lowerLabel.includes('microphone') || lowerLabel.includes('mic') || lowerLabel.includes('麦克风')) {
      score += 10
    }
    return score
  }
  /** 从设备列表中挑选默认麦克风。 */
  const pickPreferredAudioInputId = (devices: MediaDeviceInfo[]) => {
    if (devices.length === 0) {
      return ''
    }
    const sorted = [...devices].sort((left, right) => scoreAudioInputLabel(right.label) - scoreAudioInputLabel(left.label))
    return sorted[0].deviceId
  }
  /** 刷新可用麦克风设备列表并更新默认选择。 */
  const refreshAudioInputDevices = async () => {
    if (!navigator.mediaDevices?.enumerateDevices) {
      return
    }
    const devices = await navigator.mediaDevices.enumerateDevices()
    const audioInputs = devices.filter((device) => device.kind === 'audioinput')
    const options = audioInputs.map((device, index) => ({
      label: device.label || `麦克风 ${index + 1}`,
      value: device.deviceId,
    }))
    setAudioInputDevices(options)
    setSelectedAudioInputId((previous) => {
      if (previous && audioInputs.some((item) => item.deviceId === previous)) {
        return previous
      }
      return pickPreferredAudioInputId(audioInputs)
    })
  }
  /** 请求麦克风权限后刷新设备，用于拿到完整设备名称。 */
  const prepareAudioInputDevices = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      return
    }
    setAudioDevicesLoading(true)
    try {
      const permissionStream = await navigator.mediaDevices.getUserMedia({ audio: true })
      permissionStream.getTracks().forEach((track) => track.stop())
      await refreshAudioInputDevices()
    } catch {
      await refreshAudioInputDevices()
    } finally {
      setAudioDevicesLoading(false)
    }
  }
  const {
    resumeId,
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
    reset,
  } = useInterviewStore((state) => state)
  const interviewId = routeInterviewId || ''

  /** 面试页主动拉取 provider 健康状态，避免仅依赖准备页缓存。 */
  const healthQuery = useQuery({
    queryKey: ['provider-health', 'interview-page'],
    queryFn: fetchProviderHealth,
    retry: false,
    refetchInterval: 15000,
  })
  /** 会话页拉取状态，确保支持直接访问 /interview/{id}。 */
  const interviewStatusQuery = useQuery({
    queryKey: ['interview-status', interviewId],
    queryFn: () => fetchInterviewStatus(interviewId),
    enabled: Boolean(interviewId),
    refetchInterval: 15000,
  })
  /** 查询面试详情（用于左侧详情面板）。 */
  const playbackQuery = useQuery({
    queryKey: ['interview-playback', interviewId],
    queryFn: () => fetchInterviewPlayback(interviewId),
    enabled: Boolean(interviewId),
  })

  useEffect(() => {
    if (healthQuery.data) {
      setProviderHealth(healthQuery.data)
    }
  }, [healthQuery.data, setProviderHealth])

  useEffect(() => {
    if (!interviewId || !interviewStatusQuery.data) {
      return
    }
    const status = interviewStatusQuery.data
    if (!useInterviewStore.getState().interviewId) {
      setSessionConfig({
        interviewId: status.interview_id,
        jobRole: status.job_role,
        difficulty: status.difficulty,
        inputMode: status.input_mode,
        outputMode: status.output_mode,
        stage: status.current_stage,
        firstQuestion: status.current_question,
        ttsAudioUrl: status.tts_audio_url,
      })
      return
    }
    syncSessionStatus({
      stage: status.current_stage,
      followUpCount: status.follow_up_count,
    })
  }, [interviewId, interviewStatusQuery.data, setSessionConfig, syncSessionStatus])

  /** 会话进入结束态时自动跳转报告页，避免停留在不可作答页面。 */
  useEffect(() => {
    if (!interviewId || endRedirectedRef.current) {
      return
    }
    const endedByStage = currentStage === 'END'
    const endedByStatus = interviewStatusQuery.data?.status === 'FINISHED'
    if (!endedByStage && !endedByStatus) {
      return
    }
    endRedirectedRef.current = true
    Modal.info({
      title: '面试已结束',
      content: '点击查看面试报告',
      okText: '查看面试报告',
      onOk: () => {
        navigate(`/report/${interviewId}`)
      },
    })
  }, [interviewId, currentStage, interviewStatusQuery.data?.status, navigate])

  useEffect(() => {
    if (!interviewId) {
      lastRoundQuestionKeyRef.current = ''
      setQuestionRound(1)
      return
    }
    const key = pipelineMeta?.trace_id || `${currentStage}:${currentQuestion}`
    if (!currentQuestion) {
      return
    }
    if (!lastRoundQuestionKeyRef.current) {
      lastRoundQuestionKeyRef.current = key
      setQuestionRound(1)
      return
    }
    if (lastRoundQuestionKeyRef.current !== key) {
      lastRoundQuestionKeyRef.current = key
      setQuestionRound((previous) => previous + 1)
    }
  }, [interviewId, currentQuestion, currentStage, pipelineMeta?.trace_id])

  useEffect(() => {
    setPendingResumeId(resumeId)
  }, [resumeId])

  /** 组件卸载时，清理录音与计时器资源。 */
  useEffect(() => {
    return () => {
      if (countdownTimerRef.current !== null) {
        window.clearInterval(countdownTimerRef.current)
      }
      if (recordingLimitTimerRef.current !== null) {
        window.clearTimeout(recordingLimitTimerRef.current)
      }
      if (recordingProgressTimerRef.current !== null) {
        window.clearInterval(recordingProgressTimerRef.current)
      }
      if (textAnswerTimerRef.current !== null) {
        window.clearInterval(textAnswerTimerRef.current)
      }
      if (audioContextRef.current) {
        void audioContextRef.current.close()
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop()
      }
    }
  }, [])

  /** 重置当前轮次的前端运行态，确保恢复会话时从新一轮开始。 */
  const resetRoundRuntimeState = () => {
    if (countdownTimerRef.current !== null) {
      window.clearInterval(countdownTimerRef.current)
      countdownTimerRef.current = null
    }
    if (recordingLimitTimerRef.current !== null) {
      window.clearTimeout(recordingLimitTimerRef.current)
      recordingLimitTimerRef.current = null
    }
    if (recordingProgressTimerRef.current !== null) {
      window.clearInterval(recordingProgressTimerRef.current)
      recordingProgressTimerRef.current = null
    }
    if (textAnswerTimerRef.current !== null) {
      window.clearInterval(textAnswerTimerRef.current)
      textAnswerTimerRef.current = null
    }
    setCountdown(0)
    setRecording(false)
    setRecordingElapsedSeconds(0)
    setAudioFile(null)
    setAnswer('')
    submitAfterStopRef.current = false
    lastQuestionKeyRef.current = ''
    pendingCountdownQuestionKeyRef.current = ''
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      suppressRecorderStopRef.current = true
      mediaRecorderRef.current.stop()
      mediaRecorderRef.current.stream.getTracks().forEach((track) => track.stop())
    }
  }

  useEffect(() => {
    if (inputMode !== 'text' || !interviewId || !currentQuestion || currentStage === 'END') {
      if (textAnswerTimerRef.current !== null) {
        window.clearInterval(textAnswerTimerRef.current)
        textAnswerTimerRef.current = null
      }
      return
    }
    const questionKey = pipelineMeta?.trace_id || `${currentStage}:${currentQuestion}`
    if (lastTextQuestionKeyRef.current === questionKey) {
      return
    }
    lastTextQuestionKeyRef.current = questionKey
    setTextAnswerRemainingSeconds(MAX_TEXT_ANSWER_SECONDS)
    if (textAnswerTimerRef.current !== null) {
      window.clearInterval(textAnswerTimerRef.current)
    }
    textAnswerTimerRef.current = window.setInterval(() => {
      setTextAnswerRemainingSeconds((previous) => {
        if (previous <= 1) {
          if (textAnswerTimerRef.current !== null) {
            window.clearInterval(textAnswerTimerRef.current)
            textAnswerTimerRef.current = null
          }
          return 0
        }
        return previous - 1
      })
    }, 1000)
  }, [inputMode, interviewId, currentQuestion, currentStage, pipelineMeta?.trace_id])

  useEffect(() => {
    const durationSeconds = Number(interviewStatusQuery.data?.duration_seconds ?? playbackQuery.data?.meta.duration_seconds ?? 0)
    const durationUpdatedAtRaw =
      interviewStatusQuery.data?.duration_updated_at || playbackQuery.data?.meta.duration_updated_at || ''
    const status = interviewStatusQuery.data?.status || playbackQuery.data?.meta.status || ''
    const durationUpdatedAt = parseBackendDate(durationUpdatedAtRaw)
    if (!durationUpdatedAt) {
      setInterviewElapsedSeconds(Math.max(0, durationSeconds))
      return
    }
    const refreshElapsed = () => {
      if (status !== 'ACTIVE') {
        setInterviewElapsedSeconds(Math.max(0, durationSeconds))
        return
      }
      const delta = Math.floor((Date.now() - durationUpdatedAt.getTime()) / 1000)
      setInterviewElapsedSeconds(Math.max(0, durationSeconds + Math.max(0, delta)))
    }
    refreshElapsed()
    const intervalId = window.setInterval(refreshElapsed, 1000)
    return () => window.clearInterval(intervalId)
  }, [
    interviewStatusQuery.data?.duration_seconds,
    interviewStatusQuery.data?.duration_updated_at,
    interviewStatusQuery.data?.status,
    playbackQuery.data?.meta.duration_seconds,
    playbackQuery.data?.meta.duration_updated_at,
    playbackQuery.data?.meta.status,
  ])

  /** 在语音输出且音频地址变化时尝试自动播放。 */
  useEffect(() => {
    if (outputMode !== 'voice' || !ttsAudioUrl || !autoPlayAudioRef.current) {
      return
    }
    void autoPlayAudioRef.current.play().catch(() => {
      message.info('浏览器拦截了自动播放，请手动点击播放按钮')
    })
  }, [outputMode, ttsAudioUrl, resumeReplayTick])

  /** 切换会话时重置录音与倒计时状态，避免继承上一次轮次。 */
  useEffect(() => {
    if (!interviewId) {
      return
    }
    resetRoundRuntimeState()
    setResumeReplayTick((previous) => previous + 1)
  }, [interviewId])

  /** 进入语音模式时主动准备设备列表，并监听设备变化。 */
  useEffect(() => {
    if (inputMode !== 'voice') {
      return
    }
    void prepareAudioInputDevices()
    const mediaDevices = navigator.mediaDevices
    if (!mediaDevices?.addEventListener) {
      return
    }
    const handleDeviceChange = () => {
      void refreshAudioInputDevices()
    }
    mediaDevices.addEventListener('devicechange', handleDeviceChange)
    return () => {
      mediaDevices.removeEventListener('devicechange', handleDeviceChange)
    }
  }, [inputMode])

  /** 题目语音播放结束后触发倒计时。 */
  const handleQuestionAudioEnded = () => {
    setQuestionAudioPlaying(false)
    if (inputMode !== 'voice' || !interviewId || !currentQuestion || currentStage === 'END') {
      return
    }
    const questionKey = buildQuestionKey()
    if (pendingCountdownQuestionKeyRef.current !== questionKey) {
      return
    }
    pendingCountdownQuestionKeyRef.current = ''
    startCountdownRecording(true)
  }

  /** 查询可选简历。 */
  const resumeQuery = useQuery({
    queryKey: ['resumes', 'interview-picker'],
    queryFn: () => fetchResumes({ page: 1, page_size: 50 }),
    enabled: resumePickerOpen,
  })
  /** 查询暂停中的面试。 */
  const pausedQuery = useQuery({
    queryKey: ['paused-interviews', 'interview-page'],
    queryFn: () => fetchHistory({ page: 1, page_size: 20, status: 'PAUSED' }),
    enabled: !interviewId,
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
      message.success('会话创建成功')
      setCreateModalOpen(false)
      navigate(`/interview/${data.interview_id}`)
    },
    onError: () => {
      message.error('创建会话失败，请重试')
    },
  })
  /** 恢复暂停面试。 */
  const resumePausedMutation = useMutation({
    mutationFn: (targetInterviewId: string) => fetchInterviewStatus(targetInterviewId, { status: 'ACTIVE' }),
    onMutate: (targetInterviewId) => {
      setResumingInterviewId(targetInterviewId)
    },
    onSuccess: (data) => {
      resetRoundRuntimeState()
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
      setResumeReplayTick((previous) => previous + 1)
      navigate(`/interview/${data.interview_id}`)
      setResumingInterviewId('')
    },
    onError: () => {
      message.error('恢复面试失败，请重试')
      setResumingInterviewId('')
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
    mutationFn: async (payload?: { voiceFile?: File }) =>
      inputMode === 'voice'
        ? submitAudioTurn(interviewId, {
            stage: currentStage,
            file: payload?.voiceFile || audioFile!,
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
      void queryClient.invalidateQueries({ queryKey: ['interview-playback', interviewId] })
      setAnswer('')
      setAudioFile(null)
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

  /** 暂停面试并保存进度。 */
  const pauseMutation = useMutation({
    mutationFn: () => fetchInterviewStatus(interviewId, { status: 'PAUSED' }),
    onSuccess: () => {
      message.success('面试已暂停，可在准备页继续')
      reset()
      navigate('/interview')
    },
    onError: () => {
      message.error('暂停失败，请重试')
    },
  })

  /** 将录音结果转为 File。 */
  const buildRecordedAudioFile = (blob: Blob) => {
    const extension = blob.type.includes('webm') ? 'webm' : 'wav'
    const filename = `voice-answer-${Date.now()}.${extension}`
    return new File([blob], filename, { type: blob.type || 'audio/webm' })
  }

  /** 停止录音并收集音频文件。 */
  const stopRecording = () => {
    if (countdownTimerRef.current !== null) {
      window.clearInterval(countdownTimerRef.current)
      countdownTimerRef.current = null
      setCountdown(0)
    }
    if (recordingLimitTimerRef.current !== null) {
      window.clearTimeout(recordingLimitTimerRef.current)
      recordingLimitTimerRef.current = null
    }
    if (recordingProgressTimerRef.current !== null) {
      window.clearInterval(recordingProgressTimerRef.current)
      recordingProgressTimerRef.current = null
    }
    setRecordingElapsedSeconds(0)
    if (!mediaRecorderRef.current || mediaRecorderRef.current.state === 'inactive') {
      setRecording(false)
      return
    }
    mediaRecorderRef.current.stop()
  }

  /** 启动浏览器麦克风录音。 */
  const startRecording = async () => {
    if (countdownTimerRef.current !== null) {
      window.clearInterval(countdownTimerRef.current)
      countdownTimerRef.current = null
      setCountdown(0)
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: selectedAudioInputId ? { deviceId: { exact: selectedAudioInputId } } : true,
      })
      const mediaRecorder = new MediaRecorder(stream)
      mediaRecorderRef.current = mediaRecorder
      audioChunksRef.current = []
      mediaRecorder.ondataavailable = (event: BlobEvent) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data)
        }
      }
      mediaRecorder.onstop = () => {
        if (suppressRecorderStopRef.current) {
          suppressRecorderStopRef.current = false
          audioChunksRef.current = []
          stream.getTracks().forEach((track) => track.stop())
          setRecording(false)
          return
        }
        if (recordingLimitTimerRef.current !== null) {
          window.clearTimeout(recordingLimitTimerRef.current)
          recordingLimitTimerRef.current = null
        }
        if (recordingProgressTimerRef.current !== null) {
          window.clearInterval(recordingProgressTimerRef.current)
          recordingProgressTimerRef.current = null
        }
        setRecordingElapsedSeconds(0)
        const blob = new Blob(audioChunksRef.current, { type: mediaRecorder.mimeType || 'audio/webm' })
        if (blob.size > 0) {
          const file = buildRecordedAudioFile(blob)
          setAudioFile(file)
          if (submitAfterStopRef.current) {
            submitAfterStopRef.current = false
            submitMutation.mutate({ voiceFile: file })
          } else {
            message.success('录音完成')
          }
        } else {
          submitAfterStopRef.current = false
          message.warning('未采集到音频，请重试')
        }
        stream.getTracks().forEach((track) => track.stop())
        setRecording(false)
      }
      mediaRecorder.start()
      setRecordingElapsedSeconds(0)
      setRecording(true)
      message.success('开始录音')
      recordingProgressTimerRef.current = window.setInterval(() => {
        setRecordingElapsedSeconds((previous) => Math.min(previous + 1, MAX_RECORDING_SECONDS))
      }, 1000)
      recordingLimitTimerRef.current = window.setTimeout(() => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
          submitAfterStopRef.current = true
          message.warning('录音已达到 3 分钟上限，已自动提交')
          stopRecording()
        }
      }, MAX_RECORDING_SECONDS * 1000)
    } catch {
      if (selectedAudioInputId) {
        try {
          const fallbackStream = await navigator.mediaDevices.getUserMedia({ audio: true })
          const mediaRecorder = new MediaRecorder(fallbackStream)
          mediaRecorderRef.current = mediaRecorder
          audioChunksRef.current = []
          mediaRecorder.ondataavailable = (event: BlobEvent) => {
            if (event.data.size > 0) {
              audioChunksRef.current.push(event.data)
            }
          }
          mediaRecorder.onstop = () => {
            if (suppressRecorderStopRef.current) {
              suppressRecorderStopRef.current = false
              audioChunksRef.current = []
              fallbackStream.getTracks().forEach((track) => track.stop())
              setRecording(false)
              return
            }
            if (recordingLimitTimerRef.current !== null) {
              window.clearTimeout(recordingLimitTimerRef.current)
              recordingLimitTimerRef.current = null
            }
            if (recordingProgressTimerRef.current !== null) {
              window.clearInterval(recordingProgressTimerRef.current)
              recordingProgressTimerRef.current = null
            }
            setRecordingElapsedSeconds(0)
            const blob = new Blob(audioChunksRef.current, { type: mediaRecorder.mimeType || 'audio/webm' })
            if (blob.size > 0) {
              const file = buildRecordedAudioFile(blob)
              setAudioFile(file)
              if (submitAfterStopRef.current) {
                submitAfterStopRef.current = false
                submitMutation.mutate({ voiceFile: file })
              } else {
                message.success('录音完成')
              }
            } else {
              submitAfterStopRef.current = false
              message.warning('未采集到音频，请重试')
            }
            fallbackStream.getTracks().forEach((track) => track.stop())
            setRecording(false)
          }
          mediaRecorder.start()
          setRecordingElapsedSeconds(0)
          setRecording(true)
          message.warning('所选麦克风不可用，已切换到系统默认麦克风')
          recordingProgressTimerRef.current = window.setInterval(() => {
            setRecordingElapsedSeconds((previous) => Math.min(previous + 1, MAX_RECORDING_SECONDS))
          }, 1000)
          recordingLimitTimerRef.current = window.setTimeout(() => {
            if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
              submitAfterStopRef.current = true
              message.warning('录音已达到 3 分钟上限，已自动提交')
              stopRecording()
            }
          }, MAX_RECORDING_SECONDS * 1000)
          return
        } catch {
          // 降级失败时沿用统一报错提示
        }
      }
      message.error('无法访问麦克风，请检查浏览器权限或切换输入设备')
      setRecording(false)
    }
  }

  /** 播放一声提示音，用于倒计时开始提醒。 */
  const playCountdownBeep = () => {
    try {
      const AudioContextCtor = window.AudioContext || (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
      if (!AudioContextCtor) {
        return
      }
      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContextCtor()
      }
      const audioContext = audioContextRef.current
      const oscillator = audioContext.createOscillator()
      const gainNode = audioContext.createGain()
      oscillator.type = 'sine'
      oscillator.frequency.value = 880
      gainNode.gain.value = 0.08
      oscillator.connect(gainNode)
      gainNode.connect(audioContext.destination)
      oscillator.start()
      window.setTimeout(() => oscillator.stop(), 120)
    } catch {
      // 浏览器音频策略限制时静默降级
    }
  }

  /** 执行 10 秒倒计时并在结束后自动开始录音。 */
  const startCountdownRecording = (force: boolean = false) => {
    if (!force && (recording || countdown > 0 || submitMutation.isPending || currentStage === 'END')) {
      return
    }
    if (force && mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      stopRecording()
    }
    if (countdownTimerRef.current !== null) {
      window.clearInterval(countdownTimerRef.current)
    }
    setRecordingElapsedSeconds(0)
    setCountdown(AUTO_RECORD_COUNTDOWN_SECONDS)
    playCountdownBeep()
    countdownTimerRef.current = window.setInterval(() => {
      setCountdown((previous) => {
        if (previous <= 1) {
          if (countdownTimerRef.current !== null) {
            window.clearInterval(countdownTimerRef.current)
          }
          countdownTimerRef.current = null
          void startRecording()
          return 0
        }
        return previous - 1
      })
    }, 1000)
  }

  /** 新题目出现时，语音输入自动倒计时 10 秒开始录音。 */
  useEffect(() => {
    if (inputMode !== 'voice' || !interviewId || !currentQuestion || currentStage === 'END') {
      return
    }
    const questionKey = buildQuestionKey()
    if (lastQuestionKeyRef.current === questionKey) {
      return
    }
    lastQuestionKeyRef.current = questionKey
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      stopRecording()
    }
    if (recordingProgressTimerRef.current !== null) {
      window.clearInterval(recordingProgressTimerRef.current)
      recordingProgressTimerRef.current = null
    }
    setRecordingElapsedSeconds(0)
    setAudioFile(null)
    if (outputMode === 'voice' && ttsAudioUrl) {
      pendingCountdownQuestionKeyRef.current = questionKey
      return
    }
    pendingCountdownQuestionKeyRef.current = ''
    startCountdownRecording(true)
  }, [inputMode, interviewId, currentQuestion, currentStage, outputMode, ttsAudioUrl, pipelineMeta?.trace_id])

  const recordingProgressPercent = Math.round((recordingElapsedSeconds / MAX_RECORDING_SECONDS) * 100)
  const formatDuration = (seconds: number) => {
    const safeSeconds = Math.max(0, seconds)
    const minute = Math.floor(safeSeconds / 60)
    const second = safeSeconds % 60
    return `${String(minute).padStart(2, '0')}:${String(second).padStart(2, '0')}`
  }
  const formatDateTime = (value?: string) => {
    const parsed = parseBackendDate(value)
    if (!parsed) {
      if (!value) {
        return '--'
      }
      return value
    }
    return parsed.toLocaleString('zh-CN', { hour12: false })
  }
  /** 阶段文案配色，仅作用于问题区右上角阶段名。 */
  const stageTextStyle = useMemo(() => {
    const styleMap: Record<string, { color: string; background: string }> = {
      SELF_INTRO: { color: '#ad6800', background: '#fff7e6' },
      TECHNICAL: { color: '#1d39c4', background: '#e6f4ff' },
      PROJECT: { color: '#237804', background: '#f6ffed' },
      SCENARIO: { color: '#531dab', background: '#f9f0ff' },
      END: { color: '#595959', background: '#fafafa' },
    }
    return styleMap[currentStage] || styleMap.TECHNICAL
  }, [currentStage])
  /** 将轮次按顺序整理，避免后端返回顺序波动影响展示。 */
  const sortedTurns = useMemo(
    () => [...(playbackQuery.data?.turns ?? [])].sort((left, right) => left.sequence - right.sequence),
    [playbackQuery.data?.turns],
  )

  if (!routeInterviewId) {
    return (
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <ProviderHealthBanner health={providerHealth} />
        <Card title="面试大厅">
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Space wrap>
              <Button type="primary" onClick={() => setCreateModalOpen(true)}>
                创建面试
              </Button>
              <Button onClick={() => navigate('/resumes')}>去上传/管理简历</Button>
            </Space>
            <Table
              rowKey="interview_id"
              loading={pausedQuery.isLoading}
              dataSource={pausedQuery.data?.items ?? []}
              pagination={false}
              columns={[
                {
                  title: '面试名称',
                  dataIndex: 'session_name',
                  render: (value?: string) => value || '-',
                },
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
                      loading={resumePausedMutation.isPending && resumingInterviewId === row.interview_id}
                      onClick={() => resumePausedMutation.mutate(row.interview_id)}
                    >
                      继续面试
                    </Button>
                  ),
                },
              ]}
              locale={{ emptyText: '暂无暂停中的面试，可点击“创建面试”开始。' }}
            />
          </Space>
        </Card>
        <Modal
          title="创建面试"
          open={createModalOpen}
          onCancel={() => setCreateModalOpen(false)}
          footer={null}
          destroyOnClose
        >
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
              <Form.Item
                name="session_name"
                label="面试名称"
                rules={[{ required: true, whitespace: true, message: '请输入面试名称' }]}
              >
                <Input placeholder="例如：Web前端场景专项" maxLength={128} />
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
          </Space>
        </Modal>
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
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: historyCollapsed
          ? 'minmax(0, 1fr) minmax(0, 3fr)'
          : 'minmax(0, 2fr) minmax(0, 4fr) minmax(0, 2fr)',
        gap: 16,
        width: '100%',
        transition: 'grid-template-columns 0.2s ease',
        boxSizing: 'border-box',
        overflowX: 'hidden',
      }}
    >
      <Space direction="vertical" size={16} style={{ width: '100%', minWidth: 0 }}>
        {/* <Card title="会话信息">
          <Space wrap>
            <Tag color="volcano">轮次：第 {followUpCount + 1} 轮</Tag>
            <Tag color="blue">阶段：{currentStage}</Tag>
            <Tag color="cyan">模式：{generationMode}</Tag>
            <Tag color="green">实时分：{liveScore}</Tag>
            <Tag color="gold">追问次数：{followUpCount}</Tag>
            <Tag color="magenta">输入模式：{inputMode}</Tag>
            <Tag color="purple">输出模式：{outputMode}</Tag>
            <Tag color="geekblue">会话ID：{interviewId}</Tag>
          </Space>
        </Card> */}
        <Card title="面试详情">
          <Space direction="vertical" size={10} style={{ width: '100%' }}>
            <div style={{ border: '1px solid #f0f0f0', borderRadius: 10, padding: 12, background: '#fafcff' }}>
              <Space align="start" size={10} style={{ width: '100%' }}>
                <CalendarOutlined style={{ color: '#7c6cff', marginTop: 2 }} />
                <div>
                  <Typography.Text type="secondary">创建时间</Typography.Text>
                  <div>{formatDateTime(playbackQuery.data?.meta.started_at)}</div>
                </div>
              </Space>
            </div>
            <div style={{ border: '1px solid #f0f0f0', borderRadius: 10, padding: 12, background: '#fafcff' }}>
              <Space align="start" size={10} style={{ width: '100%' }}>
                <ClockCircleOutlined style={{ color: '#7c6cff', marginTop: 2 }} />
                <div>
                  <Typography.Text type="secondary">开始时间</Typography.Text>
                  <div>{formatDateTime(playbackQuery.data?.meta.started_at)}</div>
                </div>
              </Space>
            </div>
            <div style={{ border: '1px solid #f0f0f0', borderRadius: 10, padding: 12, background: '#fafcff' }}>
              <Space align="start" size={10} style={{ width: '100%' }}>
                <HourglassOutlined style={{ color: '#7c6cff', marginTop: 2 }} />
                <div>
                  <Typography.Text type="secondary">面试时长</Typography.Text>
                  <div>{formatDuration(interviewElapsedSeconds)}</div>
                </div>
              </Space>
            </div>
            <div style={{ border: '1px solid #f0f0f0', borderRadius: 10, padding: 12, background: '#fafcff' }}>
              <Space align="start" size={10} style={{ width: '100%' }}>
                <FlagOutlined style={{ color: '#7c6cff', marginTop: 2 }} />
                <div style={{ width: '100%' }}>
                  <Typography.Text type="secondary">状态</Typography.Text>
                  <div>
                    <Tag color={interviewStatusQuery.data?.status === 'PAUSED' ? 'gold' : 'blue'}>
                      {interviewStatusQuery.data?.status || 'ACTIVE'}
                    </Tag>
                  </div>
                </div>
              </Space>
            </div>
            <div style={{ border: '1px solid #f0f0f0', borderRadius: 10, padding: 12, background: '#fafcff' }}>
              <Space align="start" size={10} style={{ width: '100%' }}>
                <FilePdfOutlined style={{ color: '#7c6cff', marginTop: 2 }} />
                <div style={{ width: '100%' }}>
                  <Typography.Text type="secondary">简历信息</Typography.Text>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                    <Typography.Text style={{ flex: 1, minWidth: 0 }} ellipsis={{ tooltip: true }}>
                      {playbackQuery.data?.resume.file_name || resumeId || '--'}
                    </Typography.Text>
                    <Button
                      size="small"
                      style={{ flex: '0 0 auto' }}
                      loading={previewMutation.isPending}
                      disabled={!playbackQuery.data?.resume.resume_id}
                      onClick={() =>
                        previewMutation.mutate({
                          resumeId: playbackQuery.data?.resume.resume_id || '',
                          fileName: playbackQuery.data?.resume.file_name || 'resume',
                        })
                      }
                    >
                      预览
                    </Button>
                  </div>
                </div>
              </Space>
            </div>
            <div style={{ border: '1px solid #f0f0f0', borderRadius: 10, padding: 12, background: '#fafcff' }}>
              <Space align="start" size={10} style={{ width: '100%' }}>
                <UserOutlined style={{ color: '#7c6cff', marginTop: 2 }} />
                <div>
                  <Typography.Text type="secondary">职位描述</Typography.Text>
                  <div>{interviewStatusQuery.data?.job_role || '--'}</div>
                </div>
              </Space>
            </div>
          </Space>
        </Card>
        <ProviderHealthBanner health={providerHealth} />
      </Space>

      <div style={{ display: 'grid', gridTemplateRows: '1fr 2fr', gap: 16, minHeight: 560, minWidth: 0 }}>
        <Card
          title="问题区"
          extra={
            <Space size={8}>
              <Typography.Text strong>
                阶段{' '}
                <span
                  style={{
                    color: stageTextStyle.color,
                    background: stageTextStyle.background,
                    borderRadius: 6,
                    padding: '2px 8px',
                  }}
                >
                  {currentStage}
                </span>
              </Typography.Text>
              <Typography.Text strong>轮次 {questionRound}</Typography.Text>
            </Space>
          }
        >
          {outputMode === 'voice' ? (
            <Space direction="vertical" style={{ width: '100%' }}>
              <Typography.Paragraph style={{ marginBottom: 0 }}>
                {currentQuestion ? '已生成语音题目，可直接播放。' : '等待题目生成...'}
              </Typography.Paragraph>
              {ttsAudioUrl ? (
                <audio
                  ref={autoPlayAudioRef}
                  controls
                  src={ttsAudioUrl}
                  style={{ width: '100%' }}
                  onPlay={() => setQuestionAudioPlaying(true)}
                  onPause={() => setQuestionAudioPlaying(false)}
                  onAbort={() => setQuestionAudioPlaying(false)}
                  onEmptied={() => setQuestionAudioPlaying(false)}
                  onError={() => setQuestionAudioPlaying(false)}
                  onEnded={handleQuestionAudioEnded}
                >
                  您的浏览器不支持音频播放。
                </audio>
              ) : (
                <Typography.Text type="secondary">当前题目语音暂不可用，可先参考文本作答。</Typography.Text>
              )}
            </Space>
          ) : (
            <Typography.Paragraph style={{ marginBottom: 0 }}>{currentQuestion || '等待题目生成...'}</Typography.Paragraph>
          )}
        </Card>

        <Card title="回答区">
          {inputMode === 'voice' ? (
            <Space direction="vertical" style={{ width: '100%' }}>
              <Typography.Text>本题目语音作答</Typography.Text>
              <Select
                style={{ width: '100%' }}
                loading={audioDevicesLoading}
                placeholder="选择麦克风设备"
                value={selectedAudioInputId || undefined}
                options={audioInputDevices}
                onChange={(value) => setSelectedAudioInputId(value)}
              />
              <Button
                block
                size="large"
                type={recording ? 'primary' : 'default'}
                style={{
                  height: 54,
                  borderRadius: 28,
                  background: '#b9e0db',
                  borderColor: '#b9e0db',
                  color: '#ffffff',
                  fontWeight: 600,
                }}
                loading={submitMutation.isPending}
                disabled={submitMutation.isPending || currentStage === 'END' || questionAudioPlaying}
                onClick={() => {
                  if (submitMutation.isPending || currentStage === 'END' || questionAudioPlaying) {
                    return
                  }
                  if (recording) {
                    submitAfterStopRef.current = true
                    stopRecording()
                    return
                  }
                  void startRecording()
                }}
              >
                {submitMutation.isPending
                  ? '请稍等...'
                  : recording
                    ? `录音中，点击结束回答 ${formatDuration(MAX_RECORDING_SECONDS - recordingElapsedSeconds)}`
                    : countdown > 0
                      ? `思考 ${countdown}s 后作答`
                      : '点击马上开始作答'}
              </Button>
              {!submitMutation.isPending ? (
                <Typography.Text type="secondary">
                  {questionAudioPlaying
                    ? '题目语音播放中，播放完成后才可作答。'
                    : recording
                      ? '系统将在 3 分钟后自动结束并提交回答。'
                      : '可点击按钮立即开始，或等待倒计时结束自动开始录音。'}
                </Typography.Text>
              ) : null}
            </Space>
          ) : (
            <Space direction="vertical" style={{ width: '100%' }}>
              <Typography.Text type={textAnswerRemainingSeconds <= 30 ? 'danger' : 'secondary'}>
                剩余作答时间：{formatDuration(textAnswerRemainingSeconds)}
              </Typography.Text>
              <Input.TextArea
                rows={6}
                value={answer}
                onChange={(event) => setAnswer(event.target.value)}
                placeholder="输入你的回答"
              />
            </Space>
          )}
          <div style={{ marginTop: 12, display: 'flex', justifyContent: inputMode !== 'voice' ? 'center' : 'flex-start' }}>
            {inputMode !== 'voice' ? (
              <Button
                type="primary"
                loading={submitMutation.isPending}
                disabled={submitMutation.isPending || currentStage === 'END'}
                onClick={() => {
                  if (submitMutation.isPending || currentStage === 'END') {
                    return
                  }
                  submitMutation.mutate(undefined)
                }}
              >
                提交回答
              </Button>
            ) : null}
          </div>
        </Card>
      </div>
      {!historyCollapsed ? (
        <div style={{ minWidth: 0, height: 720, maxHeight: 720 }}>
          <Card
            title="历史记录"
            style={{ height: '100%' }}
            bodyStyle={{ padding: 12, height: 'calc(100% - 57px)', overflowY: 'auto', overflowX: 'hidden' }}
          >
            {sortedTurns.length === 0 ? (
              <Typography.Text type="secondary">当前还没有历史轮次，完成一轮后会显示在这里。</Typography.Text>
            ) : (
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                {sortedTurns.map((turn) => (
                  <div key={turn.turn_id} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <Typography.Text type="secondary">第 {turn.sequence} 轮</Typography.Text>
                    <div
                      style={{
                        alignSelf: 'flex-start',
                        maxWidth: '95%',
                        background: '#f6faff',
                        border: '1px solid #d9ecff',
                        borderRadius: 12,
                        padding: '8px 10px',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                      }}
                    >
                      <Typography.Text strong>面试官：</Typography.Text>
                      <Typography.Text>{turn.question || '（暂无问题文本）'}</Typography.Text>
                    </div>
                    <div
                      style={{
                        alignSelf: 'flex-end',
                        maxWidth: '95%',
                        background: '#f6fff8',
                        border: '1px solid #dcf3e4',
                        borderRadius: 12,
                        padding: '8px 10px',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                      }}
                    >
                      <Typography.Text strong>我：</Typography.Text>
                      <Typography.Text>{turn.answer || '（本轮回答为空）'}</Typography.Text>
                    </div>
                  </div>
                ))}
              </Space>
            )}
          </Card>
        </div>
      ) : null}
      <div
        style={{
          position: 'fixed',
          right: 24,
          top: 180,
          zIndex: 30,
        }}
      >
        <Space direction="vertical" size={8}>
          <Button
            aria-label={historyCollapsed ? '展开历史记录' : '收起历史记录'}
            icon={<UnorderedListOutlined />}
            onClick={() => setHistoryCollapsed((previous) => !previous)}
            style={{ width: 48, height: 48 }}
          />
          <Dropdown
            trigger={['click']}
            menu={{
              items: [
                {
                  key: 'pause',
                  label: '暂停并保存进度',
                  disabled: pauseMutation.isPending || finishMutation.isPending,
                },
                {
                  key: 'finish',
                  label: '结束面试',
                  danger: true,
                  disabled: finishMutation.isPending || pauseMutation.isPending,
                },
              ],
              onClick: ({ key }) => {
                if (key === 'pause') {
                  pauseMutation.mutate()
                }
                if (key === 'finish') {
                  finishMutation.mutate()
                }
              },
            }}
          >
            <Button loading={pauseMutation.isPending || finishMutation.isPending} style={{ width: 48, height: 48 }}>
              ⋮
            </Button>
          </Dropdown>
        </Space>
      </div>
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
    </div>
  )
}
