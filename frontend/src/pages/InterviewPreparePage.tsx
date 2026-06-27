import { useMutation, useQuery } from '@tanstack/react-query'
import { Button, Card, Checkbox, Form, Input, Modal, Radio, Select, Space, Switch, Table, Tabs, Tag, Typography, Upload, message } from 'antd'
import { AxiosError } from 'axios'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { fetchProviderHealth } from '../api/admin'
import { ProviderHealthBanner } from '../components/ProviderHealthBanner'
import { createInterview, fetchHistory, fetchInterviewStatus, fetchJds, fetchResumes, fetchVoiceToneProfiles, uploadJd } from '../api/interview'
import { useInterviewStore } from '../stores/interviewStore'

// InterviewPreparePage 是旧版/备用面试准备入口：
// 1. 支持选择简历、选择或上传 JD、配置岗位方向和面试模式。
// 2. 准备页会预先拉取 provider health，提示用户当前是否处于 mock/降级模式。
// 3. 创建成功后把首题和会话配置写入 interviewStore，再跳转答题页。
// 4. 页面保留暂停会话恢复入口，方便用户从准备页继续未完成面试。
// 5. 新版面试大厅也有准备弹窗，但该页面仍可作为独立入口使用。

/** 面试准备页面。 */
export function InterviewPreparePage() {
  const questionTypeOrder: Array<'project' | 'technical' | 'scenario'> = ['project', 'technical', 'scenario']
  const navigate = useNavigate()
  const resumeId = useInterviewStore((state) => state.resumeId)
  const setResumeId = useInterviewStore((state) => state.setResumeId)
  const setSessionConfig = useInterviewStore((state) => state.setSessionConfig)
  const setProviderHealth = useInterviewStore((state) => state.setProviderHealth)
  const [resumePickerOpen, setResumePickerOpen] = useState(false)
  const [pendingResumeId, setPendingResumeId] = useState('')
  const [jdPickerOpen, setJdPickerOpen] = useState(false)
  const [pendingJdId, setPendingJdId] = useState('')
  const [selectedJdTitle, setSelectedJdTitle] = useState('')
  const [currentJobRole, setCurrentJobRole] = useState<'java' | 'web'>('java')
  const [jdUploadTitle, setJdUploadTitle] = useState('')
  const [jdFilterRole, setJdFilterRole] = useState('')
  const [jdFilterTitle, setJdFilterTitle] = useState('')
  const [activeBindingTab, setActiveBindingTab] = useState<'resume' | 'jd'>('resume')
  const [positionMode, setPositionMode] = useState<'role' | 'jd'>('role')
  const [form] = Form.useForm()

  /** 查询 provider 健康状态。 */
  const healthQuery = useQuery({
    // provider health 在准备页展示给用户，避免进入面试后才发现模型不可用。
    // retry=false 可以更快暴露错误，避免页面长时间停留在加载态。
    queryKey: ['provider-health'],
    queryFn: fetchProviderHealth,
    retry: false,
  })
  const healthQueryError =
    (healthQuery.error as AxiosError<{ error?: { message?: string } }> | null)?.response?.data?.error
      ?.message ||
    (healthQuery.error as Error | null)?.message ||
    ''

  useEffect(() => {
    if (healthQuery.data) {
      // 健康状态同步进全局 store，面试页打开后可以复用最新一次检查结果。
      setProviderHealth(healthQuery.data)
    }
  }, [healthQuery.data, setProviderHealth])

  useEffect(() => {
    setPendingResumeId(resumeId)
  }, [resumeId])


  /** 查询可选简历。 */
  const resumeQuery = useQuery({
    // 准备页默认加载简历列表，帮助用户直接在表格中绑定简历。
    // page_size 取 50，避免课程项目里频繁翻页影响操作。
    queryKey: ['resumes', 'prepare-picker'],
    queryFn: () => fetchResumes({ page: 1, page_size: 50 }),
  })
  const jdQuery = useQuery({
    // JD 列表只在选择弹窗打开时查询，减少准备页初始请求数量。
    // 过滤条件由岗位方向和标题关键字控制。
    queryKey: ['jds', jdPickerOpen, jdFilterRole, jdFilterTitle],
    queryFn: () =>
      fetchJds({
        job_role: jdFilterRole.trim() || undefined,
        title: jdFilterTitle.trim() || undefined,
      }),
    enabled: jdPickerOpen,
  })
  const toneQuery = useQuery({
    // 语气配置用于 voice 输出模式。
    // 即使当前选择文本模式，也提前加载以便用户切换时立即可选。
    queryKey: ['voice-tone-profiles'],
    queryFn: fetchVoiceToneProfiles,
  })

  useEffect(() => {
    if (jdPickerOpen) {
      // 弹窗打开时主动 refetch，保证用户刚上传的 JD 能出现在列表中。
      void jdQuery.refetch()
    }
  }, [jdPickerOpen, jdQuery])

  /** 查询暂停中的面试。 */
  const pausedQuery = useQuery({
    // 暂停会话列表帮助用户从准备页恢复上次中断的面试。
    // 这里只取第一页最近记录，避免准备页承担完整历史管理职责。
    queryKey: ['paused-interviews'],
    queryFn: () => fetchHistory({ page: 1, page_size: 20, status: 'PAUSED' }),
  })

  const selectedResumeName = useMemo(() => {
    // 根据当前 resumeId 从列表中反查文件名，用于顶部已绑定标签展示。
    // 如果列表尚未返回，就退化显示 resumeId。
    const items = resumeQuery.data?.items ?? []
    const current = items.find((item) => item.resume_id === resumeId)
    return current?.file_name || ''
  }, [resumeId, resumeQuery.data])

  /** 创建面试会话。 */
  const createMutation = useMutation({
    // 创建会话成功后以后端首题为准，不在前端生成默认问题。
    // JD 模式下 variables.job_role 可能为空，因此 fallback 到 currentJobRole。
    mutationFn: createInterview,
    onSuccess: (data, variables) => {
      setSessionConfig({
        interviewId: data.interview_id,
        jobRole: variables.job_role || currentJobRole,
        difficulty: variables.difficulty,
        inputMode: variables.input_mode,
        outputMode: variables.output_mode,
        stage: data.current_stage,
        firstQuestion: data.first_question,
        ttsAudioUrl: data.tts_audio_url,
      })
      message.success('会话创建成功，进入面试页')
      navigate('/interview')
    },
    onError: () => {
      message.error('创建会话失败，请重试')
    },
  })

  /** 恢复暂停面试。 */
  const resumeMutation = useMutation({
    // 恢复会话通过 status 接口拿到当前题目和阶段。
    // 这比本地缓存可靠，因为暂停期间可能已经有其他设备更新过状态。
    mutationFn: (interviewId: string) => fetchInterviewStatus(interviewId, { status: 'ACTIVE' }),
    onSuccess: (data) => {
      setSessionConfig({
        interviewId: data.interview_id,
        jobRole: data.job_role,
        difficulty: data.difficulty,
        inputMode: data.input_mode,
        outputMode: data.output_mode,
        stage: data.current_stage,
        firstQuestion: data.current_question,
        ttsAudioUrl: data.tts_audio_url,
      })
      message.success('已恢复暂停面试')
      navigate('/interview')
    },
    onError: () => {
      message.error('恢复面试失败，请重试')
    },
  })

  return (
    <Card title="面试准备" bordered={false}>
      <div style={{ marginBottom: 16 }}>
        <ProviderHealthBanner
          health={healthQuery.data ?? null}
          loading={healthQuery.isLoading}
          errorMessage={healthQueryError}
        />
      </div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space align="center" wrap>
          <Typography.Text strong>还不想马上开练？</Typography.Text>
          <Typography.Text type="secondary">可以先预约一场，到点后直接进入面试。</Typography.Text>
          <Button onClick={() => navigate('/schedules')}>去预约模拟面试</Button>
        </Space>
      </Card>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Tabs
          activeKey={activeBindingTab}
          onChange={(value) => setActiveBindingTab(value as 'resume' | 'jd')}
          items={[
            {
              key: 'resume',
              label: '简历',
              children: (
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Space>
                    <Typography.Text strong>已绑定简历：</Typography.Text>
                    {resumeId ? (
                      <Tag color="blue">{selectedResumeName ? `${selectedResumeName} (${resumeId})` : resumeId}</Tag>
                    ) : (
                      <Tag color="red">未选择</Tag>
                    )}
                    <Button onClick={() => setResumePickerOpen(true)}>选择简历</Button>
                    <Button onClick={() => navigate('/resumes')}>去上传/管理简历</Button>
                  </Space>
                  <Table
                    rowKey="resume_id"
                    size="small"
                    loading={resumeQuery.isLoading}
                    dataSource={resumeQuery.data?.items ?? []}
                    pagination={false}
                    scroll={{ x: 860 }}
                    columns={[
                      { title: '文件名', dataIndex: 'file_name' },
                      { title: '状态', dataIndex: 'parse_status' },
                      {
                        title: '操作',
                        key: 'actions',
                        render: (_, row: { resume_id: string; file_name: string }) => (
                          <Button
                            size="small"
                            type={resumeId === row.resume_id ? 'default' : 'primary'}
                            onClick={() => {
                              setResumeId(row.resume_id)
                              message.success(`已绑定简历：${row.file_name}`)
                            }}
                          >
                            {resumeId === row.resume_id ? '已绑定' : '绑定'}
                          </Button>
                        ),
                      },
                    ]}
                    locale={{ emptyText: '暂无简历，请先上传。' }}
                  />
                </Space>
              ),
            },
            {
              key: 'jd',
              label: '岗位（JD）',
              children: (
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Space>
                    <Typography.Text strong>已绑定岗位：</Typography.Text>
                    {form.getFieldValue('jd_id') ? (
                      <Tag color="gold">{selectedJdTitle || form.getFieldValue('jd_id')}</Tag>
                    ) : (
                      <Tag>未绑定 JD（仅按方向）</Tag>
                    )}
                    <Button onClick={() => setJdPickerOpen(true)}>选择/上传 JD</Button>
                    <Button
                      onClick={() => {
                        form.setFieldValue('jd_id', '')
                        setPendingJdId('')
                        setSelectedJdTitle('')
                        message.success('已清空 JD 绑定')
                      }}
                    >
                      清空绑定
                    </Button>
                  </Space>
                  <Table
                    rowKey="jd_id"
                    size="small"
                    loading={jdQuery.isLoading}
                    dataSource={jdQuery.data?.items ?? []}
                    pagination={false}
                    scroll={{ x: 900 }}
                    columns={[
                      { title: '标题', dataIndex: 'title' },
                      {
                        title: '来源',
                        dataIndex: 'source_type',
                        render: (value: string) => (value === 'SYSTEM_PRESET' ? '系统预置' : '我的上传'),
                      },
                      {
                        title: '操作',
                        key: 'actions',
                        render: (_, row: { jd_id: string; title: string }) => (
                          <Button
                            size="small"
                            type={form.getFieldValue('jd_id') === row.jd_id ? 'default' : 'primary'}
                            onClick={() => {
                              form.setFieldValue('jd_id', row.jd_id)
                              setPendingJdId(row.jd_id)
                              setSelectedJdTitle(row.title)
                              message.success(`已绑定岗位：${row.title}`)
                            }}
                          >
                            {form.getFieldValue('jd_id') === row.jd_id ? '已绑定' : '绑定'}
                          </Button>
                        ),
                      },
                    ]}
                    locale={{ emptyText: '暂无岗位描述，可上传一份 JD。' }}
                  />
                </Space>
              ),
            },
          ]}
        />
      </Card>
      <Card title="继续暂停的面试" size="small" style={{ marginBottom: 16 }}>
        <Table
          rowKey="interview_id"
          loading={pausedQuery.isLoading}
          dataSource={pausedQuery.data?.items ?? []}
          pagination={false}
          scroll={{ x: 1000 }}
          columns={[
            {
              title: '面试名称',
              dataIndex: 'session_name',
              render: (value?: string) => value || '-',
            },
            { title: '会话ID', dataIndex: 'interview_id' },
            { title: '简历', dataIndex: 'resume_id' },
            { title: '岗位', dataIndex: 'job_role' },
            { title: '难度', dataIndex: 'difficulty' },
            { title: '状态', dataIndex: 'status' },
            {
              title: '操作',
              key: 'actions',
              render: (_, row: { interview_id: string }) => (
                <Button
                  size="small"
                  type="primary"
                  loading={resumeMutation.isPending}
                  onClick={() => resumeMutation.mutate(row.interview_id)}
                >
                  继续面试
                </Button>
              ),
            },
          ]}
          locale={{ emptyText: '暂无暂停中的面试，可直接创建新面试。' }}
        />
      </Card>
      <Form
        layout="vertical"
        initialValues={{
          job_role: 'java',
          difficulty: 'medium',
          input_mode: 'voice',
          output_mode: 'voice',
          voice_tone_id: '',
          session_name: '',
          question_types: ['project', 'technical', 'scenario'],
        }}
        onFinish={(values) => {
          if (!resumeId) {
            message.warning('请先在弹窗中选择简历')
            setResumePickerOpen(true)
            return
          }
          createMutation.mutate({
            resume_id: resumeId,
            job_role: positionMode === 'role' ? values.job_role : undefined,
            difficulty: values.difficulty,
            input_mode: values.input_mode,
            output_mode: values.output_mode,
            session_name: values.session_name,
            question_types: questionTypeOrder.filter((item) => (values.question_types || []).includes(item)),
            jd_id: positionMode === 'jd' ? values.jd_id : undefined,
            voice_tone_id: values.voice_tone_id || undefined,
          })
        }}
        form={form}
      >
        <Form.Item
          name="session_name"
          label="面试名称"
          rules={[{ required: true, whitespace: true, message: '请输入面试名称' }]}
        >
          <Input placeholder="例如：Java后端一面" maxLength={128} />
        </Form.Item>
        <Form.Item name="question_types" label="题目类型">
          <Checkbox.Group
            options={[
              { label: '项目经历', value: 'project' },
              { label: '技术', value: 'technical' },
              { label: '场景', value: 'scenario' },
            ]}
          />
        </Form.Item>
        <Form.Item label="岗位信息模式">
          <Space>
            <Typography.Text>岗位方向</Typography.Text>
            <Switch
              checked={positionMode === 'jd'}
              checkedChildren="JD"
              unCheckedChildren="方向"
              onChange={(checked) => {
                const mode: 'role' | 'jd' = checked ? 'jd' : 'role'
                setPositionMode(mode)
                if (mode === 'role') {
                  form.setFieldValue('jd_id', '')
                  setPendingJdId('')
                  setSelectedJdTitle('')
                }
              }}
            />
            <Typography.Text>岗位描述（JD）</Typography.Text>
          </Space>
        </Form.Item>
        {positionMode === 'role' ? (
          <Form.Item name="job_role" label="岗位方向" rules={[{ required: true, message: '请选择岗位方向' }]}>
            <Select
              onChange={(value: 'java' | 'web') => setCurrentJobRole(value)}
              options={[
                { label: 'Java', value: 'java' },
                { label: 'Web', value: 'web' },
              ]}
            />
          </Form.Item>
        ) : (
          <Form.Item name="jd_id" label="岗位描述（JD）" rules={[{ required: true, whitespace: true, message: '请选择岗位描述' }]}>
            <Space>
              {form.getFieldValue('jd_id') ? (
                <Tag color="gold">{selectedJdTitle || form.getFieldValue('jd_id')}</Tag>
              ) : (
                <Tag color="red">未选择 JD</Tag>
              )}
              <Button
                onClick={() => setJdPickerOpen(true)}
              >
                选择 JD
              </Button>
            </Space>
          </Form.Item>
        )}
        <Form.Item name="difficulty" label="难度">
          <Radio.Group
            options={[
              { label: '简单', value: 'easy' },
              { label: '中等', value: 'medium' },
              { label: '困难', value: 'hard' },
            ]}
          />
        </Form.Item>
        <Form.Item name="input_mode" label="输入模式">
          <Radio.Group
            options={[
              { label: '文本', value: 'text' },
              { label: '语音', value: 'voice' },
            ]}
          />
        </Form.Item>
        <Form.Item name="output_mode" label="输出模式">
          <Radio.Group
            options={[
              { label: '文本', value: 'text' },
              { label: '语音', value: 'voice' },
            ]}
          />
        </Form.Item>
        <Form.Item
          shouldUpdate={(prev, next) => prev.output_mode !== next.output_mode}
          noStyle
        >
          {({ getFieldValue }) =>
            getFieldValue('output_mode') === 'voice' ? (
              <Form.Item name="voice_tone_id" label="面试官语气">
                <Select
                  loading={toneQuery.isLoading}
                  allowClear
                  placeholder="请选择语气（不选则使用默认）"
                  options={(toneQuery.data?.items || []).map((item) => ({
                    label: `${item.tone_name}（x${item.speed.toFixed(2)}）`,
                    value: item.tone_id,
                  }))}
                />
              </Form.Item>
            ) : null
          }
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={createMutation.isPending}>
          创建会话
        </Button>
      </Form>
      <Modal
        title="选择本次面试简历"
        open={resumePickerOpen}
        onCancel={() => setResumePickerOpen(false)}
        onOk={() => {
          if (!pendingResumeId) {
            message.warning('请选择一份简历')
            return
          }
          setResumeId(pendingResumeId)
          setResumePickerOpen(false)
          message.success('已绑定简历')
        }}
        okText="确认绑定"
        cancelText="取消"
      >
        <Table
          rowKey="resume_id"
          loading={resumeQuery.isLoading}
          dataSource={resumeQuery.data?.items ?? []}
          pagination={false}
          scroll={{ x: 860 }}
          onRow={(record) => ({
            onClick: () => setPendingResumeId(record.resume_id),
          })}
          rowSelection={{
            type: 'radio',
            selectedRowKeys: pendingResumeId ? [pendingResumeId] : [],
            onChange: (keys) => {
              setPendingResumeId(String(keys[0] || ''))
            },
          }}
          columns={[
            { title: '文件名', dataIndex: 'file_name' },
            { title: '状态', dataIndex: 'parse_status' },
            { title: '创建时间', dataIndex: 'created_at' },
          ]}
          locale={{ emptyText: '暂无简历，请先去简历管理页上传。' }}
        />
      </Modal>
      <Modal
        title="选择岗位描述（JD）"
        open={jdPickerOpen}
        onCancel={() => setJdPickerOpen(false)}
        onOk={() => {
          form.setFieldValue('jd_id', pendingJdId)
          const item = (jdQuery.data?.items || []).find((row) => row.jd_id === pendingJdId)
          setSelectedJdTitle(item?.title || '')
          setJdPickerOpen(false)
          message.success('已绑定 JD')
        }}
        okText="确认绑定"
        cancelText="取消"
        width="min(1100px, 92vw)"
        styles={{ body: { height: 640, overflow: 'hidden' } }}
      >
        <Space direction="vertical" style={{ width: '100%', height: '100%' }}>
          <Space wrap style={{ width: '100%' }}>
            <Input
              placeholder="按 job_role 搜索，例如：java / web / 后端开发"
              value={jdFilterRole}
              onChange={(event) => setJdFilterRole(event.target.value)}
              style={{ width: 'min(320px, 100%)' }}
            />
            <Input
              placeholder="按标题关键词搜索"
              value={jdFilterTitle}
              onChange={(event) => setJdFilterTitle(event.target.value)}
              style={{ width: 'min(320px, 100%)' }}
            />
            <Button onClick={() => void jdQuery.refetch()}>搜索</Button>
            <Button
              onClick={() => {
                setJdFilterRole('')
                setJdFilterTitle('')
              }}
            >
              清空筛选
            </Button>
          </Space>
          <Input
            placeholder="上传 JD 时可填写标题（可选）"
            value={jdUploadTitle}
            onChange={(event) => setJdUploadTitle(event.target.value)}
          />
          <Upload
            showUploadList={false}
            customRequest={async (options) => {
              const file = options.file as File
              try {
                await uploadJd({ file, job_role: currentJobRole, title: jdUploadTitle.trim() || undefined })
                message.success('JD 上传成功')
                setJdUploadTitle('')
                await jdQuery.refetch()
                options.onSuccess?.({}, file)
              } catch (error) {
                message.error('JD 上传失败，请重试')
                options.onError?.(error as Error)
              }
            }}
          >
            <Button>上传我的 JD</Button>
          </Upload>
        </Space>
        <Table
          rowKey="jd_id"
          loading={jdQuery.isLoading}
          dataSource={jdQuery.data?.items || []}
          pagination={false}
          scroll={{ x: 1000, y: 420 }}
          onRow={(record) => ({
            onClick: () => setPendingJdId(record.jd_id),
          })}
          rowSelection={{
            type: 'radio',
            selectedRowKeys: [pendingJdId],
            onChange: (keys) => setPendingJdId(String(keys[0] || '')),
          }}
          columns={[
            {
              title: '标题',
              dataIndex: 'title',
            },
            {
              title: '公司',
              dataIndex: 'company_name',
              render: (value: string) => value || '-',
            },
            {
              title: '来源',
              dataIndex: 'source_type',
              render: (value: string) => (value === 'SYSTEM_PRESET' ? '系统预置' : value === 'USER_UPLOAD' ? '我的上传' : '-'),
            },
            {
              title: '方向',
              dataIndex: 'job_role',
            },
            {
              title: '内容摘要',
              dataIndex: 'content_text',
              render: (value: string) => (
                <Typography.Paragraph style={{ marginBottom: 0 }} ellipsis={{ rows: 2, expandable: false }}>
                  {value || '-'}
                </Typography.Paragraph>
              ),
            },
            {
              title: '更新时间',
              dataIndex: 'updated_at',
            },
          ]}
        />
      </Modal>
    </Card>
  )
}
