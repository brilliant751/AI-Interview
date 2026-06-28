import { render, screen } from '@testing-library/react'
import { describe, expect, test } from 'vitest'

import { ProviderHealthBanner } from './ProviderHealthBanner'

// ProviderHealthBanner 测试说明：
// 1. 组件只负责展示 provider 健康状态，不主动发请求。
// 2. DEGRADED 状态需要明确展示兜底模板，提醒用户当前不是完整 AI 模式。
// 3. 每个 provider 的状态和名称都应可见，便于排查语音或检索异常。
// 4. 测试构造完整 health 对象，确保新增 provider 字段时不破坏渲染。

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
