import type { InterviewScheduleListItem } from '../api/interview'

// 预约日历工具函数保持纯函数：
// 1. 页面传入 Date 或 ISO 字符串，这里统一转换成本地日期键。
// 2. 月历固定生成 6 周 42 格，便于 UI 网格尺寸稳定。
// 3. 周一作为第一列，更符合中文用户的日历习惯。
// 4. groupSchedulesByDate 会按开始时间排序，页面渲染时不用再排序。
// 5. 工具层不依赖 React，方便单元测试覆盖。

/** 将时间转换为本地日期键。 */
export function toDateKey(value: Date | string): string {
  const date = value instanceof Date ? value : new Date(value)
  const year = date.getFullYear()
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  const day = `${date.getDate()}`.padStart(2, '0')
  return `${year}-${month}-${day}`
}

/** 获取月份第一天。 */
export function startOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1)
}

/** 获取月份最后一天。 */
export function endOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth() + 1, 0)
}

/** 获取月历网格起始日期（周一为第一列）。 */
export function getCalendarGridStart(date: Date): Date {
  const firstDay = startOfMonth(date)
  const weekDay = firstDay.getDay()
  const offset = weekDay === 0 ? 6 : weekDay - 1
  return new Date(firstDay.getFullYear(), firstDay.getMonth(), firstDay.getDate() - offset)
}

/** 生成月历六周网格。 */
export function buildCalendarDays(monthDate: Date): Date[] {
  const start = getCalendarGridStart(monthDate)
  return Array.from({ length: 42 }, (_, index) => new Date(start.getFullYear(), start.getMonth(), start.getDate() + index))
}

/** 判断两个日期是否同月。 */
export function isSameMonth(left: Date, right: Date): boolean {
  return left.getFullYear() === right.getFullYear() && left.getMonth() === right.getMonth()
}

/** 按日期分组预约列表。 */
export function groupSchedulesByDate(items: InterviewScheduleListItem[]): Map<string, InterviewScheduleListItem[]> {
  // Map 的 key 是 yyyy-MM-dd，本地日期语义与页面日历格保持一致。
  // 同一天多个预约按 scheduled_start_at 升序展示。
  const grouped = new Map<string, InterviewScheduleListItem[]>()
  for (const item of items) {
    const key = toDateKey(item.scheduled_start_at)
    const currentItems = grouped.get(key) ?? []
    currentItems.push(item)
    currentItems.sort((left, right) => left.scheduled_start_at.localeCompare(right.scheduled_start_at))
    grouped.set(key, currentItems)
  }
  return grouped
}
