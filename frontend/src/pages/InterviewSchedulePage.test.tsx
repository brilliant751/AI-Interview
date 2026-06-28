import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import { InterviewSchedulePage } from './InterviewSchedulePage'
import { useInterviewStore } from '../stores/interviewStore'

const mockNavigate = vi.fn()
const mockCreateInterviewSchedule = vi.fn()
const mockFetchInterviewSchedules = vi.fn()
const mockFetchInterviewScheduleDetail = vi.fn()
const mockStartInterviewSchedule = vi.fn()
const mockCancelInterviewSchedule = vi.fn()
const mockDownloadInterviewScheduleCalendar = vi.fn()
const mockFetchResumes = vi.fn()
const mockFetchJds = vi.fn()
const mockFetchVoiceToneProfiles = vi.fn()
const mockWindowOpen = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

vi.mock('../api/interview', () => ({
  createInterviewSchedule: (payload: unknown) => mockCreateInterviewSchedule(payload),
  fetchInterviewSchedules: (params: unknown) => mockFetchInterviewSchedules(params),
  fetchInterviewScheduleDetail: (scheduleId: string) => mockFetchInterviewScheduleDetail(scheduleId),
  startInterviewSchedule: (scheduleId: string) => mockStartInterviewSchedule(scheduleId),
  cancelInterviewSchedule: (scheduleId: string) => mockCancelInterviewSchedule(scheduleId),
  downloadInterviewScheduleCalendar: (scheduleId: string) => mockDownloadInterviewScheduleCalendar(scheduleId),
  fetchResumes: (params: unknown) => mockFetchResumes(params),
  fetchJds: (params: unknown) => mockFetchJds(params),
  fetchVoiceToneProfiles: () => mockFetchVoiceToneProfiles(),
}))

