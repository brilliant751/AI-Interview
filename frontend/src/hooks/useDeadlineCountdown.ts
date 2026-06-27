import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

// 倒计时 Hook 的关键点：
// 1. 使用真实 deadline 时间戳计算剩余秒数，而不是简单每次 -1。
// 2. interval 只作为刷新触发器，页面卡顿后仍能回到正确剩余时间。
// 3. onExpire 使用 ref 保存最新回调，避免依赖变化导致重复启动定时器。
// 4. expiredRef 保证过期回调只触发一次。
// 5. clearTimer 在组件卸载时执行，避免离开页面后仍然运行 interval。

/** deadline 倒计时配置。 */
interface DeadlineCountdownOptions {
  initialSeconds: number
  tickMs?: number
  onExpire?: () => void
}

/** 基于真实时间戳的单实例倒计时，避免重复 interval 导致计时加速。 */
export function useDeadlineCountdown(options: DeadlineCountdownOptions) {
  const { initialSeconds, tickMs = 250, onExpire } = options
  const [remainingSeconds, setRemainingSeconds] = useState(initialSeconds)
  const intervalRef = useRef<number | null>(null)
  const deadlineRef = useRef<number | null>(null)
  const onExpireRef = useRef(onExpire)
  const expiredRef = useRef(false)

  useEffect(() => {
    onExpireRef.current = onExpire
  }, [onExpire])

  const clearTimer = useCallback(() => {
    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    deadlineRef.current = null
  }, [])

  const refreshRemaining = useCallback(() => {
    // 每次刷新都根据 Date.now() 和 deadline 重新计算，避免 setInterval 漂移累积误差。
    if (deadlineRef.current === null) {
      return
    }
    const nextRemaining = Math.max(0, Math.ceil((deadlineRef.current - Date.now()) / 1000))
    setRemainingSeconds(nextRemaining)
    if (nextRemaining > 0) {
      return
    }
    clearTimer()
    if (!expiredRef.current) {
      expiredRef.current = true
      onExpireRef.current?.()
    }
  }, [clearTimer])

  const start = useCallback(
    (seconds = initialSeconds) => {
      // 重启倒计时时先清理旧 interval，保证同一 Hook 实例永远只有一个计时器。
      const safeSeconds = Math.max(0, Math.ceil(seconds))
      clearTimer()
      expiredRef.current = false
      setRemainingSeconds(safeSeconds)
      if (safeSeconds <= 0) {
        expiredRef.current = true
        onExpireRef.current?.()
        return
      }
      deadlineRef.current = Date.now() + safeSeconds * 1000
      intervalRef.current = window.setInterval(refreshRemaining, tickMs)
    },
    [clearTimer, initialSeconds, refreshRemaining, tickMs],
  )

  const stop = useCallback(
    (nextRemaining = 0) => {
      clearTimer()
      expiredRef.current = false
      setRemainingSeconds(Math.max(0, Math.ceil(nextRemaining)))
    },
    [clearTimer],
  )

  const isRunning = useCallback(() => deadlineRef.current !== null, [])

  useEffect(() => clearTimer, [clearTimer])

  return useMemo(
    () => ({
      remainingSeconds,
      start,
      stop,
      isRunning,
    }),
    [isRunning, remainingSeconds, start, stop],
  )
}
