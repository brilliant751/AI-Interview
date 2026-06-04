import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
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
  fetchInterviewPlayback: vi.fn(),
  fetchInterviewStatus: vi.fn(),
  fetchJds: vi.fn(),
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

/** 面试大厅渲染测试。 */
describe('InterviewPage lobby', () => {
  test('should render lobby guidance and paused section title', async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    })

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <InterviewPage />
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(screen.getByText('面试大厅')).toBeInTheDocument()
    expect(screen.getByText('创建新的模拟面试，或继续上次暂停的会话。')).toBeInTheDocument()
    expect(screen.getByText('暂停中的面试')).toBeInTheDocument()
    expect(await screen.findByText('暂无暂停中的面试，可点击“创建面试”开始。')).toBeInTheDocument()
  })
})
