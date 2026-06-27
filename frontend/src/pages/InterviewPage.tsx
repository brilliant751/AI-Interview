import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarOutlined, ClockCircleOutlined, FilePdfOutlined, FlagOutlined, HourglassOutlined, RedoOutlined, UnorderedListOutlined, UserOutlined } from '@ant-design/icons'
import { Badge, Button, Calendar, Card, Checkbox, Col, Dropdown, Form, Grid, Input, Modal, Progress, Radio, Row, Select, Space, Statistic, Switch, Table, Tag, Tooltip, Typography, message } from 'antd'
import { AxiosError } from 'axios'
import dayjs, { type Dayjs } from 'dayjs'
import { Activity, ArrowRight, BriefcaseBusiness, CalendarClock, ChevronDown, ChevronUp, CirclePause, Code2, Database, FileText, Mic, Play, ShieldCheck, Upload, type LucideIcon } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { fetchProviderHealth } from '../api/admin'
import { ProviderHealthBanner } from '../components/ProviderHealthBanner'
import {
  createInterview,
  fetchHistory,
  fetchInterviewPlayback,
  fetchScheduledInterviews,
  fetchJds,
  fetchTurnJobResult,
  fetchInterviewStatus,
  pauseInterview,
  fetchResumeFile,
  fetchResumes,
  fetchVoiceToneProfiles,
  finishInterview,
  startScheduledInterview,
  submitAudioTurn,
  submitTurn,
} from '../api/interview'
import { useDeadlineCountdown } from '../hooks/useDeadlineCountdown'
import { useInterviewStore } from '../stores/interviewStore'

