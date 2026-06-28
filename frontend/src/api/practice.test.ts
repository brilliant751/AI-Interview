import { afterEach, describe, expect, test, vi } from 'vitest'

import { apiClient } from './client'
import {
  createPracticeSession,
  fetchAdminQuestionBank,
  fetchPracticeImportTask,
  fetchPracticeOverview,
  fetchPracticeRecords,
  fetchPracticeSession,
  fetchPracticeSessionRecords,
  finishPracticeSession,
  submitPracticeAnswer,
  uploadQuestionBankMarkdown,
} from './practice'

// practice API 测试通过 spy apiClient 验证路径、参数和表单字段。
// 不启动真实后端，避免网络依赖；这些测试保护前后端契约中的 URL 和 payload。

describe('practice api helpers', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  test('createPracticeSession posts payload to session endpoint', async () => {
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: { practice_id: 'prac_1' } })

    await createPracticeSession({ job_role: 'java', mode: 'sequence', question_count: 5 })

    expect(postSpy).toHaveBeenCalledWith('/practice/sessions', {
      job_role: 'java',
      mode: 'sequence',
      question_count: 5,
    })
  })

  test('fetchPracticeSession reads session by id', async () => {
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: { practice_id: 'prac_1' } })

    await fetchPracticeSession('prac_1')

    expect(getSpy).toHaveBeenCalledWith('/practice/sessions/prac_1')
  })

  test('submitPracticeAnswer posts answer payload to current practice', async () => {
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: { finished: false } })

    await submitPracticeAnswer('prac_1', { session_question_id: 'psq_1', answer_text: 'A' })

    expect(postSpy).toHaveBeenCalledWith('/practice/sessions/prac_1/answers', {
      session_question_id: 'psq_1',
      answer_text: 'A',
    })
  })

  test('finishPracticeSession posts to finish endpoint', async () => {
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: { status: 'FINISHED' } })

    await finishPracticeSession('prac_1')

    expect(postSpy).toHaveBeenCalledWith('/practice/sessions/prac_1/finish')
  })

  test('record and overview helpers use stable endpoints', async () => {
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: {} })

    await fetchPracticeRecords()
    await fetchPracticeOverview()
    await fetchPracticeSessionRecords('prac_1')

    expect(getSpy).toHaveBeenCalledWith('/practice/records')
    expect(getSpy).toHaveBeenCalledWith('/practice/overview')
    expect(getSpy).toHaveBeenCalledWith('/practice/sessions/prac_1/records')
  })

  test('fetchAdminQuestionBank forwards filter params', async () => {
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: { items: [] } })

    await fetchAdminQuestionBank({
      job_role: 'web',
      category: 'technical',
      keyword: 'React',
      page: 2,
      page_size: 20,
    })

    expect(getSpy).toHaveBeenCalledWith('/practice/questions', {
      params: {
        job_role: 'web',
        category: 'technical',
        keyword: 'React',
        page: 2,
        page_size: 20,
      },
    })
  })

  test('uploadQuestionBankMarkdown sends FormData and multipart header', async () => {
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: { task_id: 'task_1' } })
    const file = new File(['## 第 1 题：测试'], 'questions.md', { type: 'text/markdown' })

    await uploadQuestionBankMarkdown('java', file)

    const [url, formData, config] = postSpy.mock.calls[0]
    expect(url).toBe('/practice/questions/upload')
    expect(formData).toBeInstanceOf(FormData)
    expect((formData as FormData).get('job_role')).toBe('java')
    expect((formData as FormData).get('file')).toBe(file)
    expect(config).toEqual({ headers: { 'Content-Type': 'multipart/form-data' } })
  })

  test('fetchPracticeImportTask reads task state endpoint', async () => {
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: { task_id: 'task_1' } })

    await fetchPracticeImportTask('task_1')

    expect(getSpy).toHaveBeenCalledWith('/practice/questions/import-tasks/task_1')
  })
})
