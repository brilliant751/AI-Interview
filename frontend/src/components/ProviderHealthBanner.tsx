import { Alert, Space, Tag } from 'antd'

import type { ProviderHealthResponse } from '../api/admin'

/** provider 状态展示条。 */
export function ProviderHealthBanner({
  health,
  loading = false,
  errorMessage = '',
}: {
  health: ProviderHealthResponse | null
  loading?: boolean
  errorMessage?: string
}) {
  if (loading) {
    return <Alert type="info" message="正在获取本地模型状态..." showIcon />
  }
  if (errorMessage) {
    return <Alert type="error" message={`本地模型状态获取失败：${errorMessage}`} showIcon />
  }
  if (!health) {
    return <Alert type="warning" message="暂无本地模型状态，请稍后重试" showIcon />
  }

  const modeText =
    health.overall === 'UP' ? '本地 AI' : health.overall === 'DEGRADED' ? '兜底模板' : '异常状态'

  const modeType = health.overall === 'UP' ? 'success' : health.overall === 'DEGRADED' ? 'warning' : 'error'

  return (
    <Alert
      type={modeType}
      showIcon
      message={`当前模式：${modeText}`}
      description={
        <Space wrap>
          {Object.entries(health.providers).map(([key, item]) => (
            <Tag key={key} color={item.status === 'UP' ? 'green' : item.status === 'DEGRADED' ? 'gold' : 'red'}>
              {`${key}: ${item.status} (${item.provider})`}
            </Tag>
          ))}
        </Space>
      }
    />
  )
}
