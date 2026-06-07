import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeAll, describe, expect, test, vi } from 'vitest'

import { InterviewPage } from './InterviewPage'

vi.mock('../api/admin', () => ({
  fetchProviderHealth: vi.fn(async () => ({
    overall: 'UP',
    providers: {},
  })),
}))

vi.mock('../api/interview', () => ({
  createInterview: vi.fn(),
  fetchHistory: vi.fn(async () => ({
    total: 0,
    items: [],
  })),
  fetchInterviewPlayback: vi.fn(async () => ({
    interview_id: 'interview-001',
    resume: {
      resume_id: 'resume-001',
      file_name: 'resume.pdf',
    },
    meta: {
      job_role: 'web',
      difficulty: 'medium',
      status: 'ACTIVE',
      started_at: '2026-06-07T10:00:00Z',
      duration_seconds: 0,
    },
    turns: [],
  })),
  fetchInterviewStatus: vi.fn(async () => ({
    interview_id: 'interview-001',
    status: 'ACTIVE',
    current_stage: 'SELF_INTRO',
    follow_up_count: 0,
    technical_count: 0,
    job_role: 'web',
    difficulty: 'medium',
    input_mode: 'text',
    output_mode: 'text',
    current_question: '请做一个简短自我介绍。',
    duration_seconds: 0,
  })),
  fetchJds: vi.fn(async () => ({ items: [] })),
  fetchResumeFile: vi.fn(),
  fetchResumes: vi.fn(async () => ({
    items: [],
    page: 1,
    page_size: 50,
    total: 0,
  })),
  finishInterview: vi.fn(),
  submitAudioTurn: vi.fn(),
  submitTurn: vi.fn(),
}))

beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
  Object.defineProperty(window, 'getComputedStyle', {
    writable: true,
    value: vi.fn(() => ({
      getPropertyValue: vi.fn(() => ''),
    })),
  })
})

/** 创建测试用 QueryClient。 */
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })
}

/** 渲染面试页。 */
function renderInterviewPage(initialPath: string) {
  return render(
    <QueryClientProvider client={createTestQueryClient()}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/interview" element={<InterviewPage />} />
          <Route path="/interview/:interviewId" element={<InterviewPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('InterviewPage design', () => {
  test('should render interview center lobby sections', async () => {
    renderInterviewPage('/interview')

    expect(screen.getByText('面试中心')).toBeInTheDocument()
    expect(screen.getByText('从简历出发，快速进入一场结构化模拟面试。')).toBeInTheDocument()
    expect(screen.getByText('新建模拟面试')).toBeInTheDocument()
    expect(screen.getAllByText('继续暂停面试').length).toBeGreaterThan(0)
    expect(await screen.findByText('暂无暂停中的面试，可点击“创建面试”开始。')).toBeInTheDocument()
  })
})
