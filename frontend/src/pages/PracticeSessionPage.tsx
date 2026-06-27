import { useMutation, useQuery } from '@tanstack/react-query'
import { Button, Card, Input, Progress, Radio, Space, Tag, Typography, message } from 'antd'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { fetchPracticeSession, finishPracticeSession, submitPracticeAnswer } from '../api/practice'
import { parseApiError } from '../api/client'
import { usePracticeStore } from '../stores/practiceStore'

// 题库练习作答页：
// 1. 进入页面先根据 URL practiceId 拉取服务端会话快照。
// 2. 当前题、已完成数和下一题都以后端响应为准。
// 3. 提交后清空本地输入框，并用 applyAnswerResult 更新进度。
// 4. 手动结束会话后刷新状态，避免继续提交已结束练习。

/** 题库练习作答页。 */
export function PracticeSessionPage() {
  const navigate = useNavigate()
  const { practiceId = '' } = useParams<{ practiceId: string }>()
  const [answerText, setAnswerText] = useState('')
  const {
    status,
    mode,
    totalQuestions,
    completedCount,
    currentQuestion,
    questionStrategy,
    setSession,
    applyAnswerResult,
  } = usePracticeStore((state) => state)

  /** 拉取当前练习会话。 */
  const sessionQuery = useQuery({
    queryKey: ['practice-session', practiceId],
    queryFn: () => fetchPracticeSession(practiceId),
    enabled: Boolean(practiceId),
  })

  useEffect(() => {
    if (sessionQuery.data) {
      setSession(sessionQuery.data)
    }
  }, [sessionQuery.data, setSession])

  /** 提交当前答案。 */
  const answerMutation = useMutation({
    mutationFn: () =>
      submitPracticeAnswer(practiceId, {
        session_question_id: currentQuestion?.session_question_id || '',
        answer_text: answerText,
      }),
    onSuccess: (data) => {
      applyAnswerResult(data)
      setAnswerText('')
      if (data.finished) {
        message.success('练习已完成')
        navigate(`/practice/${practiceId}/records`)
        return
      }
      message.success('已进入下一题')
    },
    onError: (error) => {
      const parsed = parseApiError(error)
      message.error(parsed.message)
    },
  })

  /** 主动结束练习。 */
  const finishMutation = useMutation({
    mutationFn: () => finishPracticeSession(practiceId),
    onSuccess: (data) => {
      setSession(data)
      message.success('练习已结束')
      navigate(`/practice/${practiceId}/records`)
    },
    onError: (error) => {
      const parsed = parseApiError(error)
      message.error(parsed.message)
    },
  })

  if (sessionQuery.isLoading) {
    return <Card title="题库练习">加载中...</Card>
  }

  if (sessionQuery.isError) {
    return <Card title="题库练习">练习加载失败，请返回重试。</Card>
  }

  const optionItems = Array.isArray(currentQuestion?.options) ? currentQuestion.options : []

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card title="练习进度">
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Space wrap>
            <Tag color="blue">模式：{mode}</Tag>
            <Tag color="gold">推进策略：{questionStrategy}</Tag>
            <Tag color={status === 'FINISHED' ? 'success' : 'processing'}>状态：{status}</Tag>
          </Space>
          <Progress percent={totalQuestions ? Math.round((completedCount / totalQuestions) * 100) : 0} />
          <Typography.Text>
            已完成 {completedCount} / {totalQuestions}
          </Typography.Text>
        </Space>
      </Card>

      <Card
        title={currentQuestion ? `第 ${currentQuestion.question_order} 题` : '练习结束'}
        extra={
          <Space>
            <Button onClick={() => navigate(`/practice/${practiceId}/records`)}>查看记录</Button>
            <Button danger loading={finishMutation.isPending} onClick={() => finishMutation.mutate()}>
              结束练习
            </Button>
          </Space>
        }
      >
        {currentQuestion ? (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Space wrap>
              {currentQuestion.category ? <Tag color="purple">类别：{currentQuestion.category}</Tag> : null}
              {currentQuestion.analysis ? <Tag color="cyan">含解析快照</Tag> : null}
            </Space>
            <Typography.Paragraph style={{ fontSize: 16, marginBottom: 0 }}>{currentQuestion.stem}</Typography.Paragraph>
            {optionItems.length ? (
              <Radio.Group
                style={{ width: '100%' }}
                value={answerText}
                onChange={(event) => setAnswerText(String(event.target.value || ''))}
              >
                <Space direction="vertical" size={10} style={{ width: '100%' }}>
                  {optionItems.map((option) => (
                    <Radio key={`${option.key}-${option.text}`} value={option.key}>
                      {option.key}. {option.text}
                    </Radio>
                  ))}
                </Space>
              </Radio.Group>
            ) : (
              <Input.TextArea
                rows={8}
                value={answerText}
                onChange={(event) => setAnswerText(event.target.value)}
                placeholder="输入你的回答"
              />
            )}
            <Button
              type="primary"
              loading={answerMutation.isPending}
              disabled={!answerText.trim()}
              onClick={() => answerMutation.mutate()}
            >
              提交并进入下一题
            </Button>
          </Space>
        ) : (
          <Space direction="vertical">
            <Typography.Text>本次练习已结束。</Typography.Text>
            <Button type="primary" onClick={() => navigate(`/practice/${practiceId}/records`)}>
              查看练习记录
            </Button>
          </Space>
        )}
      </Card>
    </Space>
  )
}