/** 面试答题页面。 */
export function InterviewPage() {
  const screens = Grid.useBreakpoint()
  const isTabletUp = Boolean(screens.lg)
  const isDesktopWide = Boolean(screens.xl)
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
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [resumePickerOpen, setResumePickerOpen] = useState(false)
  const [jdPickerOpen, setJdPickerOpen] = useState(false)
  const [pendingResumeId, setPendingResumeId] = useState('')
  const [pendingJdId, setPendingJdId] = useState('')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewTitle, setPreviewTitle] = useState('')
  const [previewType, setPreviewType] = useState('')
  const [previewUrl, setPreviewUrl] = useState('')
  const [resumingInterviewId, setResumingInterviewId] = useState('')
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const suppressRecorderStopRef = useRef(false)
  const submitAfterStopRef = useRef(false)
  const lastQuestionKeyRef = useRef('')
  const pendingCountdownQuestionKeyRef = useRef('')
  const autoPlayAudioRef = useRef<HTMLAudioElement | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const lastRoundQuestionKeyRef = useRef('')
  const [questionRound, setQuestionRound] = useState(1)
  const [interviewElapsedSeconds, setInterviewElapsedSeconds] = useState(0)
  const [audioInputDevices, setAudioInputDevices] = useState<Array<{ label: string; value: string }>>([])
  const [selectedAudioInputId, setSelectedAudioInputId] = useState('')
  const [audioDevicesLoading, setAudioDevicesLoading] = useState(false)
  const [resumeReplayTick, setResumeReplayTick] = useState(0)
  const [createJobRole, setCreateJobRole] = useState<'java' | 'web'>('java')
  const [createPositionMode, setCreatePositionMode] = useState<'role' | 'jd'>('role')
  const [createSelectedJdTitle, setCreateSelectedJdTitle] = useState('')
  const [calendarValue, setCalendarValue] = useState<Dayjs>(() => dayjs())
  const [selectedScheduleDate, setSelectedScheduleDate] = useState<Dayjs>(() => dayjs())
  const [startingScheduleInterviewId, setStartingScheduleInterviewId] = useState('')
  const [jdFilterRole, setJdFilterRole] = useState('')
  const [jdFilterTitle, setJdFilterTitle] = useState('')
  const [questionAudioPlaying, setQuestionAudioPlaying] = useState(false)
  const [questionAudioEnded, setQuestionAudioEnded] = useState(false)
  const [suspendPolling, setSuspendPolling] = useState(false)
  const [displayedQuestionText, setDisplayedQuestionText] = useState('')
  const questionStreamTimerRef = useRef<number | null>(null)
  const audioBarSeedsRef = useRef(
    Array.from({ length: 14 }, () => ({
      base: Math.floor(24 + Math.random() * 42),
      duration: Math.floor(720 + Math.random() * 760),
      delay: Math.floor(Math.random() * 480),
      animationType: Math.floor(Math.random() * 4),
    })),
  )
  const endRedirectedRef = useRef(false)
  const [historyCollapsed, setHistoryCollapsed] = useState(false)
  const [healthDetailsOpen, setHealthDetailsOpen] = useState(false)
  const lastTextQuestionKeyRef = useRef('')
  const [createForm] = Form.useForm()
  const parseBackendDate = useCallback((value?: string) => {
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
  }, [])
  /** 将表单中的本地日期时间转换为 ISO 字符串。 */
  const toScheduleIsoString = (value?: string) => {
    if (!value) {
      return ''
    }
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) {
      return ''
    }
    return parsed.toISOString()
  }
  /** 按本地日期生成 YYYY-MM-DD key。 */
  const buildDateKey = useCallback((value?: string) => {
    const parsed = parseBackendDate(value)
    if (!parsed) {
      return ''
    }
    const year = parsed.getFullYear()
    const month = String(parsed.getMonth() + 1).padStart(2, '0')
    const day = String(parsed.getDate()).padStart(2, '0')
    return `${year}-${month}-${day}`
  }, [parseBackendDate])
  /** 格式化预约开始时间。 */
  const formatScheduleDateTime = (value?: string) => {
    const parsed = parseBackendDate(value)
    if (!parsed) {
      return '--'
    }
    return parsed.toLocaleString('zh-CN', {
      hour12: false,
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  }
  /** 判断请求是否属于主动取消。 */
  const isCanceledRequestError = (error: unknown) => {
    const axiosError = error as AxiosError
    const code = String(axiosError?.code || '')
    const name = String((axiosError as { name?: string })?.name || '')
    const messageText = String((axiosError as { message?: string })?.message || '').toLowerCase()
    return code === 'ERR_CANCELED' || name === 'CanceledError' || messageText.includes('canceled')
  }
  /** 计算麦克风优先级：优先本机内建麦克风，弱化 iPhone 连续互通设备。 */
  const scoreAudioInputLabel = useCallback((label: string) => {
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
  }, [])
  /** 从设备列表中挑选默认麦克风。 */
  const pickPreferredAudioInputId = useCallback((devices: MediaDeviceInfo[]) => {
    if (devices.length === 0) {
      return ''
    }
    const sorted = [...devices].sort((left, right) => scoreAudioInputLabel(right.label) - scoreAudioInputLabel(left.label))
    return sorted[0].deviceId
  }, [scoreAudioInputLabel])
  /** 刷新可用麦克风设备列表并更新默认选择。 */
  const refreshAudioInputDevices = useCallback(async () => {
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
  }, [pickPreferredAudioInputId])
  /** 请求麦克风权限后刷新设备，用于拿到完整设备名称。 */
  const prepareAudioInputDevices = useCallback(async () => {
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
  }, [refreshAudioInputDevices])
  const {
    resumeId,
    currentStage,
    currentQuestion,
    inputMode,
    outputMode,
    ttsAudioUrl,
    pipelineMeta,
    providerHealth,
    updateTurnResult,
    setProviderHealth,
    syncSessionStatus,
    setResumeId,
    setSessionConfig,
    reset,
  } = useInterviewStore((state) => state)
  const interviewId = routeInterviewId || ''
  /** 生成当前题目的稳定 key，避免受实时分/追问次数轮询抖动影响。 */
  const buildQuestionKey = useCallback(() => pipelineMeta?.trace_id || `${currentStage}:${currentQuestion}`, [currentQuestion, currentStage, pipelineMeta?.trace_id])
  const {
    remainingSeconds: textAnswerRemainingSeconds,
    start: startTextAnswerCountdown,
    stop: stopTextAnswerCountdown,
  } = useDeadlineCountdown({ initialSeconds: MAX_TEXT_ANSWER_SECONDS })
  const {
    remainingSeconds: countdown,
    start: startVoiceAutoRecordCountdown,
    stop: stopVoiceAutoRecordCountdown,
    isRunning: isVoiceAutoRecordCountdownRunning,
  } = useDeadlineCountdown({
    initialSeconds: AUTO_RECORD_COUNTDOWN_SECONDS,
    onExpire: () => {
      void startRecording()
    },
  })
  const {
    remainingSeconds: recordingLimitRemainingSeconds,
    start: startRecordingLimitCountdown,
    stop: stopRecordingLimitCountdown,
  } = useDeadlineCountdown({
    initialSeconds: MAX_RECORDING_SECONDS,
    onExpire: () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        submitAfterStopRef.current = true
        message.warning('录音已达到 3 分钟上限，已自动提交')
        stopRecording()
      }
    },
  })
  const recordingRemainingSeconds = recording ? recordingLimitRemainingSeconds : MAX_RECORDING_SECONDS

  /** 面试页主动拉取 provider 健康状态，避免仅依赖准备页缓存。 */
  const healthQuery = useQuery({
    queryKey: ['provider-health', 'interview-page'],
    queryFn: fetchProviderHealth,
    enabled: !suspendPolling,
    retry: false,
    refetchInterval: suspendPolling ? false : 15000,
  })
  /** 会话页拉取状态，确保支持直接访问 /interview/{id}。 */
  const interviewStatusQuery = useQuery({
    queryKey: ['interview-status', interviewId],
    queryFn: () => fetchInterviewStatus(interviewId),
    enabled: Boolean(interviewId) && !suspendPolling,
    refetchInterval: suspendPolling ? false : 15000,
  })
  /** 查询面试详情（用于左侧详情面板）。 */
  const playbackQuery = useQuery({
    queryKey: ['interview-playback', interviewId],
    queryFn: () => fetchInterviewPlayback(interviewId),
    enabled: Boolean(interviewId) && !suspendPolling,
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
      currentQuestion: status.current_question,
      ttsAudioUrl: status.tts_audio_url,
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
      if (questionStreamTimerRef.current !== null) {
        window.clearInterval(questionStreamTimerRef.current)
      }
      if (audioContextRef.current) {
        void audioContextRef.current.close()
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop()
      }
    }
  }, [])

  /** 新题目出现时按字符流式显示文本，便于边听边看。 */
  useEffect(() => {
    if (questionStreamTimerRef.current !== null) {
      window.clearInterval(questionStreamTimerRef.current)
      questionStreamTimerRef.current = null
    }
    setDisplayedQuestionText('')
    const text = (currentQuestion || '').trim()
    if (!text) {
      return
    }
    let cursor = 0
    questionStreamTimerRef.current = window.setInterval(() => {
      cursor += 1
      setDisplayedQuestionText(text.slice(0, cursor))
      if (cursor >= text.length && questionStreamTimerRef.current !== null) {
        window.clearInterval(questionStreamTimerRef.current)
        questionStreamTimerRef.current = null
      }
    }, 80)
    return () => {
      if (questionStreamTimerRef.current !== null) {
        window.clearInterval(questionStreamTimerRef.current)
        questionStreamTimerRef.current = null
      }
    }
  }, [currentQuestion, pipelineMeta?.trace_id, currentStage])

  /** 重置当前轮次的前端运行态，确保恢复会话时从新一轮开始。 */
  const resetRoundRuntimeState = useCallback(() => {
    stopVoiceAutoRecordCountdown(0)
    stopRecordingLimitCountdown(0)
    stopTextAnswerCountdown(MAX_TEXT_ANSWER_SECONDS)
    setRecording(false)
    setAudioFile(null)
    setAnswer('')
    submitAfterStopRef.current = false
    lastQuestionKeyRef.current = ''
    lastTextQuestionKeyRef.current = ''
    pendingCountdownQuestionKeyRef.current = ''
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      suppressRecorderStopRef.current = true
      mediaRecorderRef.current.stop()
      mediaRecorderRef.current.stream.getTracks().forEach((track) => track.stop())
    }
  }, [MAX_TEXT_ANSWER_SECONDS, stopRecordingLimitCountdown, stopTextAnswerCountdown, stopVoiceAutoRecordCountdown])

  useEffect(() => {
    if (inputMode !== 'text' || !interviewId || !currentQuestion || currentStage === 'END') {
      stopTextAnswerCountdown(MAX_TEXT_ANSWER_SECONDS)
      return
    }
    const questionKey = pipelineMeta?.trace_id || `${currentStage}:${currentQuestion}`
    if (lastTextQuestionKeyRef.current === questionKey) {
      return
    }
    lastTextQuestionKeyRef.current = questionKey
    startTextAnswerCountdown(MAX_TEXT_ANSWER_SECONDS)
  }, [inputMode, interviewId, currentQuestion, currentStage, pipelineMeta?.trace_id, startTextAnswerCountdown, stopTextAnswerCountdown])

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

  /** 题目更新后重置重播状态。 */
  useEffect(() => {
    setQuestionAudioEnded(false)
  }, [ttsAudioUrl, pipelineMeta?.trace_id, currentQuestion, currentStage])

  /** 切换会话时重置录音与倒计时状态，避免继承上一次轮次。 */
  useEffect(() => {
    if (!interviewId) {
      return
    }
    resetRoundRuntimeState()
    setResumeReplayTick((previous) => previous + 1)
  }, [interviewId, resetRoundRuntimeState])

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
  }, [inputMode, prepareAudioInputDevices, refreshAudioInputDevices])

  /** 题目语音播放结束后触发倒计时。 */
  const handleQuestionAudioEnded = () => {
    setQuestionAudioPlaying(false)
    setQuestionAudioEnded(true)
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
  /** 查询当前月份的预约面试。 */
  const scheduleQuery = useQuery({
    queryKey: ['interview-schedules', calendarValue.format('YYYY-MM')],
    queryFn: () =>
      fetchScheduledInterviews({
        scheduled_from: calendarValue.startOf('month').toDate().toISOString(),
        scheduled_to: calendarValue.endOf('month').toDate().toISOString(),
        statuses: ['SCHEDULED', 'ACTIVE', 'PAUSED'],
      }),
    enabled: !interviewId,
  })
  const toneQuery = useQuery({
    queryKey: ['voice-tone-profiles', 'interview-page-modal'],
    queryFn: fetchVoiceToneProfiles,
  })

  /** 查询创建面试弹窗中的 JD 列表。 */
  const jdQuery = useQuery({
    queryKey: ['jds', 'interview-page-create', jdPickerOpen, jdFilterRole, jdFilterTitle],
    queryFn: () =>
      fetchJds({
        job_role: jdFilterRole.trim() || undefined,
        title: jdFilterTitle.trim() || undefined,
      }),
    enabled: jdPickerOpen,
  })

  useEffect(() => {
    if (jdPickerOpen) {
      void jdQuery.refetch()
    }
  }, [jdPickerOpen, jdQuery])

  const selectedResumeName = useMemo(() => {
    const items = resumeQuery.data?.items ?? []
    const current = items.find((item) => item.resume_id === resumeId)
    return current?.file_name || ''
  }, [resumeId, resumeQuery.data])
  const scheduleItems = useMemo(() => scheduleQuery.data?.items ?? [], [scheduleQuery.data?.items])
  const scheduleMap = useMemo(() => {
    const mapped = new Map<string, typeof scheduleItems>()
    scheduleItems.forEach((item) => {
      const key = buildDateKey(item.scheduled_start_at)
      const currentItems = mapped.get(key) ?? []
      currentItems.push(item)
      mapped.set(key, currentItems)
    })
    return mapped
  }, [buildDateKey, scheduleItems])
  const selectedScheduleItems = useMemo(
    () => scheduleMap.get(selectedScheduleDate.format('YYYY-MM-DD')) ?? [],
    [scheduleMap, selectedScheduleDate],
  )

  /** 创建面试会话。 */
  const createMutation = useMutation({
    mutationFn: createInterview,
    onSuccess: (data, variables) => {
      setCreateModalOpen(false)
      queryClient.invalidateQueries({ queryKey: ['interview-schedules'] }).catch(() => undefined)
      queryClient.invalidateQueries({ queryKey: ['today-interview-schedules'] }).catch(() => undefined)
      queryClient.invalidateQueries({ queryKey: ['paused-interviews', 'interview-page'] }).catch(() => undefined)
      if (data.status === 'SCHEDULED') {
        message.success(`预约成功，开始时间：${formatScheduleDateTime(data.scheduled_start_at)}`)
        return
      }
      setSessionConfig({
        interviewId: data.interview_id,
        jobRole: variables.job_role || createJobRole,
        difficulty: variables.difficulty,
        inputMode: variables.input_mode,
        outputMode: variables.output_mode,
        stage: data.current_stage,
        firstQuestion: data.first_question,
        ttsAudioUrl: data.tts_audio_url,
      })
      message.success('会话创建成功')
      navigate(`/interview/${data.interview_id}`)
    },
    onError: () => {
      message.error('创建会话失败，请重试')
    },
  })
  /** 开始预约面试。 */
  const startScheduleMutation = useMutation({
    mutationFn: startScheduledInterview,
    onMutate: (targetInterviewId) => {
      setStartingScheduleInterviewId(targetInterviewId)
    },
    onSuccess: (data) => {
      resetRoundRuntimeState()
      setSessionConfig({
        interviewId: data.interview_id,
        jobRole: data.job_role,
        difficulty: data.difficulty,
        inputMode: data.input_mode,
        outputMode: data.output_mode,
        stage: data.stage,
        firstQuestion: data.question,
        ttsAudioUrl: data.tts_audio_url,
      })
      queryClient.invalidateQueries({ queryKey: ['interview-schedules'] }).catch(() => undefined)
      queryClient.invalidateQueries({ queryKey: ['today-interview-schedules'] }).catch(() => undefined)
      message.success('已开始预约面试')
      navigate(`/interview/${data.interview_id}`)
      setStartingScheduleInterviewId('')
    },
    onError: (error) => {
      const parsed = (error as AxiosError<{ error?: { message?: string } }>)?.response?.data?.error?.message
      message.error(parsed || '开始预约面试失败，请重试')
      setStartingScheduleInterviewId('')
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
    onMutate: () => {
      setSuspendPolling(true)
    },
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
    onSuccess: async (data) => {
      const startedAt = Date.now()
      while (Date.now() - startedAt < 120000) {
        let job
        try {
          job = await fetchTurnJobResult(interviewId, data.job_id)
        } catch (error) {
          if (isCanceledRequestError(error)) {
            try {
              const sessionStatus = await fetchInterviewStatus(interviewId)
              syncSessionStatus({
                stage: sessionStatus.current_stage,
                followUpCount: sessionStatus.follow_up_count,
                currentQuestion: sessionStatus.current_question,
                ttsAudioUrl: sessionStatus.tts_audio_url,
              })
              message.warning('请求被取消，已同步最新状态')
            } catch {
              message.warning('请求被取消，请刷新页面确认当前轮次')
            }
            return
          }
          message.error('任务状态查询失败，请重试')
          return
        }
        if (job.status === 'READY' && job.result) {
          updateTurnResult({
            stage: job.result.stage,
            question: job.result.next_question,
            score: job.result.live_score,
            followUpCount: job.result.follow_up_count,
            ttsAudioUrl: job.result.tts_audio_url,
            pipelineMeta: job.result.pipeline_meta,
          })
          void queryClient.invalidateQueries({ queryKey: ['interview-playback', interviewId] })
          setAnswer('')
          setAudioFile(null)
          message.success('已生成下一题')
          return
        }
        if (job.status === 'FAILED') {
          message.error(job.error_message || '提交失败，请重试')
          return
        }
        await new Promise((resolve) => {
          window.setTimeout(resolve, 800)
        })
      }
      message.warning('处理超时，请稍后重试或刷新页面查看最新状态')
    },
    onError: async (error) => {
      const axiosError = error as AxiosError<{ error?: { code?: string; message?: string } }>
      if (isCanceledRequestError(error)) {
        try {
          const sessionStatus = await fetchInterviewStatus(interviewId)
          syncSessionStatus({
            stage: sessionStatus.current_stage,
            followUpCount: sessionStatus.follow_up_count,
            currentQuestion: sessionStatus.current_question,
            ttsAudioUrl: sessionStatus.tts_audio_url,
          })
          message.warning('请求已取消，已同步到最新面试状态')
          return
        } catch {
          message.warning('请求已取消，请刷新页面确认当前轮次')
          return
        }
      }
      const apiError = axiosError.response?.data?.error
      const errorCode = apiError?.code || ''
      const errorMessage = apiError?.message || '提交失败，请重试'

      if (errorCode === 'STATE_409') {
        try {
          const sessionStatus = await fetchInterviewStatus(interviewId)
          syncSessionStatus({
            stage: sessionStatus.current_stage,
            followUpCount: sessionStatus.follow_up_count,
            currentQuestion: sessionStatus.current_question,
            ttsAudioUrl: sessionStatus.tts_audio_url,
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
    onSettled: () => {
      setSuspendPolling(false)
    },
  })

  /** 结束面试。 */
  const finishMutation = useMutation({
    onMutate: () => {
      setSuspendPolling(true)
    },
    mutationFn: () => finishInterview(interviewId),
    onSuccess: () => {
      message.success('面试已结束，正在生成报告')
      navigate(`/report/${interviewId}`)
    },
    onError: async (error) => {
      if (isCanceledRequestError(error)) {
        try {
          // 取消场景下自动补一次结束请求，避免用户停留在“无法结束”状态。
          await finishInterview(interviewId)
        } catch {
          // ignore retry error
        }
        try {
          const sessionStatus = await fetchInterviewStatus(interviewId)
          if (sessionStatus.status === 'FINISHED' || sessionStatus.current_stage === 'END') {
            message.success('面试已结束，正在跳转报告页')
            navigate(`/report/${interviewId}`)
            return
          }
        } catch {
          // ignore
        }
        message.warning('结束请求被取消，正在跳转报告页继续确认状态')
        navigate(`/report/${interviewId}`)
        return
      }
      const axiosError = error as AxiosError<{ error?: { message?: string } }>
      if (axiosError.code === 'ECONNABORTED') {
        message.warning('结束请求超时，正在跳转报告页继续确认状态')
        navigate(`/report/${interviewId}`)
        return
      }
      message.error(axiosError.response?.data?.error?.message || '结束面试失败')
    },
    onSettled: () => {
      setSuspendPolling(false)
    },
  })

  /** 暂停面试并保存进度。 */
  const pauseMutation = useMutation({
    onMutate: () => {
      setSuspendPolling(true)
    },
    mutationFn: () => pauseInterview(interviewId),
    onSuccess: () => {
      message.success('面试已暂停，可在准备页继续')
      reset()
      navigate('/interview')
    },
    onError: () => {
      message.error('暂停失败，请重试')
    },
    onSettled: () => {
      setSuspendPolling(false)
    },
  })

  /** 将录音结果转为 File。 */
  const buildRecordedAudioFile = (blob: Blob) => {
    const extension = blob.type.includes('webm') ? 'webm' : 'wav'
    const filename = `voice-answer-${Date.now()}.${extension}`
    return new File([blob], filename, { type: blob.type || 'audio/webm' })
  }

  /** 停止录音并收集音频文件。 */
  const stopRecording = useCallback(() => {
    stopVoiceAutoRecordCountdown(0)
    stopRecordingLimitCountdown(0)
    if (!mediaRecorderRef.current || mediaRecorderRef.current.state === 'inactive') {
      setRecording(false)
      return
    }
    mediaRecorderRef.current.stop()
  }, [stopRecordingLimitCountdown, stopVoiceAutoRecordCountdown])

  /** 启动浏览器麦克风录音。 */
  const startRecording = async () => {
    stopVoiceAutoRecordCountdown(0)
    stopRecordingLimitCountdown(0)
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
        stopRecordingLimitCountdown(0)
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
      setRecording(true)
      message.success('开始录音')
      startRecordingLimitCountdown(MAX_RECORDING_SECONDS)
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
            stopRecordingLimitCountdown(0)
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
          setRecording(true)
          message.warning('所选麦克风不可用，已切换到系统默认麦克风')
          startRecordingLimitCountdown(MAX_RECORDING_SECONDS)
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
  const startCountdownRecording = useCallback((force: boolean = false) => {
    if (!force && (recording || isVoiceAutoRecordCountdownRunning() || submitMutation.isPending || currentStage === 'END')) {
      return
    }
    if (force && mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      stopRecording()
    }
    stopRecordingLimitCountdown(0)
    playCountdownBeep()
    startVoiceAutoRecordCountdown(AUTO_RECORD_COUNTDOWN_SECONDS)
  }, [
    AUTO_RECORD_COUNTDOWN_SECONDS,
    currentStage,
    isVoiceAutoRecordCountdownRunning,
    recording,
    startVoiceAutoRecordCountdown,
    stopRecordingLimitCountdown,
    submitMutation.isPending,
  ])

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
    stopRecordingLimitCountdown(0)
    setAudioFile(null)
    if (outputMode === 'voice' && ttsAudioUrl) {
      pendingCountdownQuestionKeyRef.current = questionKey
      return
    }
    pendingCountdownQuestionKeyRef.current = ''
    startCountdownRecording(true)
  }, [buildQuestionKey, currentQuestion, currentStage, inputMode, interviewId, outputMode, pipelineMeta?.trace_id, startCountdownRecording, ttsAudioUrl])

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
    const pausedItems = pausedQuery.data?.items ?? []
    const pausedCount = pausedItems.length
    const resumedAtText = pausedItems[0]?.started_at ? formatDateTime(pausedItems[0].started_at) : '--'
    const quickStartRoles: Array<{ key: string; title: string; subtitle: string; icon: LucideIcon }> = [
      { key: 'web', title: 'Web 前端工程师', subtitle: '项目表达 / 性能优化 / 工程化', icon: Code2 },
      { key: 'java', title: 'Java 后端工程师', subtitle: '并发 / 系统设计 / 数据库', icon: Database },
      { key: 'pm', title: '产品经理', subtitle: '需求分析 / 指标拆解 / 场景沟通', icon: BriefcaseBusiness },
      { key: 'test', title: '测试工程师', subtitle: '测试策略 / 缺陷追踪 / 质量门禁', icon: ShieldCheck },
    ]
    const roleColorMap: Record<string, string> = {
      web: 'blue',
      java: 'cyan',
    }
    const difficultyColorMap: Record<string, string> = {
      easy: 'green',
      medium: 'gold',
      hard: 'red',
    }
    const statusColorMap: Record<string, string> = {
      SCHEDULED: 'blue',
      PAUSED: 'processing',
      ACTIVE: 'green',
      FINISHED: 'default',
    }
    const scheduleCount = scheduleItems.length
    const selectedDateLabel = selectedScheduleDate.format('YYYY 年 MM 月 DD 日')
    const calendarCellRender = (current: Dayjs, info: { originNode: React.ReactNode; type: string }) => {
      if (info.type !== 'date') {
        return info.originNode
      }
      const currentItems = scheduleMap.get(current.format('YYYY-MM-DD')) ?? []
      if (currentItems.length === 0) {
        return info.originNode
      }
      return (
        <div style={{ minHeight: 68, padding: '4px 2px' }}>
          <div>{info.originNode}</div>
          <Space direction="vertical" size={2} style={{ width: '100%' }}>
            <Badge
              count={currentItems.length}
              style={{ backgroundColor: currentItems.some((item) => item.start_available) ? '#4A9BE8' : '#1677ff' }}
            />
            <Typography.Text style={{ fontSize: 11 }} ellipsis>
              {formatScheduleDateTime(currentItems[0]?.scheduled_start_at)}
            </Typography.Text>
          </Space>
        </div>
      )
    }
    return (
      <Space className="interview-lobby" direction="vertical" size={16} style={{ width: '100%' }}>
        <Card
          className="interview-lobby-hero"
          style={{
            background: 'linear-gradient(120deg, #e8f0ff 0%, #dbe8ff 62%, #f1f5ff 100%)',
            border: '1px solid #d3e3ff',
          }}
        >
          <Row gutter={[16, 16]} align="middle">
            <Col xs={24} xl={16}>
              <Typography.Title level={3} style={{ marginTop: 0 }}>
                面试大厅
              </Typography.Title>
              <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
                开始新的模拟面试，或继续上次未完成会话。建议优先练习项目表达和技术方案讲解。
              </Typography.Paragraph>
              <Space wrap className="interview-lobby-actions">
                <Button className="interview-lobby-btn-primary" type="primary" size="large" icon={<Play size={16} />} onClick={() => setCreateModalOpen(true)}>
                  开始新面试
                </Button>
                <Button className="interview-lobby-btn-secondary" size="large" icon={<Upload size={16} />} onClick={() => navigate('/resumes')}>
                  上传/管理简历
                </Button>
                <Button className="interview-lobby-btn-secondary" size="large" icon={<FileText size={16} />} onClick={() => navigate('/report')}>
                  查看我的报告
                </Button>
              </Space>
            </Col>
            <Col xs={24} xl={8}>
              <Space direction="vertical" size={10} style={{ width: '100%' }}>
                <Card className="interview-lobby-mini-card" size="small">
                  <Space align="start" size={10}>
                    <div className="interview-lobby-icon-wrap purple"><CirclePause size={18} /></div>
                    <Statistic title="待继续会话" value={pausedCount} suffix="个" />
                  </Space>
                </Card>
                <Card className="interview-lobby-mini-card" size="small">
                  <Space align="start" size={10}>
                    <div className="interview-lobby-icon-wrap green"><CalendarClock size={18} /></div>
                    <div>
                      <Typography.Text type="secondary">最近保存时间</Typography.Text>
                      <Typography.Paragraph style={{ marginBottom: 0 }}>{resumedAtText}</Typography.Paragraph>
                    </div>
                  </Space>
                </Card>
              </Space>
            </Col>
          </Row>
        </Card>

        <Row gutter={[16, 16]}>
          <Col xs={24} xl={8}>
            <Card className="interview-lobby-kpi-card">
              <Space align="start" size={10}>
                <div className="interview-lobby-icon-wrap blue"><CirclePause size={18} /></div>
                <Statistic title="暂停中的面试" value={pausedCount} suffix="场" />
              </Space>
            </Card>
          </Col>
          <Col xs={24} xl={8}>
            <Card className="interview-lobby-kpi-card">
              <Space align="start" size={10}>
                <div className="interview-lobby-icon-wrap violet"><Mic size={18} /></div>
                <Statistic title="语音答题时长上限" value={MAX_RECORDING_SECONDS} suffix="秒/题" />
              </Space>
            </Card>
          </Col>
          <Col xs={24} xl={8}>
            <Card className="interview-lobby-kpi-card">
              <Space direction="vertical" size={8} style={{ width: '100%' }}>
                <Space align="start" size={10}>
                  <div className="interview-lobby-icon-wrap green"><FileText size={18} /></div>
                  <Typography.Text type="secondary">文本答题剩余建议</Typography.Text>
                </Space>
                <Progress percent={Math.round((textAnswerRemainingSeconds / MAX_TEXT_ANSWER_SECONDS) * 100)} />
              </Space>
            </Card>
          </Col>
        </Row>

        <Card
          className="interview-lobby-section-card"
          title="快速开始"
          extra={
            <Button type="link" onClick={() => setCreateModalOpen(true)}>
              自定义配置创建
            </Button>
          }
        >
          <Row gutter={[12, 12]}>
            {quickStartRoles.map((item) => (
              <Col xs={24} md={12} xl={6} key={item.key}>
                <Card className="interview-lobby-role-card" size="small">
                  <Space direction="vertical" size={8}>
                    <Space size={8}>
                      <div className="interview-lobby-icon-wrap soft"><item.icon size={16} /></div>
                      <Typography.Text strong>{item.title}</Typography.Text>
                    </Space>
                    <Typography.Text type="secondary">{item.subtitle}</Typography.Text>
                    <Button
                      className="interview-lobby-role-btn"
                      type="primary"
                      ghost
                      icon={<ArrowRight size={15} />}
                      onClick={() => {
                        setCreateModalOpen(true)
                        createForm.setFieldValue('job_role', item.key === 'java' ? 'java' : 'web')
                      }}
                    >
                      开始练习
                    </Button>
                  </Space>
                </Card>
              </Col>
            ))}
          </Row>
        </Card>

        <Row gutter={[16, 16]}>
          <Col xs={24} xl={15}>
            <Card
              className="interview-lobby-section-card"
              title="预约日历"
              extra={<Tag color={scheduleCount > 0 ? 'processing' : 'default'}>{`${scheduleCount} 条预约`}</Tag>}
            >
              <Calendar
                fullscreen={false}
                value={calendarValue}
                onPanelChange={(value) => setCalendarValue(value)}
                onSelect={(value) => setSelectedScheduleDate(value)}
                fullCellRender={calendarCellRender}
              />
            </Card>
          </Col>
          <Col xs={24} xl={9}>
            <Card
              className="interview-lobby-section-card"
              title={`${selectedDateLabel} 的安排`}
              extra={
                <Button
                  type="link"
                  onClick={() => {
                    setCreateModalOpen(true)
                    createForm.setFieldValue('schedule_mode', 'schedule')
                    createForm.setFieldValue('scheduled_start_at', `${selectedScheduleDate.format('YYYY-MM-DD')}T09:00`)
                  }}
                >
                  在当天新增预约
                </Button>
              }
            >
              {selectedScheduleItems.length === 0 ? (
                <Typography.Text type="secondary">这一天还没有预约面试，可以直接新建。</Typography.Text>
              ) : (
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  {selectedScheduleItems.map((item) => (
                    <Card key={item.interview_id} size="small" bodyStyle={{ padding: 14 }}>
                      <Space direction="vertical" size={8} style={{ width: '100%' }}>
                        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                          <Typography.Text strong>{item.session_name || '未命名面试'}</Typography.Text>
                          <Tag color={statusColorMap[item.status] || 'blue'}>{item.status}</Tag>
                        </Space>
                        <Space wrap size={8}>
                          <Tag color={roleColorMap[item.job_role] || 'blue'}>{`岗位：${item.job_role}`}</Tag>
                          <Tag color={difficultyColorMap[item.difficulty] || 'gold'}>{`难度：${item.difficulty}`}</Tag>
                          <Tag color={item.start_available ? 'green' : 'default'}>{item.start_available ? '已到开始时间' : '待开始'}</Tag>
                        </Space>
                        <Typography.Text type="secondary">{`预约时间：${formatScheduleDateTime(item.scheduled_start_at)}`}</Typography.Text>
                        <Typography.Text type="secondary">{`简历：${item.resume_file_name || item.resume_id}`}</Typography.Text>
                        {item.status === 'SCHEDULED' ? (
                          <Button
                            type="primary"
                            loading={startScheduleMutation.isPending && startingScheduleInterviewId === item.interview_id}
                            disabled={!item.start_available}
                            onClick={() => startScheduleMutation.mutate(item.interview_id)}
                          >
                            {item.start_available ? '开始面试' : '未到开始时间'}
                          </Button>
                        ) : item.status === 'PAUSED' ? (
                          <Button
                            type="primary"
                            loading={resumePausedMutation.isPending && resumingInterviewId === item.interview_id}
                            onClick={() => resumePausedMutation.mutate(item.interview_id)}
                          >
                            继续面试
                          </Button>
                        ) : (
                          <Button type="default" onClick={() => navigate(`/interview/${item.interview_id}`)}>
                            进入面试
                          </Button>
                        )}
                      </Space>
                    </Card>
                  ))}
                </Space>
              )}
            </Card>
          </Col>
        </Row>

        <Card className="interview-lobby-section-card" title="继续上次面试">
          {pausedQuery.isLoading ? (
            <Typography.Text type="secondary">正在加载暂停中的会话...</Typography.Text>
          ) : pausedItems.length === 0 ? (
            <Typography.Text type="secondary">暂无暂停中的面试，可点击“开始新面试”创建。</Typography.Text>
          ) : (
            <Row gutter={[12, 12]}>
              {pausedItems.map((row) => (
                <Col xs={24} lg={12} key={row.interview_id}>
                  <Card className="interview-lobby-resume-card" size="small">
                    <Space direction="vertical" size={10} style={{ width: '100%' }}>
                      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                        <Typography.Text strong>{row.session_name || '未命名面试'}</Typography.Text>
                        <Tag color="blue">{row.status}</Tag>
                      </Space>
                      <Space wrap size={8}>
                        <Tag color={roleColorMap[row.job_role] || 'blue'}>{`岗位：${row.job_role}`}</Tag>
                        <Tag color={difficultyColorMap[row.difficulty] || 'gold'}>{`难度：${row.difficulty}`}</Tag>
                        <Tooltip title="预览">
                          <Tag
                            color="purple"
                            className="interview-lobby-resume-preview-tag"
                            onClick={() =>
                              previewMutation.mutate({
                                resumeId: row.resume_id,
                                fileName: row.resume_file_name || `${row.resume_id}.pdf`,
                              })
                            }
                          >
                            {`简历：${row.resume_file_name || row.resume_id}`}
                          </Tag>
                        </Tooltip>
                      </Space>
                      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                        <Tag color={statusColorMap[row.status] || 'processing'}>{`状态：${row.status}`}</Tag>
                        <Typography.Text type="secondary">{`会话ID：${row.interview_id}`}</Typography.Text>
                      </Space>
                      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                        <Typography.Text type="secondary">{`开始时间：${formatDateTime(row.started_at)}`}</Typography.Text>
                      </Space>
                      <div className="interview-lobby-resume-action-row">
                        <Button
                          className="interview-lobby-resume-action-btn"
                          size="middle"
                          type="primary"
                          loading={resumePausedMutation.isPending && resumingInterviewId === row.interview_id}
                          onClick={() => resumePausedMutation.mutate(row.interview_id)}
                        >
                          继续面试
                        </Button>
                      </div>
                    </Space>
                  </Card>
                </Col>
              ))}
            </Row>
          )}
        </Card>

        <Card className="interview-lobby-health-summary">
          <Space style={{ width: '100%', justifyContent: 'space-between' }} wrap>
            <Space size={10}>
              <div className="interview-lobby-icon-wrap green">
                <Activity size={16} />
              </div>
              <Typography.Text strong>
                系统状态：{providerHealth?.overall === 'UP' ? '正常' : providerHealth?.overall === 'DEGRADED' ? '降级运行' : '异常'}
              </Typography.Text>
            </Space>
            <Button
              type="link"
              onClick={() => setHealthDetailsOpen((previous) => !previous)}
              icon={healthDetailsOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            >
              {healthDetailsOpen ? '隐藏详情' : '展开详情'}
            </Button>
          </Space>
          {healthDetailsOpen ? (
            <div style={{ marginTop: 12 }}>
              <ProviderHealthBanner health={providerHealth} />
            </div>
          ) : null}
        </Card>

        <Modal
          title="创建面试"
          open={createModalOpen}
          onCancel={() => setCreateModalOpen(false)}
          footer={null}
          destroyOnClose
          zIndex={1000}
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
              form={createForm}
              layout="vertical"
              initialValues={{
                job_role: 'java',
                difficulty: 'medium',
                input_mode: 'voice',
                output_mode: 'voice',
                schedule_mode: 'now',
                scheduled_start_at: '',
                voice_tone_id: '',
                session_name: '',
                question_types: ['project', 'technical', 'scenario'],
              }}
              onFinish={(values) => {
                if (!resumeId) {
                  message.warning('请先在弹窗中选择简历')
                  setResumePickerOpen(true)
                  return
                }
                if (values.schedule_mode === 'schedule' && !values.scheduled_start_at) {
                  message.warning('请选择预约开始时间')
                  return
                }
                const scheduledStartAt = values.schedule_mode === 'schedule' ? toScheduleIsoString(values.scheduled_start_at) : ''
                if (values.schedule_mode === 'schedule' && !scheduledStartAt) {
                  message.warning('预约开始时间格式不正确')
                  return
                }
                createMutation.mutate({
                  resume_id: resumeId,
                  job_role: createPositionMode === 'role' ? values.job_role : undefined,
                  jd_id: createPositionMode === 'jd' ? values.jd_id : undefined,
                  difficulty: values.difficulty,
                  input_mode: values.input_mode,
                  output_mode: values.output_mode,
                  voice_tone_id: values.voice_tone_id || undefined,
                  session_name: values.session_name,
                  question_types: questionTypeOrder.filter((item) => (values.question_types || []).includes(item)),
                  scheduled_start_at: scheduledStartAt || undefined,
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
              <Form.Item label="岗位信息模式">
                <Space>
                  <Typography.Text>岗位方向</Typography.Text>
                  <Switch
                    checked={createPositionMode === 'jd'}
                    checkedChildren="JD"
                    unCheckedChildren="方向"
                    onChange={(checked: boolean) => {
                      const mode: 'role' | 'jd' = checked ? 'jd' : 'role'
                      setCreatePositionMode(mode)
                      if (mode === 'role') {
                        createForm.setFieldValue('jd_id', '')
                        setPendingJdId('')
                        setCreateSelectedJdTitle('')
                      }
                    }}
                  />
                  <Typography.Text>岗位描述（JD）</Typography.Text>
                </Space>
              </Form.Item>
              {createPositionMode === 'role' ? (
                <Form.Item name="job_role" label="岗位方向" rules={[{ required: true, message: '请选择岗位方向' }]}>
                  <Select
                    onChange={(value: 'java' | 'web') => {
                      setCreateJobRole(value)
                    }}
                    options={[
                      { label: 'Java', value: 'java' },
                      { label: 'Web', value: 'web' },
                    ]}
                  />
                </Form.Item>
              ) : (
                <Form.Item name="jd_id" label="岗位描述（JD）" rules={[{ required: true, whitespace: true, message: '请选择岗位描述' }]}>
                  <Space>
                    {createForm.getFieldValue('jd_id') ? (
                      <Tag color="gold">{createSelectedJdTitle || createForm.getFieldValue('jd_id')}</Tag>
                    ) : (
                      <Tag color="red">未选择 JD</Tag>
                    )}
                    <Button
                      onClick={() => setJdPickerOpen(true)}
                    >
                      选择 JD
                    </Button>
                  </Space>
                </Form.Item>
              )}
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
              <Form.Item name="schedule_mode" label="开始方式">
                <Radio.Group
                  options={[
                    { label: '立即开始', value: 'now' },
                    { label: '预约开始', value: 'schedule' },
                  ]}
                />
              </Form.Item>
              <Form.Item shouldUpdate noStyle>
                {() =>
                  createForm.getFieldValue('schedule_mode') === 'schedule' ? (
                    <Form.Item
                      name="scheduled_start_at"
                      label="预约开始时间"
                      rules={[{ required: true, message: '请选择预约开始时间' }]}
                      extra="仅支持预约未来时间，到点后才可开始面试。"
                    >
                      <Input type="datetime-local" min={dayjs().format('YYYY-MM-DDTHH:mm')} />
                    </Form.Item>
                  ) : null
                }
              </Form.Item>
              <Form.Item name="output_mode" label="输出模式">
                <Radio.Group
                  options={[
                    { label: '文本', value: 'text' },
                    { label: '语音', value: 'voice' },
                  ]}
                />
              </Form.Item>
              <Form.Item shouldUpdate={(prev, next) => prev.output_mode !== next.output_mode} noStyle>
                {({ getFieldValue }) =>
                  getFieldValue('output_mode') === 'voice' ? (
                    <Form.Item name="voice_tone_id" label="面试官语气">
                      <Select
                        loading={toneQuery.isLoading}
                        allowClear
                        placeholder="请选择语气（不选则使用默认）"
                        options={(toneQuery.data?.items || []).map((item) => ({
                          label: `${item.tone_name}（x${item.speed.toFixed(2)}）`,
                          value: item.tone_id,
                        }))}
                      />
                    </Form.Item>
                  ) : null
                }
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
          title="选择岗位描述（JD）"
          open={jdPickerOpen}
          onCancel={() => setJdPickerOpen(false)}
          onOk={() => {
            createForm.setFieldValue('jd_id', pendingJdId)
            const item = (jdQuery.data?.items || []).find((row) => row.jd_id === pendingJdId)
            setCreateSelectedJdTitle(item?.title || '')
            setJdPickerOpen(false)
            message.success('已绑定 JD')
          }}
          okText="确认绑定"
          cancelText="取消"
          width="min(1100px, 92vw)"
          styles={{ body: { height: 640, overflow: 'hidden' } }}
          zIndex={1100}
        >
          <Space wrap style={{ width: '100%', marginBottom: 12 }}>
            <Input
              placeholder="按 job_role 搜索，例如：java / web / 后端开发"
              value={jdFilterRole}
              onChange={(event) => setJdFilterRole(event.target.value)}
              style={{ width: 320 }}
            />
            <Input
              placeholder="按标题关键词搜索"
              value={jdFilterTitle}
              onChange={(event) => setJdFilterTitle(event.target.value)}
              style={{ width: 320 }}
            />
            <Button onClick={() => void jdQuery.refetch()}>搜索</Button>
            <Button
              onClick={() => {
                setJdFilterRole('')
                setJdFilterTitle('')
              }}
            >
              清空筛选
            </Button>
          </Space>
          <Table
            rowKey="jd_id"
            loading={jdQuery.isLoading}
            dataSource={jdQuery.data?.items || []}
            pagination={false}
            scroll={{ y: 470 }}
            onRow={(record) => ({
              onClick: () => setPendingJdId(record.jd_id),
            })}
            rowSelection={{
              type: 'radio',
              selectedRowKeys: pendingJdId ? [pendingJdId] : [],
              onChange: (keys) => setPendingJdId(String(keys[0] || '')),
            }}
            columns={[
              { title: '标题', dataIndex: 'title' },
              {
                title: '公司',
                dataIndex: 'company_name',
                render: (value: string) => value || '-',
              },
              {
                title: '来源',
                dataIndex: 'source_type',
                render: (value: string) => (value === 'SYSTEM_PRESET' ? '系统预置' : '我的上传'),
              },
              { title: '方向', dataIndex: 'job_role' },
              {
                title: '内容摘要',
                dataIndex: 'content_text',
                render: (value: string) => (
                  <Typography.Paragraph style={{ marginBottom: 0 }} ellipsis={{ rows: 2, expandable: false }}>
                    {value || '-'}
                  </Typography.Paragraph>
                ),
              },
              { title: '更新时间', dataIndex: 'updated_at' },
            ]}
            locale={{ emptyText: '暂无岗位描述，请先去岗位管理页维护。' }}
          />
        </Modal>
        <Modal
          title={`简历预览 - ${previewTitle}`}
          open={previewOpen}
          onCancel={() => setPreviewOpen(false)}
          footer={null}
          width="min(900px, 92vw)"
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
        gridTemplateColumns: isDesktopWide
          ? historyCollapsed
            ? 'minmax(220px, 1fr) minmax(0, 3fr)'
            : 'minmax(220px, 2fr) minmax(0, 4fr) minmax(220px, 2fr)'
          : isTabletUp
            ? 'minmax(220px, 1fr) minmax(0, 2fr)'
            : 'minmax(0, 1fr)',
        gap: 16,
        width: '100%',
        height: '100%',
        minHeight: 0,
        transition: 'grid-template-columns 0.2s ease',
        boxSizing: 'border-box',
        overflow: 'hidden',
      }}
    >
      <Space direction="vertical" size={16} style={{ width: '100%', minWidth: 0, height: '100%', overflowY: 'auto', overflowX: 'hidden', paddingRight: 4 }}>
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
            <div style={{ border: '1px solid #f0f0f0', borderRadius: 10, padding: 12, background: '#fafcff' }}>
              <Space align="start" size={10} style={{ width: '100%' }}>
                <FlagOutlined style={{ color: '#7c6cff', marginTop: 2 }} />
                <div>
                  <Typography.Text type="secondary">面试难度</Typography.Text>
                  <div>
                    {interviewStatusQuery.data?.difficulty === 'easy'
                      ? '简单'
                      : interviewStatusQuery.data?.difficulty === 'hard'
                        ? '困难'
                        : '中等'}
                  </div>
                </div>
              </Space>
            </div>
          </Space>
        </Card>
        <ProviderHealthBanner health={providerHealth} />
      </Space>

      <div
        style={{
          display: 'grid',
          gridTemplateRows: isTabletUp ? 'minmax(0, 3fr) minmax(0, 2fr)' : 'auto auto',
          gap: 16,
          minHeight: isTabletUp ? 560 : undefined,
          height: '100%',
          minWidth: 0,
          overflowY: 'auto',
          overflowX: 'hidden',
          paddingRight: 4,
        }}
      >
        <Card
          title="问题区"
          style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
          bodyStyle={{ flex: 1, minHeight: 0, overflowY: 'auto', overflowX: 'hidden' }}
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
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <Typography.Paragraph style={{ marginBottom: 0 }}>
                  {!currentQuestion
                    ? '等待题目生成...'
                    : questionAudioPlaying
                      ? '正在播放语音题目'
                      : questionAudioEnded
                        ? '语音播放结束，可重播题目'
                        : '语音题目已就绪'}
                </Typography.Paragraph>
                {questionAudioEnded ? (
                  <Tooltip title="重播题目语音">
                    <Button
                      shape="circle"
                      icon={<RedoOutlined />}
                      onClick={() => {
                        if (!autoPlayAudioRef.current) {
                          return
                        }
                        autoPlayAudioRef.current.currentTime = 0
                        setQuestionAudioEnded(false)
                        void autoPlayAudioRef.current.play().catch(() => {
                          message.warning('重播失败，请重试')
                        })
                      }}
                    />
                  </Tooltip>
                ) : null}
              </div>
              {ttsAudioUrl ? (
                <>
                  <audio
                    ref={autoPlayAudioRef}
                    src={ttsAudioUrl}
                    style={{ display: 'none' }}
                    onPlay={() => {
                      setQuestionAudioPlaying(true)
                      setQuestionAudioEnded(false)
                    }}
                    onPause={() => setQuestionAudioPlaying(false)}
                    onAbort={() => setQuestionAudioPlaying(false)}
                    onEmptied={() => setQuestionAudioPlaying(false)}
                    onError={() => setQuestionAudioPlaying(false)}
                    onEnded={handleQuestionAudioEnded}
                  >
                    您的浏览器不支持音频播放。
                  </audio>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'flex-end',
                      justifyContent: 'center',
                      gap: 8,
                      height: 96,
                      padding: '12px 16px',
                      borderRadius: 10,
                      background: '#f5f8ff',
                      border: '1px solid #dce7ff',
                    }}
                  >
                    {audioBarSeedsRef.current.map((seed, index) => {
                      const active = questionAudioPlaying
                      const barHeight = active ? seed.base : Math.max(18, Math.floor(seed.base * 0.45))
                      return (
                        <div
                          key={index}
                          style={{
                            width: 10,
                            height: barHeight,
                            borderRadius: 4,
                            background: active ? '#4f7cff' : '#9eb7ff',
                            transformOrigin: 'bottom center',
                            animation: active ? `question-voice-bar-${seed.animationType} ${seed.duration}ms ease-in-out infinite` : 'none',
                            animationDelay: `${seed.delay}ms`,
                          }}
                        />
                      )
                    })}
                  </div>
                  <Typography.Paragraph
                    style={{
                      marginBottom: 0,
                      minHeight: 72,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      background: '#fafafa',
                      border: '1px dashed #e0e0e0',
                      borderRadius: 8,
                      padding: 10,
                    }}
                  >
                    {displayedQuestionText || '...'}
                  </Typography.Paragraph>
                  <style>{`
                    @keyframes question-voice-bar-0 { 0%, 100% { transform: scaleY(0.55);} 50% { transform: scaleY(1.25);} }
                    @keyframes question-voice-bar-1 { 0%, 100% { transform: scaleY(0.7);} 50% { transform: scaleY(1.35);} }
                    @keyframes question-voice-bar-2 { 0%, 100% { transform: scaleY(0.5);} 50% { transform: scaleY(1.1);} }
                    @keyframes question-voice-bar-3 { 0%, 100% { transform: scaleY(0.65);} 50% { transform: scaleY(1.3);} }
                  `}</style>
                </>
              ) : (
                <Typography.Text type="secondary">当前题目语音暂不可用，可先参考文本作答。</Typography.Text>
              )}
            </Space>
          ) : (
            <Typography.Paragraph style={{ marginBottom: 0 }}>{currentQuestion || '等待题目生成...'}</Typography.Paragraph>
          )}
        </Card>

        <Card title="回答区" style={{ height: '100%', display: 'flex', flexDirection: 'column' }} bodyStyle={{ flex: 1, minHeight: 0, overflowY: 'auto', overflowX: 'hidden' }}>
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
                    ? `录音中，点击结束回答 ${formatDuration(recordingRemainingSeconds)}`
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
        <div style={{ minWidth: 0, height: '100%', minHeight: 0, overflow: 'hidden' }}>
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
        width="min(900px, 92vw)"
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
