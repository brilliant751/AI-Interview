import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

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
