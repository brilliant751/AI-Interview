import { useMutation, useQuery } from '@tanstack/react-query'
import { Alert, Button, Card, Checkbox, Form, InputNumber, Radio, Space, Tag, Typography, message } from 'antd'
import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'

import { createPracticeSession, fetchPracticeRecords, type PracticeCategory } from '../api/practice'
import { parseApiError } from '../api/client'
import { usePracticeStore } from '../stores/practiceStore'

const CATEGORY_OPTIONS: Array<{ label: string; value: PracticeCategory }> = [
  { label: '技术', value: 'technical' },
  { label: '项目', value: 'project' },
  { label: '场景', value: 'scenario' },
  { label: '行为', value: 'behavior' },
]

/** 题库练习准备页。 */
export function PracticePreparePage() {
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const setSession = usePracticeStore((state) => state.setSession)

  /** 查询当前用户练习记录，用于展示继续练习入口。 */
  const recordsQuery = useQuery({
    queryKey: ['practice-records'],
    queryFn: fetchPracticeRecords,
  })

  const activeRecord = useMemo(
    () => recordsQuery.data?.items.find((item) => item.status === 'ACTIVE') || null,
    [recordsQuery.data?.items],
  )

  /** 创建练习会话。 */
  const createMutation = useMutation({
    mutationFn: createPracticeSession,
    onSuccess: (data) => {
      setSession(data)
      message.success('练习已开始')
      navigate(`/practice/${data.practice_id}`)
    },
    onError: (error) => {
      const parsed = parseApiError(error)
      message.error(parsed.message)
    },
  })

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card title="题库练习">
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Typography.Paragraph style={{ marginBottom: 0 }}>
            直接从题库抽题做练习，不依赖简历，不生成评分。支持固定题单和后续可扩展的追问式练习。
          </Typography.Paragraph>
          {activeRecord ? (
            <Alert
              type="info"
              showIcon
              message="发现未结束练习"
              description={
                <Space direction="vertical" size={8}>
                  <Space wrap>
                    <Tag color="blue">岗位：{activeRecord.job_role}</Tag>
                    <Tag color="gold">模式：{activeRecord.mode}</Tag>
                    <Tag color="purple">
                      进度：{activeRecord.answered_count}/{activeRecord.total_questions}
                    </Tag>
                  </Space>
                  <Button type="link" style={{ paddingInline: 0 }} onClick={() => navigate(`/practice/${activeRecord.practice_id}`)}>
                    继续当前练习
                  </Button>
                </Space>
              }
            />
          ) : null}
        </Space>
      </Card>

      <Card title="开始新练习">
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            job_role: 'java',
            mode: 'sequence',
            question_count: 5,
            category_filters: ['technical', 'project'],
          }}
          onFinish={(values) => createMutation.mutate(values)}
        >
          <Form.Item label="岗位方向" name="job_role">
            <Radio.Group
              options={[
                { label: 'Java', value: 'java' },
                { label: 'Web', value: 'web' },
              ]}
            />
          </Form.Item>
          <Form.Item label="练习模式" name="mode">
            <Radio.Group
              options={[
                { label: '固定题单', value: 'sequence' },
                { label: '追问式（预留）', value: 'followup' },
              ]}
            />
          </Form.Item>
          <Form.Item label="题量" name="question_count">
            <InputNumber min={1} max={20} style={{ width: 200 }} />
          </Form.Item>
          <Form.Item label="题目类别" name="category_filters">
            <Checkbox.Group options={CATEGORY_OPTIONS} />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={createMutation.isPending}>
            开始练习
          </Button>
        </Form>
      </Card>
    </Space>
  )
}
