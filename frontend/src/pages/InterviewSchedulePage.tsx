import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Card, Checkbox, Descriptions, Form, Input, List, Modal, Radio, Select, Space, Tag, Typography, message } from 'antd'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import {
  cancelInterviewSchedule,
  createInterviewSchedule,
  downloadInterviewScheduleCalendar,
  fetchInterviewScheduleDetail,
  fetchInterviewSchedules,
  fetchJds,
  fetchResumes,
  fetchVoiceToneProfiles,
  startInterviewSchedule,
} from '../api/interview'
import { parseApiError } from '../api/client'
import { useInterviewStore } from '../stores/interviewStore'
import { buildCalendarDays, endOfMonth, groupSchedulesByDate, isSameMonth, startOfMonth, toDateKey } from '../utils/scheduleCalendar'

// 面试预约页负责“创建、查看、取消、开始”四个动作：
// 1. 月历视图按日期组织预约，列表/详情用同一份查询数据驱动。
// 2. 创建预约前需要选择简历、岗位/JD、难度、输入输出模式和时长。
// 3. ready 状态的预约可直接开始，成功后写入 interviewStore 并跳转面试页。
// 4. 取消和开始都需要刷新列表，确保日历状态和详情弹窗一致。
// 5. 日历下载链接来自后端，前端只负责触发下载。

/** 格式化日期时间。 */
function formatDateTime(value?: string): string {
  if (!value) return '--'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString('zh-CN', { hour12: false })
}

/** 将时间转换为 datetime-local 可用值。 */
function toDatetimeLocalValue(date: Date): string {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 16)
}

/** 根据日期键构造默认晚间预约时间。 */
function buildEveningDatetimeValue(dateKey: string): string {
  return `${dateKey}T20:00`
}

/** 判断默认晚间预约时间是否已经过去。 */
function isPastEveningDatetime(dateKey: string): boolean {
  const scheduled = new Date(`${buildEveningDatetimeValue(dateKey)}:00`)
  return scheduled.getTime() < Date.now()
}

/** 格式化月份标题。 */
function formatMonthLabel(value: Date): string {
  return `${value.getFullYear()} 年 ${value.getMonth() + 1} 月`
}

/** 格式化紧凑日期。 */
function formatCompactDate(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })
}

/** 判断日期键是否早于今天。 */
function isPastDateKey(dateKey: string): boolean {
  const target = new Date(`${dateKey}T00:00:00`)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return target.getTime() < today.getTime()
}

/** 构造日历日期按钮的无障碍标签。 */
function buildCalendarDayAriaLabel(dateKey: string, options: { isCurrentMonth: boolean; isToday: boolean; scheduleCount: number }): string {
  const { isCurrentMonth, isToday, scheduleCount } = options
  const monthText = isCurrentMonth ? '本月日期' : '非本月日期'
  const todayText = isToday ? ' 今天' : ''
  const scheduleText = scheduleCount > 0 ? ` ${scheduleCount} 场预约` : ' 无预约'
  return `${dateKey} ${monthText}${todayText}${scheduleText}`
}

/** 打开外部日历链接。 */
function openExternalUrl(url: string): void {
  window.open(url, '_blank', 'noopener,noreferrer')
}

/** 获取状态标签颜色。 */
function getScheduleStatusColor(status: string): string {
  const colorMap: Record<string, string> = {
    scheduled: 'blue',
    ready: 'green',
    in_progress: 'gold',
    completed: 'default',
    missed: 'red',
    cancelled: 'default',
  }
  return colorMap[status] || 'default'
}

/** 获取状态文案。 */
function getScheduleStatusText(status: string): string {
  const textMap: Record<string, string> = {
    scheduled: '已预约',
    ready: '可进入',
    in_progress: '进行中',
    completed: '已完成',
    missed: '已错过',
    cancelled: '已取消',
  }
  return textMap[status] || status
}

/** 获取状态强调色。 */
function getScheduleStatusAccent(status: string): string {
  const colorMap: Record<string, string> = {
    scheduled: '#357ABD',
    ready: '#4A9BE8',
    in_progress: '#d97706',
    completed: '#6b7280',
    missed: '#dc2626',
    cancelled: '#9ca3af',
  }
  return colorMap[status] || '#357ABD'
}

