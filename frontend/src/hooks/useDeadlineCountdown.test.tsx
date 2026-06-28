import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'

import { useDeadlineCountdown } from './useDeadlineCountdown'

// useDeadlineCountdown 测试说明：
// 1. 使用 fake timers 固定系统时间，断言不受真实时间流逝影响。
// 2. 重复 start 和 rerender 是为了防止多 interval 导致倒计时加速。
// 3. onExpire 只能触发一次，避免面试自动提交或提示重复执行。
// 4. Hook 测试不渲染真实页面，只验证返回状态和控制函数。
// 5. 这些用例保护语音作答倒计时的稳定性。

describe('useDeadlineCountdown', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-06-07T10:00:00.000Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  test('keeps countdown aligned to real time after repeated starts and rerenders', () => {
    const onExpire = vi.fn()
    const { result, rerender } = renderHook(
      ({ transcript }) => {
        void transcript
        return useDeadlineCountdown({ initialSeconds: 10, onExpire })
      },
      { initialProps: { transcript: '' } },
    )

    act(() => {
      result.current.start(10)
      result.current.start(10)
      result.current.start(10)
    })
    rerender({ transcript: '语音识别片段 1' })
    rerender({ transcript: '语音识别片段 2' })

    act(() => {
      vi.advanceTimersByTime(3000)
    })

    expect(result.current.remainingSeconds).toBe(7)
    expect(onExpire).not.toHaveBeenCalled()

    act(() => {
      vi.advanceTimersByTime(7000)
    })

    expect(result.current.remainingSeconds).toBe(0)
    expect(onExpire).toHaveBeenCalledTimes(1)
  })

  test('clears the old timer when a new question starts a new countdown', () => {
    const onExpire = vi.fn()
    const { result } = renderHook(() => useDeadlineCountdown({ initialSeconds: 10, onExpire }))

    act(() => {
      result.current.start(10)
      vi.advanceTimersByTime(4000)
    })
    expect(result.current.remainingSeconds).toBe(6)

    act(() => {
      result.current.start(10)
      vi.advanceTimersByTime(1000)
    })
    expect(result.current.remainingSeconds).toBe(9)

    act(() => {
      vi.advanceTimersByTime(8000)
    })
    expect(result.current.remainingSeconds).toBe(1)
    expect(onExpire).not.toHaveBeenCalled()

    act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(result.current.remainingSeconds).toBe(0)
    expect(onExpire).toHaveBeenCalledTimes(1)
  })

  test('clears the timer on unmount', () => {
    const onExpire = vi.fn()
    const { result, unmount } = renderHook(() => useDeadlineCountdown({ initialSeconds: 5, onExpire }))

    act(() => {
      result.current.start(5)
    })
    unmount()

    act(() => {
      vi.advanceTimersByTime(10000)
    })

    expect(onExpire).not.toHaveBeenCalled()
  })
})
