import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Card, Col, Input, Modal, Popconfirm, Row, Select, Space, Tag, Typography, message } from 'antd'
import { AxiosError } from 'axios'
import { useMemo, useState } from 'react'

import { deleteJd, fetchCompanies, fetchJds, uploadJd } from '../api/interview'

// 岗位库页面：
// 1. 管理用户自建 JD，也展示系统预置 JD 供面试选择。
// 2. 支持按岗位、标题关键字和公司筛选，减少长列表查找成本。
// 3. 新建 JD 可以直接输入文本，后端负责保存为岗位描述记录。
// 4. 删除操作只针对用户有权限的 JD，系统预置数据由后端保护。
// 5. 公司列表用于给 JD 绑定来源公司，便于后续按公司筛选。

/** 岗位管理页面。 */
export function JobManagePage() {
  const queryClient = useQueryClient()
  const [jobRole, setJobRole] = useState('后端开发')
  const [titleInput, setTitleInput] = useState('')
  const [textInput, setTextInput] = useState('')
  const [searchTitle, setSearchTitle] = useState('')
  const [searchKeyword, setSearchKeyword] = useState('')
  const [searchCompanyId, setSearchCompanyId] = useState('')
  const [createCompanyId, setCreateCompanyId] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [detailOpen, setDetailOpen] = useState(false)
  const [activeJd, setActiveJd] = useState<null | {
    jd_id: string
    title: string
    source_type: 'SYSTEM_PRESET' | 'USER_UPLOAD'
    company_id: string
    company_name: string
    job_role: string
    content_text: string
    created_at: string
  }>(null)

  /** 查询 JD 列表。 */
  const jdQuery = useQuery({
    queryKey: ['jds', 'manage', jobRole, searchKeyword],
    queryFn: () => fetchJds({ job_role: jobRole.trim() || undefined, title: searchKeyword || undefined }),
  })
  const companiesQuery = useQuery({
    queryKey: ['companies', 'manage'],
    queryFn: fetchCompanies,
  })

  const sortedItems = useMemo(() => {
    const items = (jdQuery.data?.items ?? []).filter((item) => (searchCompanyId ? item.company_id === searchCompanyId : true))
    return [...items].sort((a, b) => {
      if (a.source_type === b.source_type) return 0
      return a.source_type === 'SYSTEM_PRESET' ? -1 : 1
    })
  }, [jdQuery.data?.items, searchCompanyId])

  /** 文本上传 JD。 */
  const uploadTextMutation = useMutation({
    mutationFn: () =>
      uploadJd({
        job_role: jobRole,
        title: titleInput.trim() || undefined,
        content_text: textInput.trim(),
        company_id: createCompanyId || undefined,
      }),
    onSuccess: async () => {
      setTitleInput('')
      setTextInput('')
      setCreateCompanyId('')
      setCreateOpen(false)
      await queryClient.invalidateQueries({ queryKey: ['jds'] })
      message.success('岗位描述已保存')
    },
    onError: (error) => {
      const axiosError = error as AxiosError<{ error?: { message?: string } }>
      message.error(axiosError.response?.data?.error?.message || '岗位描述保存失败')
    },
  })

  /** 删除 JD。 */
  const deleteMutation = useMutation({
    mutationFn: deleteJd,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['jds'] })
      message.success('岗位描述已删除')
    },
    onError: (error) => {
      const axiosError = error as AxiosError<{ error?: { message?: string } }>
      message.error(axiosError.response?.data?.error?.message || '岗位描述删除失败')
    },
  })

  return (
    <Card
      title="岗位管理"
      bordered={false}
      style={{
        background: 'linear-gradient(140deg, #f5f9ff 0%, #eef6f1 60%, #fff7ea 100%)',
      }}
    >
      <Typography.Paragraph>岗位描述支持直接文本录入。点击下方卡片可查看详情。</Typography.Paragraph>
      <Card size="small" style={{ marginBottom: 16, borderRadius: 12 }}>
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Space style={{ justifyContent: 'space-between', width: '100%' }} wrap>
            <Space wrap>
              <Select
                showSearch
                style={{ width: 'min(220px, 100%)' }}
                value={jobRole}
                onChange={(value) => setJobRole(value)}
                options={[
                  { label: '后端开发', value: '后端开发' },
                  { label: '前端开发', value: '前端开发' },
                  { label: '算法', value: '算法' },
                  { label: '产品', value: '产品' },
                  { label: '运营', value: '运营' },
                  { label: '市场', value: '市场' },
                  { label: '金融', value: '金融' },
                  { label: '咨询', value: '咨询' },
                  { label: '风控', value: '风控' },
                  { label: '数据开发', value: '数据开发' },
                  { label: '数据标注', value: '数据标注' },
                ]}
              />
              <Input
                style={{ width: 'min(220px, 100%)' }}
                placeholder="自定义岗位方向"
                value={jobRole}
                onChange={(event) => setJobRole(event.target.value)}
              />
              <Input.Search
                allowClear
                style={{ width: 'min(320px, 100%)' }}
                placeholder="搜索岗位名称"
                value={searchTitle}
                onChange={(event) => setSearchTitle(event.target.value)}
                onSearch={(value) => setSearchKeyword(value.trim())}
              />
              <Select
                allowClear
                style={{ width: 'min(220px, 100%)' }}
                placeholder="按公司筛选"
                value={searchCompanyId || undefined}
                onChange={(value) => setSearchCompanyId(value || '')}
                options={(companiesQuery.data?.items || []).map((item) => ({ label: item.name, value: item.company_id }))}
              />
            </Space>
            <Button type="primary" onClick={() => setCreateOpen(true)}>
              新增岗位描述
            </Button>
          </Space>
        </Space>
      </Card>

      <Row gutter={[16, 16]}>
        {sortedItems.map((item) => (
          <Col key={item.jd_id} xs={24} sm={12} lg={8}>
            <Card
              hoverable
              onClick={() => {
                setActiveJd(item)
                setDetailOpen(true)
              }}
              style={{
                height: '100%',
                borderRadius: 14,
                border: item.source_type === 'SYSTEM_PRESET' ? '1px solid #91caff' : '1px solid #ffd591',
                background:
                  item.source_type === 'SYSTEM_PRESET'
                    ? 'linear-gradient(160deg, #f0f5ff 0%, #ffffff 100%)'
                    : 'linear-gradient(160deg, #fff7e6 0%, #ffffff 100%)',
              }}
              bodyStyle={{ display: 'flex', flexDirection: 'column', gap: 8 }}
            >
              <Space>
                <Tag color={item.source_type === 'SYSTEM_PRESET' ? 'blue' : 'gold'}>
                  {item.source_type === 'SYSTEM_PRESET' ? '系统预置' : '我的上传'}
                </Tag>
                <Tag>{item.job_role.toUpperCase()}</Tag>
                {item.company_name ? <Tag color="purple">{item.company_name}</Tag> : null}
              </Space>
              <Typography.Title level={5} style={{ margin: 0 }}>
                {item.title}
              </Typography.Title>
              <Typography.Paragraph
                style={{ marginBottom: 0, minHeight: 66 }}
                ellipsis={{ rows: 3, tooltip: false }}
              >
                {item.content_text || '暂无内容'}
              </Typography.Paragraph>
              <Space style={{ justifyContent: 'space-between', width: '100%' }}>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {item.created_at}
                </Typography.Text>
                {item.source_type === 'USER_UPLOAD' ? (
                  <Popconfirm
                    title="确认删除该岗位描述？"
                    description="删除后将无法在新面试中继续绑定。"
                    okText="删除"
                    cancelText="取消"
                    onConfirm={(event) => {
                      event?.stopPropagation()
                      deleteMutation.mutate(item.jd_id)
                    }}
                    onCancel={(event) => event?.stopPropagation()}
                  >
                    <Button
                      size="small"
                      danger
                      loading={deleteMutation.isPending}
                      onClick={(event) => event.stopPropagation()}
                    >
                      删除
                    </Button>
                  </Popconfirm>
                ) : (
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    不可删除
                  </Typography.Text>
                )}
              </Space>
            </Card>
          </Col>
        ))}
      </Row>
      {!jdQuery.isLoading && sortedItems.length === 0 ? (
        <Card size="small" style={{ marginTop: 16 }}>
          <Typography.Text type="secondary">当前方向暂无岗位描述，可先在上方文本框录入。</Typography.Text>
        </Card>
      ) : null}

      <Modal
        title="新增岗位描述"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={() => uploadTextMutation.mutate()}
        okText="保存"
        cancelText="取消"
        confirmLoading={uploadTextMutation.isPending}
        okButtonProps={{ disabled: !textInput.trim() || !jobRole.trim() }}
        width="min(760px, 92vw)"
      >
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Typography.Text type="secondary">当前方向：{jobRole}</Typography.Text>
          <Input
            value={titleInput}
            onChange={(event) => setTitleInput(event.target.value)}
            placeholder="岗位标题（可选，例如：资深Java后端工程师）"
            maxLength={128}
          />
          <Select
            allowClear
            placeholder="选择所属公司（可选）"
            value={createCompanyId || undefined}
            onChange={(value) => setCreateCompanyId(value || '')}
            options={(companiesQuery.data?.items || []).map((item) => ({ label: item.name, value: item.company_id }))}
          />
          <Input.TextArea
            value={textInput}
            onChange={(event) => setTextInput(event.target.value)}
            placeholder="请输入岗位描述文本，例如职责、技能要求、加分项等..."
            autoSize={{ minRows: 7, maxRows: 14 }}
            maxLength={12000}
            showCount
          />
        </Space>
      </Modal>

      <Modal
        title={activeJd?.title || '岗位详情'}
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        footer={null}
        width="min(760px, 92vw)"
      >
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Space>
            <Tag color={activeJd?.source_type === 'SYSTEM_PRESET' ? 'blue' : 'gold'}>
              {activeJd?.source_type === 'SYSTEM_PRESET' ? '系统预置' : '我的上传'}
            </Tag>
            <Tag>{activeJd?.job_role?.toUpperCase()}</Tag>
            {activeJd?.company_name ? <Tag color="purple">{activeJd.company_name}</Tag> : null}
            <Typography.Text type="secondary">{activeJd?.created_at}</Typography.Text>
          </Space>
          <Card size="small" style={{ maxHeight: 420, overflowY: 'auto', borderRadius: 10 }}>
            <Typography.Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>
              {activeJd?.content_text || '暂无岗位描述内容'}
            </Typography.Paragraph>
          </Card>
        </Space>
      </Modal>
    </Card>
  )
}
