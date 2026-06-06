import { render, screen } from '@testing-library/react'
import { describe, expect, test } from 'vitest'

import { ProviderHealthBanner } from './ProviderHealthBanner'

describe('ProviderHealthBanner', () => {
  test('renders degraded provider state without failing the page', () => {
    render(
      <ProviderHealthBanner
        health={{
          overall: 'DEGRADED',
          providers: {
            asr: { status: 'DOWN', provider: 'funasr', model: 'paraformer', latency_ms: 1, error_message: 'down' },
            llm: { status: 'UP', provider: 'mock', model: 'mock', latency_ms: 1, error_message: '' },
            tts: { status: 'UP', provider: 'mock', model: 'mock', latency_ms: 1, error_message: '' },
            embed: { status: 'DEGRADED', provider: 'hash', model: 'hashing', latency_ms: 1, error_message: '' },
          },
        }}
      />,
    )

    expect(screen.getByText('当前模式：兜底模板')).toBeInTheDocument()
    expect(screen.getByText('asr: DOWN (funasr)')).toBeInTheDocument()
    expect(screen.getByText('embed: DEGRADED (hash)')).toBeInTheDocument()
  })
})
