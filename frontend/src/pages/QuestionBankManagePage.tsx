import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Card, Form, Input, Radio, Select, Space, Table, Tag, Typography, Upload, message } from 'antd'
import { useMemo, useState } from 'react'

import {
  createQuestionBankQuestion,
  fetchAdminQuestionBank,
  fetchPracticeImportTask,
  uploadQuestionBankMarkdown,
  type PracticeCategory,
} from '../api/practice'
import { parseApiError } from '../api/client'

// 题库管理页：
// 1. 管理员可以查看结构化题库、上传 Markdown、手动新增题目。
// 2. 查询条件包括岗位、类别、关键字和分页，方便定位具体题目。
// 3. Markdown 上传后会触发导入任务，页面通过 taskId 轮询进度。
// 4. 手动新增题目写入源材料后也会刷新列表，保持页面和数据库同步。
// 5. 类别选项与练习准备页保持同一套英文枚举。

const CATEGORY_OPTIONS: Array<{ label: string; value: PracticeCategory }> = [
  { label: '技术', value: 'technical' },
  { label: '项目', value: 'project' },
  { label: '场景', value: 'scenario' },
  { label: '行为', value: 'behavior' },
]

/** 题库管理页。 */
export function QuestionBankManagePage() {
  const queryClient = useQueryClient()
  const [jobRole, setJobRole] = useState<'java' | 'web'>('java')
  const [category, setCategory] = useState<PracticeCategory | undefined>(undefined)
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [taskId, setTaskId] = useState('')
  const [form] = Form.useForm()

  /** 查询题库列表。 */
  const questionBankQuery = useQuery({
    queryKey: ['admin-question-bank', jobRole, category, keyword, page, pageSize],
    queryFn: () =>
      fetchAdminQuestionBank({
        job_role: jobRole,
        category,
        keyword: keyword || undefined,
        page,
        page_size: pageSize,
      }),
  })

  /** 轮询导入任务状态。 */
  const taskQuery = useQuery({
    queryKey: ['practice-import-task', taskId],
    queryFn: () => fetchPracticeImportTask(taskId),
    enabled: Boolean(taskId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (!status) {
        return 1200
      }
      return ['SUCCESS', 'FAILED', 'PARTIAL_SUCCESS'].includes(status) ? false : 1200
    },
  })

  const isTaskRunning = useMemo(() => {
    const status = taskQuery.data?.status
    return status === 'PENDING' || status === 'RUNNING'
  }, [taskQuery.data?.status])

  /** 上传 Markdown。 */
  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!selectedFile) {
        throw new Error('请先选择 Markdown 文件')
      }
      return uploadQuestionBankMarkdown(jobRole, selectedFile)
    },
    onSuccess: (data) => {
      setTaskId(data.task_id)
      void queryClient.invalidateQueries({ queryKey: ['admin-question-bank'] })
      message.success(`上传任务已提交：${data.task_id}`)
      setSelectedFile(null)
    },
    onError: (error) => {
      const parsed = parseApiError(error)
      message.error(parsed.message)
    },
  })

  /** 单题录入。 */
  const createMutation = useMutation({
    mutationFn: createQuestionBankQuestion,
    onSuccess: (data) => {
      setTaskId(data.task_id)
      void queryClient.invalidateQueries({ queryKey: ['admin-question-bank'] })
      message.success(`题目录入任务已提交：${data.task_id}`)
      form.resetFields()
    },
    onError: (error) => {
      const parsed = parseApiError(error)
      message.error(parsed.message)
    },
  })

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card title="题库管理">
        <Alert
          type="info"
          showIcon
          message="上传规范"
          description="Markdown 必须符合现有题库结构。Java 使用 ##/###，Web 使用 ###/####，并包含“第X题 / 题干 / 类别 / 解析”顺序。"
        />
      </Card>

      <Card title="题库列表">
        <Space wrap style={{ marginBottom: 16 }}>
          <Radio.Group
            value={jobRole}
            onChange={(event) => {
              setPage(1)
              setJobRole(event.target.value)
            }}
            options={[
              { label: 'Java', value: 'java' },
              { label: 'Web', value: 'web' },
            ]}
          />
          <Select
            allowClear
            placeholder="按类别筛选"
            style={{ width: 180 }}
            options={CATEGORY_OPTIONS}
            value={category}
            onChange={(value) => {
              setPage(1)
              setCategory(value)
            }}
          />
          <Input.Search
            allowClear
            placeholder="按关键词筛选"
            style={{ width: 240 }}
            onSearch={(value) => {
              setPage(1)
              setKeyword(value)
            }}
          />
        </Space>
        <Table
          rowKey="record_id"
          loading={questionBankQuery.isLoading}
          dataSource={questionBankQuery.data?.items ?? []}
          pagination={{
            current: page,
            pageSize,
            total: questionBankQuery.data?.total ?? 0,
            onChange: (nextPage, nextPageSize) => {
              setPage(nextPage)
              setPageSize(nextPageSize)
            },
          }}
          columns={[
            { title: '题号', dataIndex: 'question_no', width: 80 },
            { title: '标题', dataIndex: 'title', width: 180 },
            { title: '类别', dataIndex: 'category', width: 120, render: (value?: string) => value || '-' },
            { title: '题干', dataIndex: 'question' },
            { title: '来源', dataIndex: 'source_path', width: 240 },
          ]}
        />
      </Card>

      <Card title="上传 Markdown">
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Upload
            accept=".md,text/markdown"
            beforeUpload={(file) => {
              setSelectedFile(file)
              return false
            }}
            fileList={selectedFile ? [selectedFile as never] : []}
            onRemove={() => {
              setSelectedFile(null)
            }}
          >
            <Button>选择 Markdown 文件</Button>
          </Upload>
          {selectedFile ? <Tag color="blue">已选择：{selectedFile.name}</Tag> : null}
          <Button type="primary" loading={uploadMutation.isPending} disabled={!selectedFile || isTaskRunning} onClick={() => uploadMutation.mutate()}>
            上传并触发导入
          </Button>
        </Space>
      </Card>

      <Card title="单题录入">
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            job_role: 'java',
            category: 'technical',
            source_note: 'admin-form',
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
          <Form.Item label="题目类别" name="category">
            <Select options={CATEGORY_OPTIONS} />
          </Form.Item>
          <Form.Item label="标题" name="title" rules={[{ required: true, message: '请输入标题' }]}>
            <Input />
          </Form.Item>
          <Form.Item label="题干" name="question" rules={[{ required: true, message: '请输入题干' }]}>
            <Input.TextArea rows={5} />
          </Form.Item>
          <Form.Item label="解析" name="analysis" rules={[{ required: true, message: '请输入解析' }]}>
            <Input.TextArea rows={5} />
          </Form.Item>
          <Form.Item label="来源说明" name="source_note">
            <Input />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={createMutation.isPending} disabled={isTaskRunning}>
            保存并触发导入
          </Button>
        </Form>
      </Card>

      <Card title="导入任务状态">
        {!taskId ? <Typography.Text type="secondary">尚未触发题库导入任务</Typography.Text> : null}
        {taskId ? (
          <Space direction="vertical" size={10} style={{ width: '100%' }}>
            <Typography.Text>任务 ID：{taskId}</Typography.Text>
            <Space wrap>
              <Tag color={taskQuery.data?.status === 'FAILED' ? 'error' : 'processing'}>
                状态：{taskQuery.data?.status || 'PENDING'}
              </Tag>
              <Tag>阶段：{taskQuery.data?.stage || '-'}</Tag>
              <Tag>进度：{taskQuery.data?.progress || 0}%</Tag>
            </Space>
            {taskQuery.data?.last_error ? <Alert type="error" message={taskQuery.data.last_error} /> : null}
          </Space>
        ) : null}
      </Card>
    </Space>
  )
}
