import { render, screen } from '@testing-library/react'
import { describe, expect, test } from 'vitest'

import { WorkspaceStatus } from './WorkspaceStatus'

describe('WorkspaceStatus', () => {
  test('renders demo status tags', () => {
    render(<WorkspaceStatus />)

    expect(screen.getByText('Workspace status')).toBeInTheDocument()
    expect(screen.getByText('Demo build')).toBeInTheDocument()
    expect(screen.getByText('Interview flow')).toBeInTheDocument()
    expect(screen.getByText('Practice module')).toBeInTheDocument()
  })
})