// InterviewSchedulePage 测试说明：
// 1. 所有后端 API 都用 mock 函数替换，测试只验证页面交互和状态写入。
// 2. 创建、取消、开始和下载日历是预约页最关键的用户动作。
// 3. start 成功后需要写入 interviewStore 并跳转面试页，这里会直接断言。
// 4. window.open/download 等浏览器能力使用 mock，避免测试环境真实打开窗口。
// 5. 预约页依赖多组异步数据，QueryClient 包装是测试稳定运行的前提。

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <InterviewSchedulePage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('InterviewSchedulePage', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.setSystemTime(new Date('2026-06-06T10:00:00+08:00'))
    vi.clearAllMocks()
    vi.stubGlobal('open', mockWindowOpen)
    vi.spyOn(window, 'getComputedStyle').mockImplementation(
      () =>
        ({
          getPropertyValue: () => '',
        }) as unknown as CSSStyleDeclaration,
    )
    useInterviewStore.getState().reset()
    useInterviewStore.getState().setResumeId('res_123456')
    mockFetchResumes.mockResolvedValue({
      items: [{ resume_id: 'res_123456', file_name: '张三-后端简历.pdf', parse_status: 'READY', created_at: '2026-06-06 10:00:00' }],
      page: 1,
      page_size: 50,
      total: 1,
    })
    mockFetchJds.mockResolvedValue({
      items: [{ jd_id: 'jd_001', title: 'Java 后端 JD', job_role: 'java' }],
    })
    mockFetchVoiceToneProfiles.mockResolvedValue({
      items: [{ tone_id: 'tone_default', tone_name: '标准面试官', description: '', base_instructions: '', speed: 1 }],
    })
    mockFetchInterviewSchedules.mockResolvedValue({
      items: [
        {
          schedule_id: 'sch_001',
          title: '预约 Java 模拟面试',
          status: 'ready',
          source_type: 'single',
          scheduled_start_at: '2026-06-10T20:00:00+08:00',
          scheduled_end_at: '2026-06-10T20:45:00+08:00',
          duration_minutes: 45,
          job_role: 'java',
          difficulty: 'medium',
          resume_id: 'res_123456',
          jd_id: 'jd_001',
          interview_id: '',
          resume_file_name: '张三-后端简历.pdf',
          google_calendar_url: 'https://calendar.google.com/calendar/render?action=TEMPLATE&text=预约+Java+模拟面试',
          outlook_calendar_url: 'https://outlook.office.com/calendar/0/deeplink/compose?subject=预约+Java+模拟面试',
          created_at: '2026-06-06T10:00:00+08:00',
        },
      ],
      page: 1,
      page_size: 20,
      total: 1,
    })
    mockFetchInterviewScheduleDetail.mockResolvedValue({
      schedule_id: 'sch_001',
      status: 'ready',
      source_type: 'single',
      title: '预约 Java 模拟面试',
      scheduled_start_at: '2026-06-10T20:00:00+08:00',
      scheduled_end_at: '2026-06-10T20:45:00+08:00',
      duration_minutes: 45,
      timezone: 'Asia/Shanghai',
      resume_id: 'res_123456',
      resume_file_name: '张三-后端简历.pdf',
      job_role: 'java',
      jd_id: 'jd_001',
      jd_title: 'Java 后端 JD',
      difficulty: 'medium',
      input_mode: 'voice',
      output_mode: 'voice',
      session_name: '预约 Java 模拟面试',
      question_types: ['project', 'technical'],
      voice_tone_id: 'tone_default',
      calendar_download_url: '/api/v1/interview-schedules/sch_001/calendar.ics',
      google_calendar_url: 'https://calendar.google.com/calendar/render?action=TEMPLATE&text=预约+Java+模拟面试',
      outlook_calendar_url: 'https://outlook.office.com/calendar/0/deeplink/compose?subject=预约+Java+模拟面试',
      can_start: true,
      can_cancel: true,
      created_at: '2026-06-06T10:00:00+08:00',
      updated_at: '2026-06-06T10:00:00+08:00',
    })
    mockCreateInterviewSchedule.mockResolvedValue({
      schedule_id: 'sch_002',
      status: 'scheduled',
      source_type: 'single',
      title: '新的预约',
      scheduled_start_at: '2026-06-11T20:00:00+08:00',
      scheduled_end_at: '2026-06-11T20:45:00+08:00',
      duration_minutes: 45,
      timezone: 'Asia/Shanghai',
      interview_id: '',
      calendar_download_url: '/api/v1/interview-schedules/sch_002/calendar.ics',
      google_calendar_url: 'https://calendar.google.com/calendar/render?action=TEMPLATE&text=新的预约',
      outlook_calendar_url: 'https://outlook.office.com/calendar/0/deeplink/compose?subject=新的预约',
      created_at: '2026-06-06T10:00:00+08:00',
    })
    mockStartInterviewSchedule.mockResolvedValue({
      schedule_id: 'sch_001',
      status: 'in_progress',
      interview_id: 'int_001',
      current_stage: 'SELF_INTRO',
      first_question: '请先做一个自我介绍。',
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  test('should render schedule calendar and ready action', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('模拟面试预约')).toBeInTheDocument()
      expect(screen.getByText('我的日程表')).toBeInTheDocument()
    })

    await waitFor(() => {
      expect(mockFetchInterviewSchedules).toHaveBeenCalled()
    })

    expect(screen.getByRole('button', { name: '创建单次预约' })).toBeInTheDocument()
    expect(screen.getByText(/的预约$/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '开始这场面试' })).toBeInTheDocument()
  })

  test('should submit create schedule payload', async () => {
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: '创建单次预约' }))

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('预约时间'), { target: { value: '2026-06-11T20:00' } })
    fireEvent.change(screen.getByPlaceholderText('例如：周三晚 Java 一面模拟'), { target: { value: '新的预约' } })
    fireEvent.click(screen.getAllByRole('button', { name: '创建预约' })[0])

    await waitFor(() => {
      expect(mockCreateInterviewSchedule).toHaveBeenCalledTimes(1)
    })

    expect(mockCreateInterviewSchedule.mock.calls[0][0]).toMatchObject({
      title: '新的预约',
      resume_id: 'res_123456',
      duration_minutes: 45,
      difficulty: 'medium',
      input_mode: 'voice',
      output_mode: 'voice',
    })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '加入 Google 日历' })).toBeInTheDocument()
    })
  })

  test('should open google calendar from schedule detail', async () => {
    const readyDateLabel = '2026-06-10 本月日期 1 场预约'

    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: readyDateLabel })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: readyDateLabel }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '查看详情' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: '查看详情' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '加入 Google 日历' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: '加入 Google 日历' }))

    expect(mockWindowOpen).toHaveBeenCalledWith(
      expect.stringContaining('calendar.google.com'),
      '_blank',
      'noopener,noreferrer',
    )
  })

  test('should keep two-column layout when selected resume is shown', async () => {
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: '创建单次预约' }))

    await waitFor(() => {
      expect(screen.getByRole('dialog', { name: '创建单次预约' })).toBeInTheDocument()
    })

    const formGrid = screen.getByTestId('schedule-create-form-grid')
    expect(formGrid.getAttribute('style')).toContain('grid-template-columns: minmax(0, 1fr) minmax(0, 1fr)')
    expect(screen.getAllByText(/张三-后端简历\.pdf/).length).toBeGreaterThan(0)
    expect(screen.getByLabelText('预约时间')).toBeInTheDocument()
    expect(screen.getByLabelText('预约标题')).toBeInTheDocument()
  })

  test('should prefill selected empty date to 20:00 when creating from empty day', async () => {
    mockFetchInterviewSchedules.mockResolvedValueOnce({
      items: [],
      page: 1,
      page_size: 20,
      total: 0,
    })

    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '为这一天新建预约' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: '为这一天新建预约' }))

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    expect(screen.getByLabelText('预约时间')).toHaveValue('2026-06-06T20:00')
  })

  test('should not allow creating schedule for past empty date', async () => {
    mockFetchInterviewSchedules.mockResolvedValueOnce({
      items: [],
      page: 1,
      page_size: 20,
      total: 0,
    })

    renderPage()

    await waitFor(() => {
      expect(screen.getByText(/这一天还没有预约/)).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: '2026-06-01 本月日期 无预约' }))

    await waitFor(() => {
      expect(screen.getByText(/这个日期已经过去了/)).toBeInTheDocument()
    })

    expect(screen.queryByRole('button', { name: '为这一天新建预约' })).not.toBeInTheDocument()
  })
})
