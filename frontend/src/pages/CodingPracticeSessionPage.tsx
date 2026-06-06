import Editor from '@monaco-editor/react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Alert, Button, Card, Col, Radio, Row, Space, Spin, Tag, Typography, message } from 'antd'
import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import {
  fetchCodingPracticeSession,
  runCodingPracticeSelfTest,
  submitCodingPracticeSolution,
  type CodingLanguage,
} from '../api/codingPractice'
import { parseApiError } from '../api/client'
import { useCodingPracticeStore } from '../stores/codingPracticeStore'

const LANGUAGE_LABELS: Record<CodingLanguage, string> = {
  cpp: 'C++11',
  java: 'Java 21',
  javascript: 'JavaScript',
}

const LANGUAGE_EDITOR_MODE: Record<CodingLanguage, string> = {
  cpp: 'cpp',
  java: 'java',
  javascript: 'javascript',
}

export function CodingPracticeSessionPage() {
  const navigate = useNavigate()
  const { sessionId = '' } = useParams<{ sessionId: string }>()
  const {
    question,
    activeLanguage,
    activeCode,
    executionResult,
    setSession,
    setActiveLanguage,
    setActiveCode,
    setExecutionResult,
  } = useCodingPracticeStore((state) => state)

  const sessionQuery = useQuery({
    queryKey: ['coding-practice-session', sessionId],
    queryFn: () => fetchCodingPracticeSession(sessionId),
    enabled: Boolean(sessionId),
  })

  useEffect(() => {
    if (sessionQuery.data) {
      setSession(sessionQuery.data)
    }
  }, [sessionQuery.data, setSession])

  const runMutation = useMutation({
    mutationFn: () => runCodingPracticeSelfTest(sessionId, { language: activeLanguage, source_code: activeCode }),
    onSuccess: (data) => {
      setExecutionResult(data.result)
      message.success('自测已完成')
    },
    onError: (error) => {
      const parsed = parseApiError(error)
      message.error(parsed.message)
    },
  })

  const submitMutation = useMutation({
    mutationFn: () => submitCodingPracticeSolution(sessionId, { language: activeLanguage, source_code: activeCode }),
    onSuccess: (data) => {
      setExecutionResult(data.result)
      message.success(data.result.status === 'ACCEPTED' ? '提交通过' : '提交完成')
    },
    onError: (error) => {
      const parsed = parseApiError(error)
      message.error(parsed.message)
    },
  })

  if (sessionQuery.isLoading) {
    return (
      <Card>
        <Spin />
      </Card>
    )
  }

  if (!question) {
    return (
      <Card>
        <Typography.Text>练习加载失败，请返回列表重试。</Typography.Text>
      </Card>
    )
  }

  return (
    <Row gutter={[16, 16]} style={{ width: '100%' }}>
      <Col xs={24} xl={10}>
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Card
            title={question.title}
            extra={
              <Space>
                <Tag color="blue">{question.difficulty.toUpperCase()}</Tag>
                <Button onClick={() => navigate('/coding-practice')}>返回列表</Button>
              </Space>
            }
          >
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <Space wrap>
                {question.topic_tags.map((tag) => (
                  <Tag key={tag}>{tag}</Tag>
                ))}
              </Space>
              <Typography.Paragraph>{question.prompt_markdown}</Typography.Paragraph>
              <Typography.Title level={5}>输入说明</Typography.Title>
              <Typography.Paragraph>{question.input_spec}</Typography.Paragraph>
              <Typography.Title level={5}>输出说明</Typography.Title>
              <Typography.Paragraph>{question.output_spec}</Typography.Paragraph>
              <Typography.Title level={5}>约束</Typography.Title>
              <Typography.Paragraph>{question.constraints_text}</Typography.Paragraph>
              <Typography.Title level={5}>样例</Typography.Title>
              {question.sample_cases.map((item, index) => (
                <Card key={`${item.input}-${index}`} size="small">
                  <Typography.Text strong>输入</Typography.Text>
                  <pre>{item.input}</pre>
                  <Typography.Text strong>输出</Typography.Text>
                  <pre>{item.output}</pre>
                </Card>
              ))}
              <Alert
                type="info"
                showIcon
                message="自测用例"
                description={
                  <Space direction="vertical" size={4} style={{ width: '100%' }}>
                    <Typography.Text>输入：</Typography.Text>
                    <pre>{question.self_test_case.input}</pre>
                    <Typography.Text>期望输出：</Typography.Text>
                    <pre>{question.self_test_case.output}</pre>
                  </Space>
                }
              />
            </Space>
          </Card>
        </Space>
      </Col>
      <Col xs={24} xl={14}>
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Card>
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <Space wrap style={{ justifyContent: 'space-between', width: '100%' }}>
                <Radio.Group
                  value={activeLanguage}
                  onChange={(event) => setActiveLanguage(event.target.value)}
                  options={[
                    { label: 'C++11', value: 'cpp' },
                    { label: 'Java 21', value: 'java' },
                    { label: 'JavaScript', value: 'javascript' },
                  ]}
                />
                <Space>
                  <Tag>仅当前页面暂存</Tag>
                  <Button onClick={() => runMutation.mutate()} loading={runMutation.isPending}>
                    运行自测
                  </Button>
                  <Button type="primary" onClick={() => submitMutation.mutate()} loading={submitMutation.isPending}>
                    提交判题
                  </Button>
                </Space>
              </Space>
              <Typography.Text type="secondary">当前语言：{LANGUAGE_LABELS[activeLanguage]}</Typography.Text>
              <div style={{ border: '1px solid #d9e2f2', borderRadius: 12, overflow: 'hidden' }}>
                <Editor
                  height="60vh"
                  language={LANGUAGE_EDITOR_MODE[activeLanguage]}
                  value={activeCode}
                  onChange={(value) => setActiveCode(value || '')}
                  theme="vs-dark"
                  options={{
                    automaticLayout: true,
                    minimap: { enabled: false },
                    fontSize: 14,
                    wordWrap: 'on',
                    scrollBeyondLastLine: false,
                  }}
                />
              </div>
            </Space>
          </Card>
          <Card title="运行结果">
            {executionResult ? (
              <Space direction="vertical" size={10} style={{ width: '100%' }}>
                <Space wrap>
                  <Tag color={executionResult.status === 'ACCEPTED' ? 'success' : 'error'}>{executionResult.status}</Tag>
                  <Tag>{executionResult.submit_type}</Tag>
                  <Tag>
                    通过 {executionResult.passed_count}/{executionResult.total_count}
                  </Tag>
                </Space>
                <Typography.Text>{executionResult.message}</Typography.Text>
                {executionResult.compile_output ? <pre>{executionResult.compile_output}</pre> : null}
                {executionResult.results.map((item, index) => (
                  <Card key={index} size="small">
                    <pre>{JSON.stringify(item, null, 2)}</pre>
                  </Card>
                ))}
              </Space>
            ) : (
              <Typography.Text type="secondary">尚未运行。</Typography.Text>
            )}
          </Card>
        </Space>
      </Col>
    </Row>
  )
}
