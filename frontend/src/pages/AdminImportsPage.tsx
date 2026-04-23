import { useMutation, useQuery } from '@tanstack/react-query'
import { Alert, Button, Card, Checkbox, Form, Progress, Radio, Space, Tag, Typography, message } from 'antd'
import { useMemo, useState } from 'react'

import { getImportTask, triggerMaterialImport } from '../api/admin'
import { parseApiError } from '../api/client'

/** 管理导入表单载荷。 */
interface ImportFormPayload {
  rebuild_mode: 'full' | 'incremental'
  roles: Array<'java' | 'web'>
  dry_run: boolean
  chunk_model: string
  embedding_model: string
}

/** 管理端材料重建页面。 */
export function AdminImportsPage() {
  const [form] = Form.useForm()
  const [taskId, setTaskId] = useState('')
  const [lastPayload, setLastPayload] = useState<ImportFormPayload>({
    rebuild_mode: 'full' as const,
    roles: ['java', 'web'] as Array<'java' | 'web'>,
    dry_run: false,
    chunk_model: 'qwen2.5:7b',
    embedding_model: 'nomic-embed-text',
  })

  /** 轮询任务状态。 */
  const taskQuery = useQuery({
    queryKey: ['admin-import-task', taskId],
    queryFn: () => getImportTask(taskId),
    enabled: !!taskId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (!status) {
        return 1200
      }
      return ['SUCCESS', 'FAILED', 'PARTIAL_SUCCESS'].includes(status) ? false : 1200
    },
  })

  /** 是否存在运行中的任务。 */
  const isRunning = useMemo(() => {
    const status = taskQuery.data?.status
    return status === 'PENDING' || status === 'RUNNING'
  }, [taskQuery.data?.status])

  /** 触发导入任务。 */
  const triggerMutation = useMutation({
    mutationFn: async (payload: ImportFormPayload) => triggerMaterialImport(payload),
    onSuccess: (data, payload) => {
      setTaskId(data.task_id)
      setLastPayload(payload)
      message.success(`任务已提交：${data.task_id}`)
    },
    onError: (error) => {
      const parsed = parseApiError(error)
      if (parsed.code === 'KB_BUILD_409') {
        message.warning('全量重建任务已在运行，请等待当前任务完成')
        return
      }
      message.error(parsed.message)
    },
  })

  /** 提交创建任务。 */
  const handleSubmit = (values: {
    rebuild_mode: 'full' | 'incremental'
    roles: Array<'java' | 'web'>
    dry_run: boolean
  }) => {
    triggerMutation.mutate({
      ...values,
      chunk_model: 'qwen2.5:7b',
      embedding_model: 'nomic-embed-text',
    })
  }

  /** 使用上次参数重试。 */
  const handleRetryLast = () => {
    triggerMutation.mutate(lastPayload)
  }

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card title="知识库重建任务">
        <Form
          form={form}
          initialValues={lastPayload}
          layout="vertical"
          onFinish={handleSubmit}
        >
          <Form.Item label="重建模式" name="rebuild_mode">
            <Radio.Group
              options={[
                { label: '全量重建', value: 'full' },
                { label: '增量重建', value: 'incremental' },
              ]}
            />
          </Form.Item>
          <Form.Item label="岗位范围" name="roles">
            <Checkbox.Group
              options={[
                { label: 'Java', value: 'java' },
                { label: 'Web', value: 'web' },
              ]}
            />
          </Form.Item>
          <Form.Item label="模型（固定）">
            <Space>
              <Tag color="processing">chunk: qwen2.5:7b</Tag>
              <Tag color="purple">embed: nomic-embed-text</Tag>
            </Space>
          </Form.Item>
          <Form.Item name="dry_run" valuePropName="checked">
            <Checkbox>仅执行 dry-run</Checkbox>
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={triggerMutation.isPending} disabled={isRunning}>
            发起任务
          </Button>
        </Form>
      </Card>

      <Card title="任务状态">
        {!taskId && <Typography.Text type="secondary">尚未提交任务</Typography.Text>}
        {taskId && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Typography.Text>任务 ID：{taskId}</Typography.Text>
            <Space>
              <Tag color={taskQuery.data?.status === 'FAILED' ? 'error' : 'blue'}>
                状态：{taskQuery.data?.status ?? 'PENDING'}
              </Tag>
              <Tag>阶段：{taskQuery.data?.stage ?? '-'}</Tag>
            </Space>
            <Progress percent={taskQuery.data?.progress ?? 0} />
            {taskQuery.data?.last_error ? <Alert type="error" message={taskQuery.data.last_error} /> : null}
            {taskQuery.data && ['FAILED', 'PARTIAL_SUCCESS'].includes(taskQuery.data.status) ? (
              <Button onClick={handleRetryLast} loading={triggerMutation.isPending}>
                按上次参数重试
              </Button>
            ) : null}
          </Space>
        )}
      </Card>
    </Space>
  )
}
