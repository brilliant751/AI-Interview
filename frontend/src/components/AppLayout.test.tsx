import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, test } from 'vitest'

import { AppLayout } from './AppLayout'

/** AppLayout 渲染测试。 */
describe('AppLayout', () => {
  test('should render navigation labels', () => {
    render(
      <MemoryRouter>
        <AppLayout>
          <div>content</div>
        </AppLayout>
      </MemoryRouter>,
    )

    expect(screen.getByText('AI Interview')).toBeInTheDocument()
    expect(screen.getByText('上传简历')).toBeInTheDocument()
    expect(screen.getByText('模拟面试')).toBeInTheDocument()
    expect(screen.getByText('面试报告')).toBeInTheDocument()
    expect(screen.getByText('历史记录')).toBeInTheDocument()
  })
})

