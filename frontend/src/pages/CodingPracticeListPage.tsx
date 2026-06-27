import { useMutation, useQuery } from '@tanstack/react-query'
import { Button, Card, Col, List, Row, Space, Tag, Typography, message } from 'antd'
import { useNavigate } from 'react-router-dom'

import { createCodingPracticeSession, fetchCodingPracticeQuestions, type CodingPracticeQuestionSummary } from '../api/codingPractice'
import { parseApiError } from '../api/client'

// 编程练习列表页：
// 1. 展示题目难度、标签和当前用户进度。
// 2. 点击题目先创建或恢复后端 session，再跳转到编辑器页面。
// 3. 列表数据已经包含最新提交状态，页面无需额外请求记录接口。
// 4. 错误统一走 parseApiError，保持和其他业务页一致的提示方式。

const DIFFICULTY_COLOR: Record<'easy' | 'medium' | 'hard', string> = {
  easy: 'green',
  medium: 'orange',
  hard: 'red',
}

const STATUS_LABEL: Record<string, string> = {
  NOT_STARTED: '未开始',
  ACTIVE: '进行中',
  SOLVED: '已通过',
}

export function CodingPracticeListPage() {
  const navigate = useNavigate()
  const questionsQuery = useQuery({
    // 题目列表相对稳定，React Query 会在页面返回时复用缓存并按需刷新。
    queryKey: ['coding-practice-questions'],
    queryFn: fetchCodingPracticeQuestions,
  })

  const createSessionMutation = useMutation({
    mutationFn: createCodingPracticeSession,
    onSuccess: (data) => {
      navigate(`/coding-practice/${data.session_id}`)
    },
    onError: (error) => {
      const parsed = parseApiError(error)
      message.error(parsed.message)
    },
  })

  const handleOpen = (item: CodingPracticeQuestionSummary) => {
    if (item.session_id) {
      navigate(`/coding-practice/${item.session_id}`)
      return
    }
    createSessionMutation.mutate(item.question_id)
  }

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card>
        <Typography.Title level={2} style={{ marginTop: 0, marginBottom: 8 }}>
          编程练习
        </Typography.Title>
        <Typography.Paragraph style={{ marginBottom: 0, color: '#5e697a' }}>
          浏览中文算法题，支持 C++、Java、JavaScript 在线编写、运行自测与提交判题。
        </Typography.Paragraph>
      </Card>
      <Card loading={questionsQuery.isLoading}>
        <List
          dataSource={questionsQuery.data?.items || []}
          renderItem={(item) => (
            <List.Item key={item.question_id}>
              <Row gutter={[12, 12]} style={{ width: '100%' }} align="middle">
                <Col flex="auto">
                  <Space direction="vertical" size={6} style={{ width: '100%' }}>
                    <Space wrap>
                      <Typography.Text strong>{item.title}</Typography.Text>
                      <Tag color={DIFFICULTY_COLOR[item.difficulty]}>{item.difficulty.toUpperCase()}</Tag>
                      <Tag color={item.status === 'SOLVED' ? 'success' : item.status === 'ACTIVE' ? 'processing' : 'default'}>
                        {STATUS_LABEL[item.status]}
                      </Tag>
                    </Space>
                    <Space wrap>
                      {item.topic_tags.map((tag) => (
                        <Tag key={tag}>{tag}</Tag>
                      ))}
                    </Space>
                    <Typography.Text type="secondary">
                      最近语言：{item.last_language.toUpperCase()}
                      {item.latest_submission_status ? ` · 最近结果：${item.latest_submission_status}` : ''}
                    </Typography.Text>
                  </Space>
                </Col>
                <Col>
                  <Button type="primary" onClick={() => handleOpen(item)} loading={createSessionMutation.isPending}>
                    {item.status === 'NOT_STARTED' ? '开始练习' : '继续练习'}
                  </Button>
                </Col>
              </Row>
            </List.Item>
          )}
        />
      </Card>
    </Space>
  )
}
