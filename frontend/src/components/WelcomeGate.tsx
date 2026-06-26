import { useEffect, useState } from 'react'
import { Typography } from 'antd'

/** 应用级欢迎页：每次刷新或重新进入网页时展示一次。 */
export function WelcomeGate() {
  const [visible, setVisible] = useState(true)
  const [leaving, setLeaving] = useState(false)

  useEffect(() => {
    if (!visible) {
      return
    }
    const leaveTimer = window.setTimeout(() => {
      setLeaving(true)
    }, 2000)
    const hideTimer = window.setTimeout(() => {
      setVisible(false)
    }, 2800)
    return () => {
      window.clearTimeout(leaveTimer)
      window.clearTimeout(hideTimer)
    }
  }, [visible])

  if (!visible) {
    return null
  }

  return (
    <section className={`app-welcome-screen ${leaving ? 'is-leaving' : ''}`} aria-label="欢迎进入 AI 模拟面试系统">
      <div className="login-leaf-scene" aria-hidden="true">
        <span className="leaf leaf-a" />
        <span className="leaf leaf-b" />
        <span className="leaf leaf-c" />
        <span className="leaf leaf-d" />
        <span className="leaf-stem stem-a" />
        <span className="leaf-stem stem-b" />
      </div>
      <div className="login-welcome-copy">
        <Typography.Text className="login-welcome-kicker">AI Interview</Typography.Text>
        <Typography.Title level={1}>欢迎进入 AI 模拟面试系统</Typography.Title>
        <Typography.Paragraph>正在为你整理面试环境、练习记录和智能评估能力</Typography.Paragraph>
      </div>
    </section>
  )
}
