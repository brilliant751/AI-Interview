import { useMutation } from '@tanstack/react-query'
import { Button, Card, Typography, Upload, message } from 'antd'
import type { UploadFile } from 'antd'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { uploadResume } from '../api/interview'
import { useInterviewStore } from '../stores/interviewStore'

/** 简历上传页面。 */
export function ResumeUploadPage() {
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const navigate = useNavigate()
  const setResumeId = useInterviewStore((state) => state.setResumeId)

  /** 上传动作。 */
  const uploadMutation = useMutation({
    mutationFn: async () => {
      const currentFile = fileList[0]?.originFileObj
      if (!currentFile) {
        throw new Error('请先选择简历文件')
      }
      return uploadResume(currentFile)
    },
    onSuccess: (data) => {
      setResumeId(data.resume_id)
      message.success('简历上传成功，进入准备环节')
      navigate('/prepare')
    },
    onError: (error: Error) => {
      message.error(error.message || '简历上传失败')
    },
  })

  return (
    <Card title="上传简历" bordered={false}>
      <Typography.Paragraph>支持 PDF 文件，上传后将用于面试上下文构建。</Typography.Paragraph>
      <Upload
        beforeUpload={() => false}
        fileList={fileList}
        onChange={(event) => setFileList(event.fileList.slice(-1))}
        accept=".pdf"
      >
        <Button>选择文件</Button>
      </Upload>
      <Button
        type="primary"
        style={{ marginTop: 16 }}
        loading={uploadMutation.isPending}
        onClick={() => uploadMutation.mutate()}
      >
        开始解析并继续
      </Button>
    </Card>
  )
}