/** 面试预约页面。 */
export function InterviewSchedulePage() {
  const questionTypeOrder: Array<'project' | 'technical' | 'scenario'> = ['project', 'technical', 'scenario']
  const weekLabels = ['一', '二', '三', '四', '五', '六', '日']
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const resumeId = useInterviewStore((state) => state.resumeId)
  const setResumeId = useInterviewStore((state) => state.setResumeId)
  const [positionMode, setPositionMode] = useState<'role' | 'jd'>('role')
  const [jobRole, setJobRole] = useState<'java' | 'web'>('java')
  const [selectedScheduleId, setSelectedScheduleId] = useState('')
  const [detailModalOpen, setDetailModalOpen] = useState(false)
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [selectedDateKey, setSelectedDateKey] = useState(toDateKey(new Date()))
  const [currentMonth, setCurrentMonth] = useState(startOfMonth(new Date()))
  const [form] = Form.useForm()

  const visibleMonthRange = useMemo(() => {
    const start = startOfMonth(currentMonth)
    const end = endOfMonth(currentMonth)
    return {
      dateFrom: `${toDateKey(start)}T00:00:00`,
      dateTo: `${toDateKey(end)}T23:59:59`,
    }
  }, [currentMonth])

  useEffect(() => {
    const suggested = new Date(Date.now() + 30 * 60 * 1000)
    form.setFieldsValue({
      title: '',
      scheduled_start_at: toDatetimeLocalValue(suggested),
      duration_minutes: 45,
      job_role: 'java',
      difficulty: 'medium',
      input_mode: 'voice',
      output_mode: 'voice',
      session_name: '',
      question_types: ['project', 'technical', 'scenario'],
      voice_tone_id: '',
      jd_id: '',
    })
  }, [form])

  const resumeQuery = useQuery({
    queryKey: ['resumes', 'schedule-page'],
    queryFn: () => fetchResumes({ page: 1, page_size: 50 }),
  })

  const jdQuery = useQuery({
    queryKey: ['jds', 'schedule-page', jobRole],
    queryFn: () => fetchJds({ job_role: jobRole }),
  })

  const toneQuery = useQuery({
    queryKey: ['voice-tone-profiles', 'schedule-page'],
    queryFn: fetchVoiceToneProfiles,
  })

  const scheduleListQuery = useQuery({
    queryKey: ['interview-schedules', visibleMonthRange.dateFrom, visibleMonthRange.dateTo],
    queryFn: () =>
      fetchInterviewSchedules({
        page: 1,
        page_size: 50,
        date_from: visibleMonthRange.dateFrom,
        date_to: visibleMonthRange.dateTo,
      }),
  })

  const scheduleDetailQuery = useQuery({
    queryKey: ['interview-schedule-detail', selectedScheduleId],
    queryFn: () => fetchInterviewScheduleDetail(selectedScheduleId),
    enabled: detailModalOpen && !!selectedScheduleId,
  })

  const selectedResumeName = useMemo(() => {
    const items = resumeQuery.data?.items ?? []
    return items.find((item) => item.resume_id === resumeId)?.file_name || ''
  }, [resumeId, resumeQuery.data])

  const schedulesByDate = useMemo(() => {
    return groupSchedulesByDate(scheduleListQuery.data?.items ?? [])
  }, [scheduleListQuery.data])

  const monthDays = useMemo(() => buildCalendarDays(currentMonth), [currentMonth])
  const selectedDateSchedules = schedulesByDate.get(selectedDateKey) ?? []
  const todayKey = toDateKey(new Date())
  const selectedDateIsPast = isPastDateKey(selectedDateKey)
  const selectedDateDefaultTimePassed = isPastEveningDatetime(selectedDateKey)
  const scheduleItems = useMemo(() => scheduleListQuery.data?.items ?? [], [scheduleListQuery.data?.items])
  const statCards = useMemo(
    () => [
      {
        key: 'all',
        label: '本月预约',
        value: scheduleItems.length,
        note: '已写入当前月历的场次',
      },
      {
        key: 'ready',
        label: '待开始',
        value: scheduleItems.filter((item) => item.status === 'ready').length,
        note: '到点后可直接进入面试',
      },
      {
        key: 'progress',
        label: '进行中',
        value: scheduleItems.filter((item) => item.status === 'in_progress').length,
        note: '还可以随时回到面试现场',
      },
      {
        key: 'days',
        label: '活跃日期',
        value: schedulesByDate.size,
        note: '这个月实际排了多少天练习',
      },
    ],
    [scheduleItems, schedulesByDate],
  )
  const nextReadySchedule = scheduleItems.find((item) => item.status === 'ready')

  useEffect(() => {
    const firstScheduleDate = (scheduleListQuery.data?.items ?? [])[0]?.scheduled_start_at
    const selectedDate = new Date(`${selectedDateKey}T00:00:00`)

    // 用户已经手动选中了当前月内的某一天时，不要再被自动纠正逻辑覆盖。
    if (isSameMonth(selectedDate, currentMonth)) {
      return
    }

    if (firstScheduleDate && isSameMonth(new Date(firstScheduleDate), currentMonth)) {
      setSelectedDateKey(toDateKey(firstScheduleDate))
      return
    }
    if (isSameMonth(new Date(), currentMonth)) {
      setSelectedDateKey(todayKey)
      return
    }
    setSelectedDateKey(toDateKey(currentMonth))
  }, [currentMonth, scheduleListQuery.data, schedulesByDate, selectedDateKey, todayKey])

  const createMutation = useMutation({
    mutationFn: createInterviewSchedule,
    onSuccess: async (data) => {
      message.success('预约创建成功')
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['interview-schedules'] }),
        queryClient.invalidateQueries({ queryKey: ['interview-schedule-detail', data.schedule_id] }),
      ])
      form.setFieldValue('title', '')
      form.setFieldValue('session_name', '')
      setCreateModalOpen(false)
      setSelectedScheduleId(data.schedule_id)
      setDetailModalOpen(true)
    },
    onError: (error) => {
      message.error(parseApiError(error).message)
    },
  })

  const cancelMutation = useMutation({
    mutationFn: (scheduleId: string) => cancelInterviewSchedule(scheduleId),
    onSuccess: async () => {
      message.success('预约已取消')
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['interview-schedules'] }),
        queryClient.invalidateQueries({ queryKey: ['interview-schedule-detail', selectedScheduleId] }),
      ])
    },
    onError: (error) => {
      message.error(parseApiError(error).message)
    },
  })

  const startMutation = useMutation({
    mutationFn: (scheduleId: string) => startInterviewSchedule(scheduleId),
    onSuccess: async (data) => {
      message.success('开始预约面试')
      await queryClient.invalidateQueries({ queryKey: ['interview-schedules'] })
      navigate(`/interview/${data.interview_id}`)
    },
    onError: (error) => {
      message.error(parseApiError(error).message)
    },
  })

  /** 下载 .ics 文件。 */
  const handleCalendarDownload = async (scheduleId: string) => {
    try {
      const blob = await downloadInterviewScheduleCalendar(scheduleId)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `${scheduleId}.ics`
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (error) {
      message.error(parseApiError(error).message)
    }
  }

  /** 打开预约详情弹窗。 */
  const openScheduleDetailModal = (scheduleId: string) => {
    setSelectedScheduleId(scheduleId)
    setDetailModalOpen(true)
  }

  /** 打开创建预约弹窗，并按需预填预约时间。 */
  const openCreateScheduleModal = (dateKey?: string) => {
    if (dateKey && isPastEveningDatetime(dateKey)) {
      message.warning('这个时间已经过去了，请选择今天之后仍可预约的时间')
      return
    }
    if (dateKey) {
      form.setFieldValue('scheduled_start_at', buildEveningDatetimeValue(dateKey))
    }
    setCreateModalOpen(true)
  }

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card
        variant="borderless"
        styles={{
          body: {
            padding: 28,
            borderRadius: 24,
            background: 'linear-gradient(135deg, #0d2b4a 0%, #153e68 40%, #edf4fb 40%, #f8fafd 100%)',
          },
        }}
      >
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 1.3fr) minmax(280px, 0.7fr)',
            gap: 20,
            alignItems: 'stretch',
          }}
        >
          <Space direction="vertical" size={14} style={{ width: '100%' }}>
            <Tag color="cyan" style={{ width: 'fit-content', marginInlineEnd: 0 }}>
              面试练习日程工作台
            </Tag>
            <Typography.Title level={2} style={{ margin: 0, color: '#ffffff' }}>
              模拟面试预约
            </Typography.Title>
            <Typography.Paragraph style={{ margin: 0, color: 'rgba(255,255,255,0.78)', maxWidth: 560 }}>
              把练习节奏先定下来，到点后直接回到面试现场。这个页面会帮你看清本月排期、待开始场次，以及哪一天最适合补一场练习。
            </Typography.Paragraph>
            <Space wrap>
              <Button type="primary" size="large" onClick={() => openCreateScheduleModal()}>
                创建单次预约
              </Button>
              <Button size="large" onClick={() => navigate('/interview')}>
                立即开始面试
              </Button>
              <Button size="large" onClick={() => navigate('/resumes')}>
                去管理简历
              </Button>
            </Space>
          </Space>

          <Card
            variant="borderless"
            style={{ borderRadius: 20, background: 'rgba(255,255,255,0.92)', backdropFilter: 'blur(12px)', boxShadow: '0 12px 36px rgba(0,0,0,0.10)' }}
            styles={{ body: { padding: 22 } }}
          >
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <Typography.Text strong>最近需要你关注</Typography.Text>
              {nextReadySchedule ? (
                <>
                  <Typography.Title level={4} style={{ margin: 0 }}>
                    {nextReadySchedule.title || nextReadySchedule.resume_file_name || '待开始面试'}
                  </Typography.Title>
                  <Typography.Text type="secondary">{formatDateTime(nextReadySchedule.scheduled_start_at)}</Typography.Text>
                  <Tag color="green" style={{ width: 'fit-content', marginInlineEnd: 0 }}>
                    可直接进入
                  </Tag>
                  <Button type="primary" block onClick={() => startMutation.mutate(nextReadySchedule.schedule_id)} loading={startMutation.isPending}>
                    开始这场面试
                  </Button>
                </>
              ) : (
                <>
                  <Typography.Text type="secondary">当前没有到点可直接开始的预约，但你的排期已经会在下面的月历里完整展示。</Typography.Text>
                  <Button block onClick={() => navigate('/overview')}>
                    返回首页概览
                  </Button>
                </>
              )}
            </Space>
          </Card>
        </div>
      </Card>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: 14,
        }}
      >
        {statCards.map((item, index) => (
          <Card
            key={item.key}
            variant="borderless"
            style={{
              borderRadius: 18,
              background: index === 0 ? 'linear-gradient(180deg, #f0f4fc 0%, #ffffff 100%)' : '#ffffff',
              boxShadow: '0 1px 0 rgba(0,0,0,0.04), 0 8px 24px rgba(0,0,0,0.04)',
            }}
            styles={{ body: { padding: '20px 22px' } }}
          >
            <Space direction="vertical" size={6}>
              <Typography.Text type="secondary">{item.label}</Typography.Text>
              <Typography.Title level={2} style={{ margin: 0 }}>
                {item.value}
              </Typography.Title>
              <Typography.Text type="secondary">{item.note}</Typography.Text>
            </Space>
          </Card>
        ))}
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1.6fr) minmax(300px, 0.8fr)',
          gap: 16,
          alignItems: 'start',
        }}
      >
        <Card
          variant="borderless"
          style={{ borderRadius: 20, boxShadow: '0 1px 0 rgba(0,0,0,0.04), 0 12px 32px rgba(0,0,0,0.05)' }}
          styles={{ body: { padding: 24 } }}
          title={<Typography.Title level={4} style={{ margin: 0, fontSize: 18, fontWeight: 600, letterSpacing: '-0.01em' }}>我的日程表</Typography.Title>}
          extra={
            <Space size={8}>
              <Button size="small" onClick={() => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1))}>上个月</Button>
              <Typography.Text strong style={{ minWidth: 100, textAlign: 'center', fontSize: 14 }}>{formatMonthLabel(currentMonth)}</Typography.Text>
              <Button size="small" onClick={() => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1))}>下个月</Button>
            </Space>
          }
        >
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Space style={{ justifyContent: 'space-between', width: '100%' }}>
              <Space size={16}>
                <Space size={4}><span style={{ width: 8, height: 8, borderRadius: 4, background: '#4A9BE8', display: 'inline-block' }} /><Typography.Text type="secondary" style={{ fontSize: 12 }}>已预约</Typography.Text></Space>
                <Space size={4}><span style={{ width: 8, height: 8, borderRadius: 4, background: '#22c55e', display: 'inline-block' }} /><Typography.Text type="secondary" style={{ fontSize: 12 }}>可进入</Typography.Text></Space>
                <Space size={4}><span style={{ width: 8, height: 8, borderRadius: 4, background: '#f59e0b', display: 'inline-block' }} /><Typography.Text type="secondary" style={{ fontSize: 12 }}>进行中</Typography.Text></Space>
              </Space>
              <Button type="link" size="small" style={{ paddingInline: 0, fontSize: 13 }} onClick={() => setCurrentMonth(startOfMonth(new Date()))}>
                回到本月
              </Button>
            </Space>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, minmax(0, 1fr))', gap: 8 }}>
              {weekLabels.map((label) => (
                <div key={label} style={{ textAlign: 'center', fontWeight: 600, color: '#86868b', fontSize: 12, paddingBlock: 6, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                  {label}
                </div>
              ))}
              {monthDays.map((day) => {
                const key = toDateKey(day)
                const items = schedulesByDate.get(key) ?? []
                const isCurrentMonth = isSameMonth(day, currentMonth)
                const isSelected = key === selectedDateKey
                const isToday = key === todayKey
                return (
                  <button
                    key={key}
                    type="button"
                    aria-label={buildCalendarDayAriaLabel(key, { isCurrentMonth, isToday, scheduleCount: items.length })}
                    onClick={() => setSelectedDateKey(key)}
                    style={{
                      minHeight: 110,
                      borderRadius: 14,
                      border: isSelected
                        ? '2px solid #0071e3'
                        : isToday && !isSelected
                          ? '2px solid #86868b'
                          : '1px solid transparent',
                      background: isSelected
                        ? '#ffffff'
                        : isCurrentMonth
                          ? 'rgba(255,255,255,0.55)'
                          : 'rgba(248,250,252,0.4)',
                      padding: 10,
                      textAlign: 'left',
                      cursor: isCurrentMonth ? 'pointer' : 'default',
                      boxShadow: isSelected ? '0 0 0 3px rgba(0,113,227,0.12), 0 8px 24px rgba(0,0,0,0.06)' : 'none',
                      transition: 'box-shadow 0.2s ease, border-color 0.2s ease',
                      opacity: isCurrentMonth ? 1 : 0.45,
                    }}
                  >
                    <Space direction="vertical" size={6} style={{ width: '100%' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Typography.Text strong style={{
                          fontSize: 14,
                          fontWeight: isToday ? 700 : 600,
                          width: 24,
                          height: 24,
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          borderRadius: 12,
                          background: isToday ? '#1d1d1f' : 'transparent',
                          color: isToday ? '#ffffff' : isCurrentMonth ? '#1d1d1f' : '#86868b',
                        }}>
                          {day.getDate()}
                        </Typography.Text>
                        {items.length > 0 ? (
                          <div style={{ display: 'flex', gap: 3 }}>
                            {items.slice(0, 3).map((it, i) => (
                              <span key={i} style={{ width: 6, height: 6, borderRadius: 3, background: getScheduleStatusAccent(it.status), display: 'inline-block' }} />
                            ))}
                          </div>
                        ) : null}
                      </div>
                      {items.length > 0 ? (
                        <Space direction="vertical" size={4} style={{ width: '100%' }}>
                          {items.slice(0, 2).map((item) => (
                            <div
                              key={item.schedule_id}
                              style={{
                                borderRadius: 8,
                                background: 'rgba(0,0,0,0.03)',
                                padding: '4px 8px',
                                fontSize: 11,
                                color: '#424245',
                                lineHeight: 1.3,
                                overflow: 'hidden',
                                whiteSpace: 'nowrap',
                                textOverflow: 'ellipsis',
                              }}
                            >
                              {new Date(item.scheduled_start_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })} {item.title || item.resume_file_name || ''}
                            </div>
                          ))}
                          {items.length > 2 ? (
                            <Typography.Text style={{ fontSize: 11, color: '#86868b' }}>{`+${items.length - 2} 场`}</Typography.Text>
                          ) : null}
                        </Space>
                      ) : isCurrentMonth ? (
                        <Typography.Text style={{ fontSize: 11, color: '#d2d2d7' }}>可预约</Typography.Text>
                      ) : null}
                    </Space>
                  </button>
                )
              })}
            </div>
          </Space>
        </Card>

        <Card
          variant="borderless"
          style={{ borderRadius: 20, boxShadow: '0 1px 0 rgba(0,0,0,0.04), 0 12px 32px rgba(0,0,0,0.05)', position: 'sticky', top: 16 }}
          styles={{ body: { padding: 22 } }}
        >
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <div>
              <Typography.Text type="secondary">所选日期</Typography.Text>
              <Typography.Title level={4} style={{ margin: '6px 0 0' }}>
                {`${selectedDateKey} 的预约`}
              </Typography.Title>
            </div>

            {scheduleListQuery.isLoading ? (
              <Typography.Text type="secondary">日程加载中...</Typography.Text>
            ) : selectedDateSchedules.length > 0 ? (
              <List
                dataSource={selectedDateSchedules}
                split={false}
                renderItem={(item) => (
                  <List.Item style={{ paddingInline: 0, paddingBlock: 0, marginBottom: 12 }}>
                    <Card
                      size="small"
                      variant="borderless"
                      style={{
                        width: '100%',
                        borderRadius: 14,
                        background: '#ffffff',
                        border: '1px solid rgba(0,0,0,0.05)',
                        boxShadow: '0 2px 8px rgba(0,0,0,0.03)',
                      }}
                      styles={{ body: { padding: 14 } }}
                    >
                      <Space direction="vertical" size={10} style={{ width: '100%' }}>
                        <Space wrap style={{ justifyContent: 'space-between', width: '100%' }}>
                          <Typography.Text strong>{item.title || item.resume_file_name || item.schedule_id}</Typography.Text>
                          <Tag color={getScheduleStatusColor(item.status)} style={{ marginInlineEnd: 0 }}>
                            {getScheduleStatusText(item.status)}
                          </Tag>
                        </Space>
                        <Typography.Text type="secondary">{formatCompactDate(item.scheduled_start_at)}</Typography.Text>
                        <Space wrap>
                          <Tag style={{ marginInlineEnd: 0 }}>{`${item.duration_minutes} 分钟`}</Tag>
                          <Tag style={{ marginInlineEnd: 0 }}>{item.job_role || '--'}</Tag>
                          <Tag style={{ marginInlineEnd: 0 }}>{item.difficulty}</Tag>
                        </Space>
                        <Space wrap>
                          <Button size="small" onClick={() => openScheduleDetailModal(item.schedule_id)}>
                            查看详情
                          </Button>
                          {item.status === 'ready' ? (
                            <Button size="small" type="primary" loading={startMutation.isPending} onClick={() => startMutation.mutate(item.schedule_id)}>
                              开始面试
                            </Button>
                          ) : null}
                          {item.status === 'in_progress' && item.interview_id ? (
                            <Button size="small" type="primary" onClick={() => navigate(`/interview/${item.interview_id}`)}>
                              继续面试
                            </Button>
                          ) : null}
                        </Space>
                      </Space>
                    </Card>
                  </List.Item>
                )}
              />
            ) : (
              <Card
                variant="borderless"
                style={{
                  borderRadius: 14,
                  background: '#fafafa',
                  border: '1px dashed #d2d2d7',
                }}
                styles={{ body: { padding: 20 } }}
              >
                <Space direction="vertical" size={10} style={{ width: '100%' }}>
                  <Typography.Text strong>这一天还没有预约</Typography.Text>
                  <Typography.Text type="secondary">
                    {selectedDateDefaultTimePassed
                      ? selectedDateIsPast
                        ? '这个日期已经过去了，不能再新建预约。你可以切换到今天或之后的日期继续安排练习。'
                        : '今天默认的晚间预约时间已经过去了。你可以改约到之后的日期，或直接使用顶部按钮重新选择时间。'
                      : '如果你想把练习频率稳定下来，可以先约一场 20 或 45 分钟的模拟面试。'}
                  </Typography.Text>
                  {!selectedDateDefaultTimePassed ? (
                    <Button type="primary" onClick={() => openCreateScheduleModal(selectedDateKey)}>
                      为这一天新建预约
                    </Button>
                  ) : null}
                </Space>
              </Card>
            )}

            <Card
              size="small"
              variant="borderless"
              style={{ borderRadius: 14, background: '#1d1d1f' }}
              styles={{ body: { padding: 16 } }}
            >
              <Space direction="vertical" size={4}>
                <Typography.Text style={{ color: '#86868b', fontSize: 12, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase' }}>使用建议</Typography.Text>
                <Typography.Text style={{ color: '#d2d2d7', fontSize: 13, lineHeight: 1.6 }}>把高压一点的正式模拟，尽量排在精力更好的时段。把 20 分钟短练习塞进工作日晚上，通常更容易坚持。</Typography.Text>
              </Space>
            </Card>
          </Space>
        </Card>
      </div>

      <Modal title="预约详情" open={detailModalOpen} onCancel={() => setDetailModalOpen(false)} footer={null} width={640} destroyOnHidden>
        {scheduleDetailQuery.data ? (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="标题">{scheduleDetailQuery.data.title || '--'}</Descriptions.Item>
              <Descriptions.Item label="预约时间">{formatDateTime(scheduleDetailQuery.data.scheduled_start_at)}</Descriptions.Item>
              <Descriptions.Item label="时长">{`${scheduleDetailQuery.data.duration_minutes} 分钟`}</Descriptions.Item>
              <Descriptions.Item label="简历">{scheduleDetailQuery.data.resume_file_name || scheduleDetailQuery.data.resume_id}</Descriptions.Item>
              <Descriptions.Item label="岗位方向">{scheduleDetailQuery.data.job_role || '--'}</Descriptions.Item>
              <Descriptions.Item label="JD">{scheduleDetailQuery.data.jd_title || scheduleDetailQuery.data.jd_id || '--'}</Descriptions.Item>
              <Descriptions.Item label="难度">{scheduleDetailQuery.data.difficulty}</Descriptions.Item>
              <Descriptions.Item label="输入/输出">{`${scheduleDetailQuery.data.input_mode} / ${scheduleDetailQuery.data.output_mode}`}</Descriptions.Item>
              <Descriptions.Item label="题型">{scheduleDetailQuery.data.question_types.join('、') || '--'}</Descriptions.Item>
            </Descriptions>
            <Space wrap>
              <Button onClick={() => openExternalUrl(scheduleDetailQuery.data.google_calendar_url)}>加入 Google 日历</Button>
              <Button onClick={() => openExternalUrl(scheduleDetailQuery.data.outlook_calendar_url)}>加入 Outlook 日历</Button>
              <Button onClick={() => void handleCalendarDownload(scheduleDetailQuery.data.schedule_id)}>下载 .ics</Button>
              {scheduleDetailQuery.data.can_cancel ? (
                <Button danger loading={cancelMutation.isPending} onClick={() => cancelMutation.mutate(scheduleDetailQuery.data.schedule_id)}>
                  取消预约
                </Button>
              ) : null}
              {scheduleDetailQuery.data.can_start ? (
                <Button type="primary" loading={startMutation.isPending} onClick={() => startMutation.mutate(scheduleDetailQuery.data.schedule_id)}>
                  开始面试
                </Button>
              ) : null}
              {scheduleDetailQuery.data.status === 'in_progress' && scheduleDetailQuery.data.interview_id ? (
                <Button type="primary" onClick={() => navigate(`/interview/${scheduleDetailQuery.data.interview_id}`)}>
                  继续面试
                </Button>
              ) : null}
            </Space>
          </Space>
        ) : (
          <Typography.Text type="secondary">{scheduleDetailQuery.isLoading ? '加载中...' : '暂无详情'}</Typography.Text>
        )}
      </Modal>

      <Modal
        title="创建单次预约"
        open={createModalOpen}
        onCancel={() => setCreateModalOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={createMutation.isPending}
        okText="创建预约"
        cancelText="取消"
        width={880}
        forceRender
        destroyOnHidden
      >
        <Form
          form={form}
          preserve={false}
          layout="vertical"
          onFinish={(values) => {
            if (!resumeId) {
              message.warning('请先选择简历')
              return
            }
            const localValue = String(values.scheduled_start_at || '').trim()
            if (!localValue) {
              message.warning('请选择预约时间')
              return
            }
            createMutation.mutate({
              title: values.title || values.session_name || '',
              scheduled_start_at: new Date(localValue).toISOString(),
              duration_minutes: values.duration_minutes,
              resume_id: resumeId,
              job_role: positionMode === 'role' ? values.job_role : undefined,
              difficulty: values.difficulty,
              input_mode: values.input_mode,
              output_mode: values.output_mode,
              session_name: values.session_name,
              question_types: questionTypeOrder.filter((item) => (values.question_types || []).includes(item)),
              jd_id: positionMode === 'jd' ? values.jd_id : undefined,
              voice_tone_id: values.output_mode === 'voice' ? values.voice_tone_id || undefined : undefined,
            })
          }}
        >
          <div
            data-testid="schedule-create-form-grid"
            style={{
              display: 'grid',
              gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)',
              gap: 16,
              alignItems: 'start',
            }}
          >
            <div style={{ minWidth: 0 }}>
              <Form.Item label="已选简历">
                <Space direction="vertical" size={10} style={{ width: '100%' }}>
                  {resumeId ? <Tag color="blue">{selectedResumeName ? `${selectedResumeName} (${resumeId})` : resumeId}</Tag> : <Tag color="red">未选择</Tag>}
                  <Select
                    value={resumeId || undefined}
                    style={{ width: '100%' }}
                    placeholder="请选择简历"
                    options={(resumeQuery.data?.items ?? []).map((item) => ({
                      label: `${item.file_name}（${item.parse_status}）`,
                      value: item.resume_id,
                    }))}
                    onChange={(value: string) => setResumeId(value)}
                  />
                </Space>
              </Form.Item>
              <Form.Item name="scheduled_start_at" label="预约时间" rules={[{ required: true, message: '请选择预约时间' }]}>
                <Input type="datetime-local" />
              </Form.Item>
              <Form.Item name="duration_minutes" label="面试时长">
                <Radio.Group
                  options={[
                    { label: '20 分钟', value: 20 },
                    { label: '45 分钟', value: 45 },
                    { label: '60 分钟', value: 60 },
                  ]}
                />
              </Form.Item>
              <Form.Item label="岗位信息模式">
                <Radio.Group
                  value={positionMode}
                  onChange={(event) => {
                    const nextMode = event.target.value as 'role' | 'jd'
                    setPositionMode(nextMode)
                    if (nextMode === 'role') {
                      form.setFieldValue('jd_id', '')
                    }
                  }}
                  options={[
                    { label: '岗位方向', value: 'role' },
                    { label: '岗位描述（JD）', value: 'jd' },
                  ]}
                />
              </Form.Item>
              {positionMode === 'role' ? (
                <Form.Item name="job_role" label="岗位方向" rules={[{ required: true, message: '请选择岗位方向' }]}>
                  <Select
                    options={[
                      { label: 'Java', value: 'java' },
                      { label: 'Web', value: 'web' },
                    ]}
                    onChange={(value: 'java' | 'web') => setJobRole(value)}
                  />
                </Form.Item>
              ) : (
                <Form.Item name="jd_id" label="岗位描述（JD）" rules={[{ required: true, message: '请选择岗位描述' }]}>
                  <Select
                    showSearch
                    optionFilterProp="label"
                    placeholder="请选择 JD"
                    options={(jdQuery.data?.items ?? []).map((item) => ({
                      label: `${item.title}（${item.job_role}）`,
                      value: item.jd_id,
                    }))}
                  />
                </Form.Item>
              )}
            </div>

            <div style={{ minWidth: 0 }}>
              <Form.Item name="title" label="预约标题">
                <Input placeholder="例如：周三晚 Java 一面模拟" maxLength={128} />
              </Form.Item>
              <Form.Item name="session_name" label="面试名称">
                <Input placeholder="例如：Java 后端一面模拟" maxLength={128} />
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
              <Form.Item shouldUpdate={(prev, next) => prev.output_mode !== next.output_mode} noStyle>
                {({ getFieldValue }) =>
                  getFieldValue('output_mode') === 'voice' ? (
                    <Form.Item name="voice_tone_id" label="面试官语气">
                      <Select
                        allowClear
                        loading={toneQuery.isLoading}
                        placeholder="可选，不选则使用默认语气"
                        options={(toneQuery.data?.items ?? []).map((item) => ({
                          label: `${item.tone_name}（x${item.speed.toFixed(2)}）`,
                          value: item.tone_id,
                        }))}
                      />
                    </Form.Item>
                  ) : null
                }
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
            </div>
          </div>
        </Form>
      </Modal>
    </Space>
  )
}
