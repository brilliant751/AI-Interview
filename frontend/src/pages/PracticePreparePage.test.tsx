import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, test, vi } from 'vitest'

import { PracticePreparePage } from './PracticePreparePage'
import { usePracticeStore } from '../stores/practiceStore'

const mockFetchPracticeOverview = vi.fn()
const mockFetchPracticeRecords = vi.fn()
const mockCreatePracticeSession = vi.fn()
const mockNavigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

vi.mock('../api/practice', async () => {
  const actual = await vi.importActual('../api/practice')
  return {
    ...actual,
    fetchPracticeOverview: () => mockFetchPracticeOverview(),
    fetchPracticeRecords: () => mockFetchPracticeRecords(),
    createPracticeSession: (payload: unknown) => mockCreatePracticeSession(payload),
  }
})

/** 渲染题库练习准备页。 */
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
        <PracticePreparePage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('PracticePreparePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    usePracticeStore.getState().reset()
    mockFetchPracticeOverview.mockResolvedValue({
      total_questions: 200,
      total_answered_questions: 48,
      total_sessions: 6,
      active_sessions: 1,
      role_stats: [
        {
          job_role: 'java',
          total_questions: 120,
          active_sessions: 1,
          finished_sessions: 3,
          answered_questions: 35,
          completion_rate: 0.2917,
          latest_active_practice_id: 'prac-001',
        },
        {
          job_role: 'web',
          total_questions: 80,
          active_sessions: 0,
          finished_sessions: 2,
          answered_questions: 13,
          completion_rate: 0.1625,
          latest_active_practice_id: null,
        },
      ],
      recent_records: [
        {
          practice_id: 'prac-001',
          job_role: 'java',
          mode: 'sequence',
          status: 'ACTIVE',
          total_questions: 10,
          answered_count: 3,
          created_at: '2026-05-23 10:00:00',
        },
      ],
    })
    mockFetchPracticeRecords.mockResolvedValue({
      total: 1,
      items: [
        {
          practice_id: 'prac-001',
          job_role: 'java',
          mode: 'sequence',
          status: 'ACTIVE',
          total_questions: 10,
          answered_count: 3,
          created_at: '2026-05-23 10:00:00',
        },
      ],
    })
    mockCreatePracticeSession.mockResolvedValue({
      practice_id: 'prac-002',
      job_role: 'java',
      mode: 'sequence',
      status: 'ACTIVE',
      total_questions: 10,
      completed_count: 0,
      finished: false,
      question_strategy: 'sequence',
      current_question: {
        session_question_id: 'psq-001',
        question_order: 1,
        stem: '什么是 JVM？',
      },
    })
  })

  test('should render overview data and role cards', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('题库练习')).toBeInTheDocument()
      expect(screen.getByText('200')).toBeInTheDocument()
    })

    expect(screen.getByText('Java 题库练习')).toBeInTheDocument()
    expect(screen.getByText('Web 题库练习')).toBeInTheDocument()
    expect(screen.getByText('累计作答 35 题')).toBeInTheDocument()
    expect(screen.getByText('覆盖率 29.2%')).toBeInTheDocument()
    expect(screen.getByText('继续当前练习')).toBeInTheDocument()
  })

  test('should navigate to existing active session for role', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Java 题库练习')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: '继续该岗位练习' }))

    expect(mockNavigate).toHaveBeenCalledWith('/practice/prac-001')
    expect(mockCreatePracticeSession).not.toHaveBeenCalled()
  })

  test('should create session with selected filters when no active session', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Web 题库练习')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByLabelText('Web'))
    fireEvent.click(screen.getByLabelText('15 题'))
    fireEvent.click(screen.getByRole('button', { name: '开始该岗位练习' }))

    await waitFor(() => {
      expect(mockCreatePracticeSession).toHaveBeenCalledTimes(1)
    })

    expect(mockCreatePracticeSession).toHaveBeenCalledWith({
      job_role: 'web',
      mode: 'sequence',
      question_count: 15,
      category_filters: [],
    })
  })
})
