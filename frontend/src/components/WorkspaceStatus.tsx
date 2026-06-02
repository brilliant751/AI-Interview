import { Space, Tag, Typography } from 'antd'

const statusItems = [
  { label: 'Demo build', color: 'blue' },
  { label: 'Interview flow', color: 'green' },
  { label: 'Practice module', color: 'purple' },
]

/** Lightweight informational widget for the demo workspace. */
export function WorkspaceStatus() {
  return (
    <section
      aria-label="workspace status"
      style={{
        marginTop: 28,
        padding: '12px 16px',
        border: '1px solid #dbeafe',
        borderRadius: 8,
        background: '#f8fbff',
      }}
    >
      <Space direction="vertical" size={8}>
        <Typography.Text strong>Workspace status</Typography.Text>
        <Space wrap>
          {statusItems.map((item) => (
            <Tag key={item.label} color={item.color}>
              {item.label}
            </Tag>
          ))}
        </Space>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          This panel is a small frontend-only note for local demonstration and review.
        </Typography.Text>
      </Space>
    </section>
  )
}
