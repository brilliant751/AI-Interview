import { describe, expect, test } from 'vitest'

import {
  buildCalendarDays,
  endOfMonth,
  getCalendarGridStart,
  groupSchedulesByDate,
  isSameMonth,
  startOfMonth,
  toDateKey,
} from './scheduleCalendar'
import type { InterviewScheduleListItem } from '../api/interview'

// 日历工具是预约页、首页概览和顶部提醒共同依赖的纯函数。
// 这些测试不需要渲染 React 页面，主要保护日期键、月历网格和预约排序规则。

function schedule(overrides: Partial<InterviewScheduleListItem>): InterviewScheduleListItem {
  return {
    schedule_id: overrides.schedule_id ?? 'sch_default',
    title: overrides.title ?? '模拟面试',
    status: overrides.status ?? 'scheduled',
    source_type: overrides.source_type ?? 'single',
    scheduled_start_at: overrides.scheduled_start_at ?? '2026-06-20T10:00:00+08:00',
    scheduled_end_at: overrides.scheduled_end_at ?? '2026-06-20T11:00:00+08:00',
    duration_minutes: overrides.duration_minutes ?? 60,
    job_role: overrides.job_role ?? 'java',
    difficulty: overrides.difficulty ?? 'medium',
    resume_id: overrides.resume_id ?? 'res_001',
    jd_id: overrides.jd_id ?? '',
    interview_id: overrides.interview_id ?? '',
    resume_file_name: overrides.resume_file_name ?? 'resume.pdf',
    google_calendar_url: overrides.google_calendar_url ?? '',
    outlook_calendar_url: overrides.outlook_calendar_url ?? '',
    created_at: overrides.created_at ?? '2026-06-01T00:00:00+08:00',
  }
}

describe('scheduleCalendar utilities', () => {
  test('toDateKey formats Date and string values as local date keys', () => {
    const date = new Date(2026, 5, 7, 9, 30, 0)

    expect(toDateKey(date)).toBe('2026-06-07')
    expect(toDateKey('2026-06-08T10:00:00+08:00')).toBe('2026-06-08')
  })

  test('startOfMonth and endOfMonth return calendar boundaries', () => {
    const date = new Date(2026, 5, 17, 12, 0, 0)

    expect(startOfMonth(date).getDate()).toBe(1)
    expect(startOfMonth(date).getMonth()).toBe(5)
    expect(endOfMonth(date).getDate()).toBe(30)
    expect(endOfMonth(date).getMonth()).toBe(5)
  })

  test('getCalendarGridStart uses Monday as the first column', () => {
    const month = new Date(2026, 5, 1)
    const gridStart = getCalendarGridStart(month)

    expect(toDateKey(gridStart)).toBe('2026-06-01')
  })

  test('buildCalendarDays always returns six full weeks', () => {
    const days = buildCalendarDays(new Date(2026, 5, 15))

    expect(days).toHaveLength(42)
    expect(toDateKey(days[0])).toBe('2026-06-01')
    expect(toDateKey(days[41])).toBe('2026-07-12')
  })

  test('isSameMonth compares year and month together', () => {
    expect(isSameMonth(new Date(2026, 5, 1), new Date(2026, 5, 30))).toBe(true)
    expect(isSameMonth(new Date(2026, 5, 1), new Date(2027, 5, 1))).toBe(false)
    expect(isSameMonth(new Date(2026, 5, 1), new Date(2026, 6, 1))).toBe(false)
  })

  test('groupSchedulesByDate groups and sorts schedules by start time', () => {
    const grouped = groupSchedulesByDate([
      schedule({ schedule_id: 'late', scheduled_start_at: '2026-06-20T19:00:00+08:00' }),
      schedule({ schedule_id: 'early', scheduled_start_at: '2026-06-20T09:00:00+08:00' }),
      schedule({ schedule_id: 'other', scheduled_start_at: '2026-06-21T09:00:00+08:00' }),
    ])

    expect([...grouped.keys()]).toEqual(['2026-06-20', '2026-06-21'])
    expect(grouped.get('2026-06-20')?.map((item) => item.schedule_id)).toEqual(['early', 'late'])
    expect(grouped.get('2026-06-21')?.map((item) => item.schedule_id)).toEqual(['other'])
  })
})
