import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, test, vi } from 'vitest'

import { HomeOverviewPage } from './HomeOverviewPage'

const mockNavigate = vi.fn()
const mockFetchProviderHealth = vi.fn()
const mockFetchInterviewSchedules = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

vi.mock('../api/admin', () => ({
  fetchProviderHealth: () => mockFetchProviderHealth(),
}))

vi.mock('../api/interview', () => ({
  fetchInterviewSchedules: (params: unknown) => mockFetchInterviewSchedules(params),
}))

/** 渲染首页概览页。 */
function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <HomeOverviewPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('HomeOverviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(window, 'getComputedStyle').mockImplementation(
      () =>
        ({
          getPropertyValue: () => '',
        }) as unknown as CSSStyleDeclaration,
    )
    mockFetchProviderHealth.mockResolvedValue({
      overall: 'UP',
      providers: {
        asr: { status: 'UP' },
        llm: { status: 'UP' },
        embed: { status: 'UP' },
      },
    })
    mockFetchInterviewSchedules.mockResolvedValue({
      items: [
        {
          schedule_id: 'sch_001',
          title: '周三晚 Java 一面模拟',
          status: 'scheduled',
          source_type: 'single',
          scheduled_start_at: '2026-06-10T20:00:00+08:00',
          scheduled_end_at: '2026-06-10T20:45:00+08:00',
          duration_minutes: 45,
          job_role: 'java',
          difficulty: 'medium',
          resume_id: 'res_001',
          jd_id: '',
          interview_id: '',
          resume_file_name: '张三-后端简历.pdf',
          google_calendar_url: 'https://calendar.google.com/calendar/render?action=TEMPLATE',
          outlook_calendar_url: 'https://outlook.office.com/calendar/0/deeplink/compose',
          created_at: '2026-06-06T10:00:00+08:00',
        },
      ],
      page: 1,
      page_size: 3,
      total: 1,
    })
  })

  test('should render booking entry and recent schedule card', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('预约面试')).toBeInTheDocument()
    })

    await waitFor(() => {
      expect(mockFetchInterviewSchedules).toHaveBeenCalledTimes(1)
    })

    expect(screen.getByText('最近预约')).toBeInTheDocument()
    expect(screen.getByText(/预约概览$/)).toBeInTheDocument()
    expect(screen.getByText('查看日程表')).toBeInTheDocument()
  })
})
