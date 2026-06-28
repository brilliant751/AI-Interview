import { afterEach, describe, expect, test, vi } from 'vitest'

import { apiClient } from './client'
import {
  cancelInterviewSchedule,
  createInterview,
  deleteInterviewHistory,
  deleteJd,
  deleteResume,
  downloadInterviewScheduleCalendar,
  fetchInterviewStatus,
  fetchScheduledInterviews,
  finishInterview,
  startScheduledInterview,
  submitAudioTurn,
  submitTurn,
  uploadJd,
  uploadResume,
} from './interview'

// interview API helper 覆盖面广，是前端和后端面试域契约的集中入口。
// 这些测试只验证 URL、payload、FormData 和参数序列化，不依赖真实网络。

describe('interview api helpers', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  test('uploadResume sends multipart FormData', async () => {
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: { resume_id: 'res_1' } })
    const file = new File(['resume'], 'resume.pdf', { type: 'application/pdf' })

    await uploadResume(file)

    const [url, formData, config] = postSpy.mock.calls[0]
    expect(url).toBe('/resumes')
    expect(formData).toBeInstanceOf(FormData)
    expect((formData as FormData).get('file')).toBe(file)
    expect(config).toEqual({ headers: { 'Content-Type': 'multipart/form-data' } })
  })

  test('delete helpers call stable resource endpoints', async () => {
    const deleteSpy = vi.spyOn(apiClient, 'delete').mockResolvedValue({ data: { deleted: true } })

    await deleteResume('res_1')
    await deleteInterviewHistory('int_1')
    await deleteJd('jd_1')

    expect(deleteSpy).toHaveBeenCalledWith('/resumes/res_1')
    expect(deleteSpy).toHaveBeenCalledWith('/interviews/history/int_1')
    expect(deleteSpy).toHaveBeenCalledWith('/jds/jd_1')
  })

  test('createInterview posts complete interview payload', async () => {
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: { interview_id: 'int_1' } })

    await createInterview({
      resume_id: 'res_1',
      job_role: 'java',
      difficulty: 'medium',
      input_mode: 'text',
      output_mode: 'voice',
      question_types: ['project', 'technical'],
      jd_id: 'jd_1',
    })

    expect(postSpy).toHaveBeenCalledWith('/interviews', {
      resume_id: 'res_1',
      job_role: 'java',
      difficulty: 'medium',
      input_mode: 'text',
      output_mode: 'voice',
      question_types: ['project', 'technical'],
      jd_id: 'jd_1',
    })
  })

  test('submitTurn posts answer payload and receives job response', async () => {
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: { job_id: 'job_1' } })

    await submitTurn('int_1', {
      stage: 'TECHNICAL',
      answer_text: '我的回答',
      asr_text: '',
      answer_audio_url: '',
      answer_audio_format: 'mp3',
    })

    expect(postSpy).toHaveBeenCalledWith('/interviews/int_1/turns', {
      stage: 'TECHNICAL',
      answer_text: '我的回答',
      asr_text: '',
      answer_audio_url: '',
      answer_audio_format: 'mp3',
    })
  })

  test('submitAudioTurn sends stage and file as multipart data', async () => {
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: { job_id: 'job_audio' } })
    const file = new File(['audio'], 'answer.wav', { type: 'audio/wav' })

    await submitAudioTurn('int_1', { stage: 'SELF_INTRO', file })

    const [url, formData, config] = postSpy.mock.calls[0]
    expect(url).toBe('/interviews/int_1/turns/audio')
    expect((formData as FormData).get('stage')).toBe('SELF_INTRO')
    expect((formData as FormData).get('file')).toBe(file)
    expect(config).toEqual({ headers: { 'Content-Type': 'multipart/form-data' } })
  })

  test('finishInterview uses longer timeout for report trigger path', async () => {
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: { report_status: 'GENERATING' } })

    await finishInterview('int_1')

    expect(postSpy).toHaveBeenCalledWith('/interviews/int_1/finish', undefined, { timeout: 30000 })
  })

  test('schedule actions call expected endpoints', async () => {
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: {} })
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: new Blob() })

    await cancelInterviewSchedule('sch_1', '临时有事')
    await downloadInterviewScheduleCalendar('sch_1')
    await startScheduledInterview('int_1')

    expect(postSpy).toHaveBeenCalledWith('/interview-schedules/sch_1/cancel', { reason: '临时有事' })
    expect(getSpy).toHaveBeenCalledWith('/interview-schedules/sch_1/calendar.ics', { responseType: 'blob' })
    expect(postSpy).toHaveBeenCalledWith('/interviews/int_1/start')
  })

  test('fetchInterviewStatus forwards optional status param', async () => {
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: { interview_id: 'int_1' } })

    await fetchInterviewStatus('int_1', { status: 'ACTIVE' })

    expect(getSpy).toHaveBeenCalledWith('/interviews/int_1/status', { params: { status: 'ACTIVE' } })
  })

  test('fetchScheduledInterviews serializes status list as comma separated string', async () => {
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: { items: [] } })

    await fetchScheduledInterviews({
      scheduled_from: '2026-06-01T00:00:00.000Z',
      scheduled_to: '2026-06-30T23:59:59.999Z',
      statuses: ['SCHEDULED', 'ACTIVE', 'PAUSED'],
    })

    expect(getSpy).toHaveBeenCalledWith('/interviews/schedules', {
      params: {
        scheduled_from: '2026-06-01T00:00:00.000Z',
        scheduled_to: '2026-06-30T23:59:59.999Z',
        statuses: 'SCHEDULED,ACTIVE,PAUSED',
      },
    })
  })

  test('uploadJd supports both text and file fields in one FormData payload', async () => {
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: { jd_id: 'jd_1' } })
    const file = new File(['jd'], 'jd.docx')

    await uploadJd({
      job_role: 'java',
      title: '后端 JD',
      file,
      content_text: '岗位描述',
      company_id: 'company_1',
    })

    const [url, formData, config] = postSpy.mock.calls[0]
    expect(url).toBe('/jds')
    expect((formData as FormData).get('job_role')).toBe('java')
    expect((formData as FormData).get('title')).toBe('后端 JD')
    expect((formData as FormData).get('file')).toBe(file)
    expect((formData as FormData).get('content_text')).toBe('岗位描述')
    expect((formData as FormData).get('company_id')).toBe('company_1')
    expect(config).toEqual({ headers: { 'Content-Type': 'multipart/form-data' } })
  })
})
