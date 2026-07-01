import { render, screen } from '@testing-library/react'
import { describe, expect, test } from 'vitest'

import { ProviderHealthBanner } from './ProviderHealthBanner'

// ProviderHealthBanner 的主测试覆盖了 degraded 情况。
// 这里补充 loading、error、empty 和 UP/DOWN 情况，确保健康状态横幅各分支都有保护。

describe('ProviderHealthBanner extra states', () => {
  test('renders loading state', () => {
    render(<ProviderHealthBanner health={null} loading />)

    expect(screen.getByText('正在获取本地模型状态...')).toBeInTheDocument()
  })

  test('renders error state before empty state', () => {
    render(<ProviderHealthBanner health={null} errorMessage="network failed" />)

    expect(screen.getByText('本地模型状态获取失败：network failed')).toBeInTheDocument()
  })

  test('renders empty state when no health data is available', () => {
    render(<ProviderHealthBanner health={null} />)

    expect(screen.getByText('暂无本地模型状态，请稍后重试')).toBeInTheDocument()
  })

  test('renders UP provider status as local AI mode', () => {
    render(
      <ProviderHealthBanner
        health={{
          overall: 'UP',
          providers: {
            asr: { status: 'UP', provider: 'mock', model: 'mock', latency_ms: 1, error_message: '' },
            llm: { status: 'UP', provider: 'mock', model: 'mock', latency_ms: 1, error_message: '' },
            tts: { status: 'UP', provider: 'mock', model: 'mock', latency_ms: 1, error_message: '' },
          },
        }}
      />,
    )

    expect(screen.getByText('当前模式：本地 AI')).toBeInTheDocument()
    expect(screen.getByText('llm: UP (mock)')).toBeInTheDocument()
  })

  test('renders DOWN provider status as abnormal mode', () => {
    render(
      <ProviderHealthBanner
        health={{
          overall: 'DOWN',
          providers: {
            llm: { status: 'DOWN', provider: 'ollama', model: 'qwen', latency_ms: 0, error_message: 'down' },
          },
        }}
      />,
    )

    expect(screen.getByText('当前模式：异常状态')).toBeInTheDocument()
    expect(screen.getByText('llm: DOWN (ollama)')).toBeInTheDocument()
  })
})
