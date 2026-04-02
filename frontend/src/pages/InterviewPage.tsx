import { useMutation } from '@tanstack/react-query'
import { Button, Card, Input, Space, Tag, Typography, message } from 'antd'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { finishInterview, submitTurn } from '../api/interview'
import { useInterviewStore } from '../stores/interviewStore'

/** 面试答题页面。 */
export function InterviewPage() {
  const navigate = useNavigate()
  const [answer, setAnswer] = useState('')
  const {
    interviewId,
    currentStage,
    currentQuestion,
    liveScore,
    followUpCount,
    outputMode,
    updateTurnResult,
  } = useInterviewStore((state) => state)

  /** 提交轮次。 */
  const submitMutation = useMutation({
    mutationFn: async () =>
      submitTurn(interviewId, {
        stage: currentStage,
        answer_text: answer,
      }),
    onSuccess: (data) => {
      updateTurnResult({
        stage: data.stage,
        question: data.next_question,
        score: data.live_score,
        followUpCount: data.follow_up_count,
      })
      setAnswer('')
      message.success('已生成下一题')
    },
    onError: () => {
      message.error('提交失败，请重试')
    },
  })

  /** 结束面试。 */
  const finishMutation = useMutation({
    mutationFn: () => finishInterview(interviewId),
    onSuccess: () => {
      message.success('面试已结束，正在生成报告')
      navigate('/report')
    },
    onError: () => message.error('结束面试失败'),
  })

  if (!interviewId) {
    return (
      <Card>
        <Typography.Text>尚未创建会话，请先完成简历上传和准备步骤。</Typography.Text>
        <div style={{ marginTop: 12 }}>
          <Button type="primary" onClick={() => navigate('/upload')}>
            去上传
          </Button>
        </div>
      </Card>
    )
  }

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card>
        <Space wrap>
          <Tag color="blue">阶段：{currentStage}</Tag>
          <Tag color="green">实时分：{liveScore}</Tag>
          <Tag color="gold">追问次数：{followUpCount}</Tag>
          <Tag color="purple">输出模式：{outputMode}</Tag>
        </Space>
      </Card>
      <Card title="当前问题">
        <Typography.Paragraph style={{ marginBottom: 0 }}>{currentQuestion || '等待题目生成...'}</Typography.Paragraph>
      </Card>
      <Card title="你的回答">
        <Input.TextArea
          rows={6}
          value={answer}
          onChange={(event) => setAnswer(event.target.value)}
          placeholder="输入你的回答"
        />
        <Space style={{ marginTop: 12 }}>
          <Button type="primary" loading={submitMutation.isPending} onClick={() => submitMutation.mutate()}>
            提交回答
          </Button>
          <Button danger loading={finishMutation.isPending} onClick={() => finishMutation.mutate()}>
            结束面试
          </Button>
        </Space>
      </Card>
    </Space>
  )
}

